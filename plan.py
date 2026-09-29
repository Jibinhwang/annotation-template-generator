"""
plan.py — v2의 핵심 객체 "task plan": 어떤 데이터를, 어떤 단위로, 어떤 화면에, 어떤 질문으로 물을지.

사용자 prompt + 데이터 분석 결과를 보고 LLM이 이 JSON을 쓴다 (plan_from_prompt.py).
사람이 직접 써도 된다 (plans/ 폴더의 예시 참고). preprocess_v2 / render_v2 는 plan을 실행만 한다.

{
  "name": "short_slug_name",  "description": "...",     # name: letters/digits/_/- only (hit_id prefix)
  "id_path": "qid",
  "roles": {                                  # 데이터 안의 역할 → 경로 (jsonpath.py 문법)
    "question":   {"path": "query"},                       # 스칼라
    "subqueries": {"path": "decomposed_query{}"},          # 리스트
    "facts":      {"path": "atomic_facts.BM25.GPT-5{}"},
    "passages":   {"path": "retrieved_chunk.BM25[:10]"},
    "gt":         {"path": "gt_chunk[]"}
  },
  "unit": {"type": "single" | "pair" | "item", "of": "<list role>", "pairing": "adjacent" | "random"},
      # single: 리스트 role의 원소 하나 = annotation 항목 1개  (예: passage 하나)
      # pair  : 리스트 role의 원소 두 개 = 항목 1개             (예: passage A/B 비교)
      # item  : 데이터 item 자체 = 항목 1개                     (예: query 하나에 fact 전체)
  "display": {
    "context": [{"role": "question", "label": "Question"}, ...],   # 상단 맥락 카드 (스칼라/리스트 모두 가능)
    "left":  {"label": "Passage",  "source": "unit" | "unit.a" | "unit.b" | "role:<name>"},
    "right": {"label": "Statements", "source": "role:facts"}         # right는 생략 가능
  },
  "questions": [                              # 항목 안에서 묻는 질문들 (1개 이상)
    {"id": "support", "prompt": "Which statements are supported?",
     "widget": "multi_select" | "single_choice" | "likert" | "free_text",
     "per": "unit" | "role:<list role>",      # unit: 항목당 1번 / role:facts: fact마다 1번씩 반복
     "options": ["...", ...]                  # multi_select(고정 옵션) / single_choice 에서 사용
     "options_from": "role:facts",            # multi_select 옵션을 role 리스트에서 (options 대신)
     "none_option": "None of the above",      # multi_select 전용, 생략 가능
     "scale": {"min": 1, "max": 5, "min_label": "...", "max_label": "..."},   # likert
     "min_chars": 20,                         # free_text
     "required": true,
     "gold": {                                # (선택) 이 질문에 대한 기존 LLM 라벨이 데이터에 있으면 그 위치. 없으면 생략/null
       "path": "relevance_check.BM25.GPT-5.chunk_fact_relevance",   # 라벨 컨테이너 (dict 또는 list)
       "lookup": "unit" | "rep" | null,       # unit: 현재 unit의 인덱스로 컨테이너에서 찾기 ("Chunk 3" ↔ passages[2])
                                              # rep : per="role:x" 반복의 인덱스로 찾기 ("Core subquery2" ↔ subqueries[1])
       "field": "selected_facts",             # (선택) 찾은 값이 dict면 이 키를 꺼냄
       "value": "enum_index" | "raw"}         # enum_index: "Atomic fact3" → 2 로 변환 (multi_select 답과 같은 형식)
     }
  ],
  "instructions": {"title","summary","background","definitions":[["term","meaning"],...],"howto":[...],"tip"},
  "hit": {"group_by_item": true, "items_per_hit": 10, "n_hits": 20, "seed": 0, "sampling": "random" | "balanced"},
      # group_by_item: single/pair 단위일 때 한 item의 unit들을 한 HIT으로 (query 1개 × passage 10개)
      # balanced: 첫 gold 있는 질문 기준으로 positive(gold 비어있지 않음) item ≈70% / negative 30% 로 섞음
  "filters": {"max_role_size": {"facts": 8, "subqueries": 4}, "id_prefix": null, "exclude_ids": "auto"},
  "attention": {"strategy": "mismatch" | "none", "per_hit": 1,
                "swap": "unit" | "unit.b" | "role:<name>",         # 무엇을 남의 item 것으로 바꿀지
                "set": {"unit.a": "role:gt"},                        # (선택) 바꾸기 전에 자기 item 값으로 고정
                "expected": {"<question id>": "<정답 옵션 | none | 숫자 | null>"}}
}
"""
import json, os, glob

WIDGETS = ("multi_select", "single_choice", "likert", "free_text")
UNIT_TYPES = ("single", "pair", "item")

PLAN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plans")


