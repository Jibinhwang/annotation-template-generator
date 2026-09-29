#!/usr/bin/env python3
"""
plan_from_prompt.py — 사용자 prompt + 데이터 분석 결과 → plan.json (LLM)

    python plan_from_prompt.py raw.json "passage 두 개를 나란히 보여주고 어느 쪽이 질문에 더 잘 답하는지 고르게 하자" \
        --stats analyze_out/stats.json --out plan.json [--model ...] [--confirm]

LLM에게 주는 것
    1. plan 스키마 설명 (plan.py docstring)
    2. 데이터 컨텍스트: analyze의 stats.json 요약 (필드, 축, 크기) + 실제 item 1개를 잘라낸 샘플
    3. 예시 plan 2개 (few-shot)
    4. 사용자 prompt
LLM이 주는 것: {"plan": {...}, "rationale": "..."}
검증: validate_plan(plan, 샘플 20개) — 경로가 실제로 값을 돌려주는지까지. 실패 시 오류를 돌려주고 최대 2회 재시도.
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from plan import plan_schema_doc, example_plans, validate_plan
from jsonpath import normalize, resolve
from llm_client import chat

SYSTEM = """You design human-annotation tasks for Mechanical Turk. Given (a) a description of a JSON dataset and (b) a researcher's
request in natural language (Korean or English), write a task plan as JSON following the PLAN SCHEMA exactly.
Output ONLY a JSON object: {"plan": <plan>, "rationale": "<2-4 sentences: what unit/widget you chose and why, any assumption>"}.
Rules:
- roles.*.path must be real paths from DATA CONTEXT (use the path grammar: a.b, list[], list[:k], enumerated_dict{}).
  Prefer the retriever / model the user names; otherwise choose one that exists and say so in rationale.
  Limit passages with [:k] (default 10) — never show 30 passages in one item.
- Pick the smallest unit that matches the request: compare two → unit.type=pair; judge each passage → single; judge the item's
  whole answer → item.
- Widgets: multi_select (tick several), single_choice (exactly one of 2-5 options; use for A/B, 3-way, categories),
  likert (numeric scale), free_text (short written answer). Use per="role:<r>" when the same question is asked for every element
  of a list (e.g., every atomic fact).
- Write instructions in clear English for crowd workers: summary, background, definitions (terms of art), 3-5 howto bullets, tip.
  Use <strong>/<em> HTML for emphasis only.
- attention: use strategy "mismatch" with an expected answer that is unambiguous for a swapped-in unrelated passage/fact
  (e.g., "none", "Not mentioned", the middle of a scale, or the gold side of a pair). Set expected for free_text to null.
- gold: if DATA CONTEXT contains existing model labels that answer THE SAME question (e.g. relevance_check.*.chunk_fact_relevance
  for "which facts does this passage support"), attach them via question.gold so human answers can be compared with them, and set
  hit.sampling="balanced". If no such labels exist for the question (a new kind of judgment), set gold to null and sampling "random".
  Never attach labels that answer a different question. For a multi_select question whose options come from an enumerated role,
  gold.value MUST be "enum_index" (labels like "Atomic fact3" become option index 2). Use "raw" only for single_choice string labels.
- Sensible defaults: filters.max_role_size for list roles shown as options (facts ≤ 8, subqueries ≤ 4); hit.n_hits 20 unless told.
- Copy the user's numbers (top-k, number of HITs, items per HIT) when given. Never invent keys not in the schema.
- Paths use dot notation exactly as listed in DATA CONTEXT (e.g. relevance_check.BM25.GPT-5.query_chunk_coverage). Never use '/'.
  For gold, copy a path from LABEL CONTAINERS verbatim.
- Worker-facing text (instructions, card labels, prompts, options) must never mention internal system names such as retriever or
  model identifiers (BM25, ANCE, GPT-5, Claude, Qwen...). Say "the system's answer", "retrieved passage", "atomic statement".
