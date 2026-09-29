"""
llm_client.py — OpenRouter 호출 + 사용량/비용 기록.

    from llm_client import chat, usage_summary
    text, usage = chat([{"role":"user","content":"..."}], purpose="spec_from_prompt")

- API 키: 환경변수 OPENROUTER_API_KEY, 없으면 이 폴더의 .env 파일에서 읽는다 (.env는 .gitignore에 포함)
      .env 내용 예:  OPENROUTER_API_KEY=sk-or-v1-...
- 모든 호출은 llm_usage.jsonl 에 한 줄씩 기록: 시각, 모델, 목적, 토큰 수, 비용(USD)
- 비용은 OpenRouter가 응답에 넣어주는 usage.cost 를 그대로 기록 (요청에 usage.include=true 필요)
- `python llm_client.py` 로 누적 사용량 요약 출력
"""
import json, os, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv():
    """이 폴더의 .env 를 읽어 없는 환경변수만 채운다. (KEY=VALUE 한 줄씩, # 주석 허용)"""
    p = os.path.join(HERE, ".env")
    if not os.path.exists(p):
        return
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv()
DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "qwen/qwen3.8-flash")
USAGE_LOG = os.environ.get("LLM_USAGE_LOG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_usage.jsonl"))
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


def chat(messages, model=None, purpose="", temperature=0.0, max_tokens=2048, json_mode=False, timeout=180, reasoning=False):
    """reasoning=False: thinking 모델(qwen3.x 등)의 사고 과정을 끈다 — 켜두면 max_tokens를 사고에 다 써서 본문이 비어 올 수 있음."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError(f"OPENROUTER_API_KEY가 없습니다. {HERE}\\.env 파일에 'OPENROUTER_API_KEY=키' 한 줄을 넣어주세요.")
    model = model or DEFAULT_MODEL
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens,
            "usage": {"include": True}}
    if not reasoning:
        body["reasoning"] = {"enabled": False}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"), method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/annotation-template-generator", "X-Title": "annotation-template-generator"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenRouter HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")
    choice = resp["choices"][0]
    text = choice["message"].get("content")
    finish = choice.get("finish_reason")
    u = resp.get("usage") or {}
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": resp.get("model", model), "purpose": purpose,
           "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
           "total_tokens": u.get("total_tokens"), "cost_usd": u.get("cost"), "latency_s": round(time.time() - t0, 2),
           "finish_reason": finish, "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
           "id": resp.get("id")}
    with open(USAGE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tot = usage_summary(quiet=True)
    print(f"[llm] {rec['model']} {purpose}: {rec['prompt_tokens']}+{rec['completion_tokens']} tok, "
          f"${(rec['cost_usd'] or 0):.5f}  |  누적 ${tot['cost_usd']:.4f} / {tot['calls']} calls"
          + (f"  [finish={finish}]" if finish and finish != "stop" else ""), file=sys.stderr)
    if not text:
        raise RuntimeError(f"LLM 응답 본문이 비어 있음 (finish_reason={finish}, reasoning_tokens={rec['reasoning_tokens']}). "
                           f"max_tokens({max_tokens})를 늘리거나 reasoning을 끈 상태인지 확인.")
    if finish == "length":
        raise RuntimeError(f"LLM 응답이 max_tokens({max_tokens})에서 잘림 — 상한을 늘려야 함.")
    return text, rec


def usage_summary(quiet=False):
    calls, cost, ptok, ctok, by_purpose = 0, 0.0, 0, 0, {}
    if os.path.exists(USAGE_LOG):
        for line in open(USAGE_LOG, encoding="utf-8"):
            r = json.loads(line)
            calls += 1; cost += r.get("cost_usd") or 0
            ptok += r.get("prompt_tokens") or 0; ctok += r.get("completion_tokens") or 0
            bp = by_purpose.setdefault(r.get("purpose") or "-", {"calls": 0, "cost_usd": 0.0})
            bp["calls"] += 1; bp["cost_usd"] += r.get("cost_usd") or 0
    s = {"calls": calls, "cost_usd": round(cost, 6), "prompt_tokens": ptok, "completion_tokens": ctok, "by_purpose": by_purpose}
    if not quiet:
        print(json.dumps(s, indent=2, ensure_ascii=False))
    return s


if __name__ == "__main__":
    usage_summary()