def load_plan(path):
    return json.load(open(path, encoding="utf-8"))


def example_plans():
    return {os.path.basename(p)[:-5]: load_plan(p) for p in sorted(glob.glob(os.path.join(PLAN_DIR, "*.json")))}


def _role_names(plan):
    return set(plan.get("roles", {}))


def _source_ok(src, plan, allow_unit):
    if src in ("unit", "unit.a", "unit.b"):
        return allow_unit
    return src.startswith("role:") and src[5:] in _role_names(plan)


def _suggest(path, known):
    """known 경로 중 토큰 겹침이 가장 큰 것 (오타/표기 실수 교정 힌트)."""
    import re as _re
    from difflib import SequenceMatcher
    toks = set(_re.split(r"[./{}\[\]:]+", str(path).lower())) - {""}
    ks = [k.rstrip("{}") for k in known]
    leaves = [k for k in ks if not any(o != k and o.startswith(k + ".") for o in ks)]   # 다른 경로의 접두사인 것 제외
    best, score = None, 0.0
    for k in leaves:
        kt = set(_re.split(r"[./{}\[\]:]+", k.lower())) - {""}
        jacc = len(toks & kt) / max(1, len(toks | kt))          # 토큰 집합 유사도
        s = jacc + 0.5 * SequenceMatcher(None, str(path).lower(), k.lower()).ratio()   # 철자 유사도
        if s > score:
            best, score = k, s
    return best