PLAN SCHEMA:
""" + plan_schema_doc()


def shrink(v, depth=0):
    """샘플 item을 LLM에 보여줄 수 있게 줄인다: 문자열 160자, 리스트 2개, dict 6키."""
    if isinstance(v, str):
        return v if len(v) <= 160 else v[:160] + f"…(+{len(v)-160} chars)"
    if isinstance(v, list):
        out = [shrink(x, depth + 1) for x in v[:2]]
        if len(v) > 2:
            out.append(f"…(+{len(v)-2} more)")
        return out
    if isinstance(v, dict):
        keys = list(v)
        out = {k: shrink(v[k], depth + 1) for k in keys[:6]}
        if len(keys) > 6:
            out["…"] = f"+{len(keys)-6} more keys: {keys[6:12]}"
        return out
    return v


def known_paths(stats):
    """stats.json의 경로들을 plan 문법(점 표기)으로. gold 제안/검증 힌트에 씀."""
    out = set()
    for p in list(stats.get("categorical_axes", {})) + list(stats.get("enum_axes", {})):
        n = normalize(p)
        if n:
            out.add(n)
    for p in stats.get("enum_axes", {}):
        n = normalize(p)
        if n and not n.endswith("{}"):
            out.add(n + "{}")
    return sorted(out)


def data_context(stats, sample):
    skip = lambda p: "reasoning" in p or "_text" in p
    lines = [f"items: {stats.get('n_items')}   id field: {stats.get('id_field')}",
             "top-level fields: " + ", ".join(stats.get("top_level_fields", {})),
             "", "CATEGORICAL AXES (dict keys that repeat across items, e.g. retriever / model names) — dot paths:"]
    for p, vocab in stats.get("categorical_axes", {}).items():
        if len(vocab) <= 20 and not skip(p):
            lines.append(f"  {normalize(p)} → keys {list(vocab)}")
    lines.append("")
    lines.append(f"ENUMERATED CONTAINERS (dict keyed like 'Chunk 3' / 'Atomic fact2' → write the path with {{}} to get an index-ordered list):")
    for p, names in stats.get("enum_axes", {}).items():
        if skip(p):
            continue
        n = normalize(p)
        ex = resolve(sample, n + "{}") if not n.endswith("{}") else resolve(sample, n)
        lines.append(f"  {n}{{}}  ← keys '{list(names)[0]} N';  sample value: {json.dumps(shrink(ex), ensure_ascii=False)[:160]}")
    lines.append("")
    lines.append("LABEL CONTAINERS (existing model judgments; candidates for question.gold — copy the path verbatim):")
    lab = [normalize(p) for p in stats.get("enum_axes", {}) if "relevance" in p or "label" in p or "judg" in p or "coverage" in p]
    lab = [l for l in lab if not skip(l)]
    lines += [f"  {l}   (lookup by the enumerated key; values look like: {json.dumps(shrink(resolve(sample, l)), ensure_ascii=False)[:140]})" for l in lab] or ["  (none found)"]
    lines.append("")
    lines.append("SIZES per item (path: median/max):")
    for p, d in stats.get("size_distributions", {}).items():
        if d.get("max", 0) > 1 and not skip(p):
            lines.append(f"  {normalize(p)}: {d['median']}/{d['max']}")
    lines.append("\nONE SAMPLE ITEM (truncated):\n" + json.dumps(shrink(sample), ensure_ascii=False, indent=1))
    return "\n".join(lines)


DEFAULT_SHOTS = ("completeness_conciseness", "groundedness_multiselect", "retrieval_coverage", "pairwise_passages")


def make_plan(prompt, items, stats, model=None, max_retry=2, log=print, attempts_dir=None, shots=None):
    """attempts_dir: 시도마다 {llm 응답, 검증 오류}를 attempt_N.json 으로 저장 (프롬프트 개선용 진단 로그).
    shots: few-shot으로 보여줄 plans/ 이름 리스트. None=기본 4개, []=예시 없이 (일반화 테스트용)."""
    ex = example_plans()
    names = DEFAULT_SHOTS if shots is None else shots
    unknown = [n for n in names if n not in ex]
    if unknown:
        raise SystemExit(f"--shots 에 없는 plan 이름: {unknown}. 가능한 값: {sorted(ex)}")
    shots_plans = [ex[k] for k in names]
    log(f"  few-shot: {list(names) or '(없음)'}")
    user = ("DATA CONTEXT:\n" + data_context(stats, items[0]) +
            ("\n\nEXAMPLE PLANS (for a similar dataset; adapt paths to the DATA CONTEXT above):\n" + json.dumps(shots_plans, ensure_ascii=False) if shots_plans else "") +
            "\n\nREQUEST:\n" + prompt)
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    errs, obj = ["no attempt"], None
    for attempt in range(max_retry + 1):
        try:
            text, _ = chat(msgs, model=model, purpose="plan_from_prompt", json_mode=True, max_tokens=16000)
        except RuntimeError as e:   # 빈 응답 / 잘림 / HTTP 오류 → 대화에 붙이지 않고 같은 요청을 재시도
            log(f"  LLM 호출 실패 (시도 {attempt+1}): {str(e)[:300]}")
            errs = [str(e)]
            continue
        try:
            obj = json.loads(text)
            plan = obj["plan"]
            plan.setdefault("name", "custom_task")
            errs = validate_plan(plan, items[:20], known_paths(stats))
        except Exception as e:
            errs = [f"invalid JSON/shape: {e}"]
        if attempts_dir:
            os.makedirs(attempts_dir, exist_ok=True)
            json.dump({"attempt": attempt + 1, "errors": errs, "response": text},
                      open(os.path.join(attempts_dir, f"attempt_{attempt+1}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if not errs:
            return plan, obj.get("rationale", "")
        log(f"  plan 검증 실패 (시도 {attempt+1}): " + "; ".join(errs)[:400])
        msgs += [{"role": "assistant", "content": text},
                 {"role": "user", "content": "The plan failed validation. Fix these and output the full JSON again:\n- " + "\n- ".join(errs)}]
    raise SystemExit("plan 생성 실패: " + "; ".join(errs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw"); ap.add_argument("prompt")
    ap.add_argument("--stats", required=True); ap.add_argument("--out", default="plan.json")
    ap.add_argument("--model"); ap.add_argument("--confirm", action="store_true", help="저장 전에 plan을 보여주고 y/n 확인")
    ap.add_argument("--shots", nargs="*", default=None, help="few-shot 예시 plan 이름들 (plans/ 파일명). 'none' 이면 예시 없이")
    a = ap.parse_args()
    data = json.load(open(a.raw, encoding="utf-8"))
    items = list(data.values()) if isinstance(data, dict) else data
    stats = json.load(open(a.stats, encoding="utf-8"))
    shots = None if a.shots is None else ([] if a.shots == ["none"] else a.shots)
    plan, rationale = make_plan(a.prompt, items, stats, a.model, shots=shots)
    print("--- rationale ---\n" + rationale + "\n--- plan ---\n" + json.dumps(plan, ensure_ascii=False, indent=2))
    if a.confirm and input("이 plan으로 진행할까요? [y/N] ").strip().lower() != "y":
        sys.exit("취소됨")
    json.dump(plan, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
