#!/usr/bin/env python3
"""
run_pipeline_v2.py — 사용자 prompt + raw JSON → annotation HTML, end-to-end (v2: plan 기반, 형식 자유)

    # 자연어 prompt (LLM이 데이터 분석 결과를 보고 plan을 씀; OPENROUTER_API_KEY 또는 .env 필요)
    python run_pipeline_v2.py raw.json --prompt "passage 두 개를 나란히 보여주고 어느 쪽이 질문에 더 잘 답하는지 고르게 하자. HIT 20개" --out runs/pairwise --open

    # 미리 써둔 plan (LLM 없이)
    python run_pipeline_v2.py raw.json --plan plans/threeway_support.json --out runs/threeway

산출물: <out>/1_analyze  2_plan/plan.json(+prompt.txt, rationale.txt)  3_prep/hits.csv  4_render/preview.html, template.html  pipeline_summary.json
"""
import argparse, json, os, shutil, subprocess, sys, time, webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE
sys.path.insert(0, HERE)
PY = sys.executable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--prompt"); ap.add_argument("--plan")
    ap.add_argument("--out", default="runs/latest_v2"); ap.add_argument("--model")
    ap.add_argument("--confirm", action="store_true", help="LLM이 만든 plan을 보여주고 승인 후 진행")
    ap.add_argument("--shots", nargs="*", default=None, help="few-shot 예시 plan 이름들. 'none' 이면 예시 없이 (일반화 테스트)")
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    if bool(a.prompt) == bool(a.plan):
        sys.exit("--prompt 또는 --plan 중 하나를 지정")

    out = os.path.abspath(a.out)
    d1, d2, d3, d4 = [os.path.join(out, n) for n in ("1_analyze", "2_plan", "3_prep", "4_render")]
    for d in (d1, d2, d3, d4):
        os.makedirs(d, exist_ok=True)
    T = {}

    t = time.time()
    print("=== 1/4 analyze")
    r = subprocess.run([PY, os.path.join(ROOT, "analyze.py"), a.raw, "--out", d1], text=True, capture_output=True)
    print(r.stdout.strip());
    if r.returncode:
        sys.exit(r.stderr)
    T["analyze"] = round(time.time() - t, 1)
    stats = json.load(open(os.path.join(d1, "stats.json"), encoding="utf-8"))
    data = json.load(open(a.raw, encoding="utf-8"))
    items = list(data.values()) if isinstance(data, dict) else data

    plan_path = os.path.join(d2, "plan.json")
    t = time.time()
    if a.prompt:
        print("\n=== 2/4 plan (LLM)")
        from plan_from_prompt import make_plan
        open(os.path.join(d2, "prompt.txt"), "w", encoding="utf-8").write(a.prompt)
        shots = None if a.shots is None else ([] if a.shots == ["none"] else a.shots)
        plan, rationale = make_plan(a.prompt, items, stats, a.model, attempts_dir=os.path.join(d2, "attempts"), shots=shots)
        open(os.path.join(d2, "shots.txt"), "w", encoding="utf-8").write("\n".join(shots if shots is not None else list(__import__("plan_from_prompt").DEFAULT_SHOTS)))
        open(os.path.join(d2, "rationale.txt"), "w", encoding="utf-8").write(rationale)
        print("--- rationale ---\n" + rationale)
        print(f"--- plan: {plan['name']} | unit={plan['unit']} | questions=" +
              ", ".join(f"{q['id']}({q['widget']}, per={q.get('per','unit')})" for q in plan["questions"]))
        print("--- roles: " + ", ".join(f"{k}={v['path']}" for k, v in plan["roles"].items()))
        if a.confirm and input("이 plan으로 진행할까요? [y/N] ").strip().lower() != "y":
            json.dump(plan, open(plan_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            sys.exit(f"중단. plan은 {plan_path}에 저장했으니 수정 후 --plan 으로 다시 실행하세요.")
    else:
        print("\n=== 2/4 plan: 제공된 파일 사용")
        plan = json.load(open(a.plan, encoding="utf-8"))
    json.dump(plan, open(plan_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    T["plan"] = round(time.time() - t, 1)

    print("\n=== 3/4 preprocess")
    t = time.time()
    import preprocess_v2
    m = preprocess_v2.run(a.raw, plan, stats, d3)
    T["preprocess"] = round(time.time() - t, 1)

    print("\n=== 4/4 render")
    t = time.time()
    import render_v2
    render_v2.run(os.path.join(d3, "hits.csv"), plan, d4, all_previews=True)
    T["render"] = round(time.time() - t, 1)

    usage = None
    try:
        from llm_client import usage_summary; usage = usage_summary(quiet=True)
    except Exception:
        pass
    summary = {"raw": os.path.abspath(a.raw), "out": out, "plan_name": plan["name"], "unit": plan["unit"],
               "questions": [{k: q.get(k) for k in ("id", "widget", "per")} for q in plan["questions"]],
               "n_hits": m["n_hits"], "n_units": m["n_units"], "n_attention": m["n_attention"], "excluded": m["excluded"],
               "timing_s": T, "llm_usage_total": usage,
               "mturk_upload": {"template": os.path.join(d4, "template.html"), "input_csv": os.path.join(d3, "hits.csv")},
               "preview": os.path.join(d4, "preview.html")}
    json.dump(summary, open(os.path.join(out, "pipeline_summary.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\n=== 완료  plan={plan['name']} hits={m['n_hits']} units={m['n_units']} (attention {m['n_attention']})")
    print(f"미리보기 : {summary['preview']}\nMTurk    : {summary['mturk_upload']['template']}  +  {summary['mturk_upload']['input_csv']}")
    if usage:
        print(f"LLM 누적 : ${usage['cost_usd']:.4f} / {usage['calls']} calls")
    if a.open:
        webbrowser.open("file://" + summary["preview"])


if __name__ == "__main__":
    main()