def validate_plan(plan, sample_items=None, known_paths=None):
    """구조 검증 + (샘플 item이 있으면) 경로가 실제로 값을 돌려주는지 검증. 오류 문자열 리스트 반환."""
    from jsonpath import resolve, is_list_path
    E = []
    roles = plan.get("roles") or {}
    if not roles:
        E.append("roles is empty")
    for r, spec in roles.items():
        if not isinstance(spec, dict) or "path" not in spec:
            E.append(f"role {r!r} needs {{'path': ...}}")
    unit = plan.get("unit") or {}
    ut = unit.get("type")
    if ut not in UNIT_TYPES:
        E.append(f"unit.type must be one of {UNIT_TYPES}")
    if ut in ("single", "pair"):
        of = unit.get("of")
        if of not in roles:
            E.append(f"unit.of must name a list role, got {of!r}")
        elif not is_list_path(roles[of]["path"]):
            E.append(f"unit.of role {of!r} is not a list path ({roles[of]['path']}) — add [] / [:k] / {{}}")
    disp = plan.get("display") or {}
    for c in disp.get("context", []):
        if c.get("role") not in roles:
            E.append(f"display.context role {c.get('role')!r} unknown")
    for slot in ("left", "right"):
        if slot in disp and disp[slot]:
            if not _source_ok(disp[slot].get("source", ""), plan, ut != "item"):
                E.append(f"display.{slot}.source {disp[slot].get('source')!r} invalid (unit sources need unit.type single/pair)")
            if ut != "pair" and disp[slot].get("source") in ("unit.a", "unit.b"):
                E.append(f"display.{slot}.source unit.a/unit.b requires unit.type=pair")
    qs = plan.get("questions") or []
    if not qs:
        E.append("questions is empty")
    ids = set()
    for q in qs:
        qid = q.get("id")
        if not qid or qid in ids:
            E.append(f"question id missing/duplicate: {qid!r}")
        ids.add(qid)
        if q.get("widget") not in WIDGETS:
            E.append(f"question {qid}: widget must be one of {WIDGETS}")
        per = q.get("per", "unit")
        if per != "unit" and not (per.startswith("role:") and per[5:] in roles):
            E.append(f"question {qid}: per must be 'unit' or 'role:<name>'")
        if q.get("widget") == "single_choice" and len(q.get("options") or []) < 2:
            E.append(f"question {qid}: single_choice needs >=2 options")
        if q.get("widget") == "multi_select" and not (q.get("options") or q.get("options_from")):
            E.append(f"question {qid}: multi_select needs options or options_from")
        if q.get("options_from") and not _source_ok(q["options_from"], plan, False):
            E.append(f"question {qid}: options_from must be role:<list role>")
        g = q.get("gold")
        if g:
            if not isinstance(g, dict) or not g.get("path"):
                E.append(f"question {qid}: gold needs a path")
            elif g.get("lookup") not in (None, "unit", "rep"):
                E.append(f"question {qid}: gold.lookup must be unit|rep|null")
            elif g.get("lookup") == "unit" and ut == "item":
                E.append(f"question {qid}: gold.lookup=unit requires unit.type single/pair")
            elif g.get("lookup") == "rep" and per == "unit":
                E.append(f"question {qid}: gold.lookup=rep requires per=role:<x>")
        if q.get("widget") == "likert":
            sc = q.get("scale") or {}
            if not (isinstance(sc.get("min"), int) and isinstance(sc.get("max"), int) and sc["max"] > sc["min"]):
                E.append(f"question {qid}: likert needs scale.min < scale.max (ints)")
    ins = plan.get("instructions") or {}
    for k in ("title", "summary"):
        if not isinstance(ins.get(k), str) or len(ins[k].strip()) < 5:
            E.append(f"instructions.{k} must be a non-empty string")
    howto = ins.get("howto")
    if not isinstance(howto, list) or not howto or not all(isinstance(h, str) and len(h.strip()) >= 5 for h in howto):
        E.append("instructions.howto must be a list of 3-6 non-empty sentences (strings)")
    defs = ins.get("definitions", [])
    if not isinstance(defs, list) or not all(isinstance(d, list) and len(d) == 2 and all(isinstance(x, str) and x.strip() for x in d) for d in defs):
        E.append("instructions.definitions must be a list of [term, meaning] string pairs")
    import re as _re
    if not _re.match(r"^[A-Za-z0-9_\-]+$", str(plan.get("name", ""))):
        E.append("name must be a short slug: letters, digits, '_' or '-' only (it becomes the hit_id prefix)")
    att = plan.get("attention") or {"strategy": "none"}
    if att.get("strategy", "none") not in ("none", "mismatch"):
        E.append("attention.strategy must be none|mismatch")
    qmap = {q.get("id"): q for q in qs}
    for k, v in (att.get("expected") or {}).items():
        q = qmap.get(k)
        if not q:
            continue
        w = q.get("widget")
        if w == "multi_select" and not (v == "none" or (isinstance(v, list) and all(isinstance(i, int) for i in v))):
            E.append(f"attention.expected[{k}]: for multi_select use the literal string \"none\" (or a list of option indices), not the option label")
        elif w == "single_choice" and v not in (q.get("options") or []):
            E.append(f"attention.expected[{k}] must be one of options {q.get('options')}")
        elif w == "likert" and not isinstance(v, int):
            E.append(f"attention.expected[{k}] must be an integer on the scale")
        elif w == "free_text" and v is not None:
            E.append(f"attention.expected[{k}] must be null for free_text")
    if att.get("strategy") == "mismatch":
        sw = att.get("swap", "")
        if not _source_ok(sw, plan, ut != "item"):
            E.append(f"attention.swap {sw!r} invalid")
        for k in (att.get("expected") or {}):
            if k not in ids:
                E.append(f"attention.expected references unknown question {k!r}")
    # 경로 실검증 (roles가 구조적으로 멀쩡하면 다른 오류가 있어도 같이 알려준다 → 재시도 횟수 절약)
    if sample_items and roles and all(isinstance(s, dict) and "path" in s for s in roles.values()):
        for r, spec in roles.items():
            hits = 0
            for it in sample_items:
                v = resolve(it, spec["path"])
                if v not in (None, []):
                    hits += 1
            if hits == 0:
                E.append(f"role {r!r}: path {spec['path']!r} resolves to nothing in {len(sample_items)} sample items")
        if plan.get("id_path"):
            if all(resolve(it, plan["id_path"]) is None for it in sample_items):
                E.append(f"id_path {plan['id_path']!r} not found")
        for q in qs:
            g = q.get("gold")
            if isinstance(g, dict) and g.get("path") and q.get("widget") == "single_choice" and g.get("value", "raw") == "raw":
                # gold 라벨 어휘가 선택지 문자열과 정확히 같아야 나중에 사람 답과 비교 가능
                vocab = set()
                for it in sample_items:
                    v = resolve(it, g["path"])
                    vals = list(v.values()) if isinstance(v, dict) else (v if isinstance(v, list) else [v])
                    for x in vals:
                        if g.get("field") and isinstance(x, dict):
                            x = x.get(g["field"])
                        if isinstance(x, str):
                            vocab.add(x)
                missing = sorted(vocab - set(q.get("options") or []))
                if vocab and missing:
                    E.append(f"question {q.get('id')}: gold labels in data are {sorted(vocab)} but options are {q.get('options')} — "
                             f"options must use exactly these label strings (or set gold to null)")
            if isinstance(g, dict) and g.get("path"):
                if all(resolve(it, g["path"]) in (None, [], {}) for it in sample_items):
                    hint = _suggest(g["path"], known_paths or [])
                    E.append(f"question {q.get('id')}: gold.path {g['path']!r} resolves to nothing. "
                             + (f"Did you mean {hint!r}? Fix the path (dot notation, copy from LABEL CONTAINERS). " if hint else "")
                             + "Only set gold to null if no listed container answers this question.")
    return E


def plan_schema_doc():
    """LLM에게 보여줄 스키마 설명 = 이 파일의 docstring."""
    return __doc__
