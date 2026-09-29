#!/usr/bin/env python3
"""
preprocess_v2.py — raw JSON + plan.json → HIT 데이터 (plan에 적힌 경로/단위/attention 규칙을 실행)

    python preprocess_v2.py raw.json --plan plans/pairwise_passages.json [--stats runs/x/1_analyze/stats.json] --out prep_out

출력: hits.csv (MTurk, 1행=1HIT, 셀=JSON 리스트), units.jsonl, manifest.json
각 annotation 항목(unit)은
    roles : plan.roles 를 이 item에서 해석한 값들 {"question": "...", "facts": [...], ...}   (attention이면 일부가 바뀜)
    unit  : 단위 payload — single {"value": x} / pair {"a": x, "b": y} / item {}
    unit_meta : 원본 인덱스 등 (template에는 넣지 않음)
"""
import argparse, csv, json, os, random, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jsonpath import resolve, enum_sorted, ENUM_NUM
from plan import load_plan, validate_plan


# ---------------------------------------------------------------- gold (기존 LLM 라벨) 해석
def _enum_idx(s):
    m = ENUM_NUM.search(str(s))
    return int(m.group(1)) - 1 if m else None


def _lookup(container, idx):
    """컨테이너에서 0-based idx에 해당하는 원소: list면 [idx], dict면 끝번호==idx+1 인 키."""
    if isinstance(container, list):
        return container[idx] if idx < len(container) else None
    if isinstance(container, dict):
        for k, v in container.items():
            if _enum_idx(k) == idx:
                return v
    return None


def _as_value(v, mode):
    if mode != "enum_index":
        return v
    if isinstance(v, list):
        return sorted(i for i in (_enum_idx(x) for x in v) if i is not None)
    if isinstance(v, str):
        return _enum_idx(v)
    return v


def gold_for(item, q, unit_index=None, rep_count=None):
    """질문 q의 gold를 이 item/unit에 대해 계산. per=unit → 값 1개, per=role → 반복 수만큼 리스트."""
    g = q.get("gold")
    if not g or not g.get("path"):
        return None
    base = resolve(item, g["path"])
    if base is None:
        return None
    mode = g.get("value", "raw")

    def finish(v):
        if v is None:
            return [] if q.get("widget") == "multi_select" else None
        if g.get("field") and isinstance(v, dict):
            v = v.get(g["field"])
        v = _as_value(v, mode)
        # 다중선택 답은 인덱스 리스트이므로, LLM이 value="raw"로 적었어도 "Atomic fact3" 같은 열거 키는 인덱스로 맞춘다
        if q.get("widget") == "multi_select" and isinstance(v, list) and v and all(isinstance(x, str) for x in v):
            conv = [_enum_idx(x) for x in v]
            if all(c is not None for c in conv):
                v = sorted(conv)
        if q.get("widget") == "multi_select" and isinstance(v, (str, int)):
            v = [v] if isinstance(v, int) else ([_enum_idx(v)] if _enum_idx(v) is not None else [v])
        return v

    lk = g.get("lookup")
    if lk == "unit":
        return finish(_lookup(base, unit_index))
    if lk == "rep":
        return [finish(_lookup(base, r)) for r in range(rep_count or 0)]
    return finish(base)


def resolve_roles(item, plan):
    return {r: resolve(item, spec["path"]) for r, spec in plan["roles"].items()}


def select_items(items, plan, stats):
    f = plan.get("filters") or {}
    excl = Counter()
    exclude_ids = set()
    if f.get("exclude_ids") == "auto" and stats:
        exclude_ids = {a["id"] for a in stats.get("anomalies", [])}
    elif isinstance(f.get("exclude_ids"), list):
        exclude_ids = set(f["exclude_ids"])
    used_roles = _used_roles(plan)
    out = []
    for it in items:
        sid = resolve(it, plan.get("id_path") or "id")
        if sid in exclude_ids:
            excl["exclude_ids/anomaly"] += 1; continue
        if f.get("id_prefix") and not any(str(sid).startswith(p) for p in f["id_prefix"]):
            excl["id_prefix"] += 1; continue
        roles = resolve_roles(it, plan)
        bad = next((r for r in used_roles if roles.get(r) in (None, [], "")), None)
        if bad:
            excl[f"missing_role:{bad}"] += 1; continue
        too_big = next((r for r, k in (f.get("max_role_size") or {}).items()
                        if isinstance(roles.get(r), list) and len(roles[r]) > k), None)
        if too_big:
            excl[f"too_many:{too_big}"] += 1; continue
        out.append({"id": sid, "roles": roles, "item": it})
    return out, excl


def _used_roles(plan):
    used = set(c["role"] for c in plan["display"].get("context", []))
    for slot in ("left", "right"):
        s = (plan["display"].get(slot) or {}).get("source", "")
        if s.startswith("role:"):
            used.add(s[5:])
    if plan["unit"]["type"] != "item":
        used.add(plan["unit"]["of"])
    for q in plan["questions"]:
        for k in ("per", "options_from"):
            if str(q.get(k, "")).startswith("role:"):
                used.add(q[k][5:])
    att = plan.get("attention") or {}
    for v in list((att.get("set") or {}).values()) + [att.get("swap", "")]:
        if str(v).startswith("role:"):
            used.add(v[5:])
    return used


def unit_gold(src, plan, unit_index):
    out = {}
    for q in plan["questions"]:
        if not q.get("gold"):
            continue
        per = q.get("per", "unit")
        rep = len(src["roles"].get(per[5:]) or []) if per.startswith("role:") else None
        out[q["id"]] = gold_for(src["item"], q, unit_index, rep)
    return out or None


def make_units(src, plan, rng):
    """한 item → unit 리스트 (gold 포함)."""
    u = plan["unit"]
    if u["type"] == "item":
        return [{"unit": {}, "unit_meta": {}, "gold": unit_gold(src, plan, None)}]
    seq = src["roles"][u["of"]]
    if u["type"] == "single":
        return [{"unit": {"value": v}, "unit_meta": {"index": i}, "gold": unit_gold(src, plan, i)} for i, v in enumerate(seq)]
    idx = list(range(len(seq)))
    if u.get("pairing", "adjacent") == "random":
        rng.shuffle(idx)
    pairs = [(idx[i], idx[i + 1]) for i in range(0, len(idx) - 1, 2)]
    return [{"unit": {"a": seq[a], "b": seq[b]}, "unit_meta": {"a_index": a, "b_index": b}, "gold": None} for a, b in pairs]


def make_attention(host_src, host_unit, others, plan, rng):
    """mismatch: host 항목을 복사한 뒤, plan.attention.set 을 적용하고 swap 대상을 남의 item 것으로 바꾼다."""
    att = plan["attention"]
    pref = lambda s: str(s).split("_")[0]
    cands = [o for o in others if pref(o["id"]) != pref(host_src["id"])] or others
    other = rng.choice(cands)
    roles = json.loads(json.dumps(host_src["roles"]))
    unit = json.loads(json.dumps(host_unit["unit"]))
    note = []

    def pick(src_roles, ref):
        r = ref[5:]
        v = src_roles.get(r)
        return rng.choice(v) if isinstance(v, list) and v else v

    for target, ref in (att.get("set") or {}).items():
        val = pick(roles, ref)
        if target == "unit":
            unit["value"] = val
        elif target in ("unit.a", "unit.b"):
            unit[target[-1]] = val
        else:
            roles[target[5:]] = val
        note.append(f"{target}<-{ref}")
    sw = att["swap"]
    if sw == "unit":
        unit["value"] = pick(other["roles"], "role:" + plan["unit"]["of"])
    elif sw in ("unit.a", "unit.b"):
        unit[sw[-1]] = pick(other["roles"], "role:" + plan["unit"]["of"])
    else:
        roles[sw[5:]] = other["roles"][sw[5:]]
    note.append(f"{sw}<-{other['id']}")
    return {"roles": roles, "unit": unit, "unit_meta": {"attention": True}, "src_id": "attention", "gold": None,
            "is_attention": 1, "attention_note": "; ".join(note), "expected": att.get("expected") or {}}


def balance(chosen, plan, rng):
    """gold가 있는 첫 질문 기준: item 안에 positive gold(비어있지 않은 값)가 하나라도 있으면 positive.
    positive ≈70% / negative 30% 순서로 앞에 배치 (n_hits로 잘리기 전에)."""
    gq = next((q for q in plan["questions"] if q.get("gold")), None)
    if not gq:
        return chosen
    def positive(src):
        for u in make_units(src, plan, random.Random(0)):
            g = (u.get("gold") or {}).get(gq["id"])
            vals = g if isinstance(g, list) else [g]
            if any(v not in (None, [], "", 0, "Not covered") for v in vals):
                return True
        return False
    pos = [s for s in chosen if positive(s)]; neg = [s for s in chosen if not positive(s)]
    need = (plan.get("hit") or {}).get("n_hits") or len(chosen)
    n_pos = min(len(pos), max(1, round(need * 0.7))); n_neg = min(len(neg), max(0, need - n_pos)); n_pos = min(len(pos), need - n_neg)
    out = pos[:n_pos] + neg[:n_neg]; rng.shuffle(out)
    return out + pos[n_pos:] + neg[n_neg:]


def build_hits(chosen, plan, rng):
    h = plan.get("hit") or {}
    per = h.get("items_per_hit", 10)
    n_hits = h.get("n_hits")
    groups = []  # list of list of (src, unit)
    if h.get("group_by_item", plan["unit"]["type"] != "item"):
        for src in chosen:
            us = make_units(src, plan, rng)
            for s in range(0, len(us), per):
                groups.append([(src, u) for u in us[s:s + per]])
    else:
        flat = [(src, u) for src in chosen for u in make_units(src, plan, rng)]
        rng.shuffle(flat)
        groups = [flat[s:s + per] for s in range(0, len(flat), per) if len(flat[s:s + per]) == per]
    if n_hits:
        groups = groups[:n_hits]

    att = plan.get("attention") or {"strategy": "none"}
    hits, units = [], []
    for gi, grp in enumerate(groups):
        rows = [dict(roles=src["roles"], unit=u["unit"], unit_meta=u["unit_meta"], src_id=src["id"], gold=u.get("gold"),
                     is_attention=0, attention_note=None, expected=None) for src, u in grp]
        if att.get("strategy") == "mismatch":
            host_ids = {src["id"] for src, _ in grp}
            others = [s for s in chosen if s["id"] not in host_ids] or chosen
            for _ in range(att.get("per_hit", 1)):
                src, u = grp[rng.randrange(len(grp))]
                rows.insert(rng.randrange(len(rows) + 1), make_attention(src, u, others, plan, rng))
        hid = f"{plan['name']}_{gi:04d}"
        for i, r in enumerate(rows):
            units.append(dict(hit_id=hid, item_idx=i, **r))
        hits.append((hid, rows))
    return hits, units


HIT_COLUMNS = ["hit_id", "plan_name", "n_items", "src_id", "is_attention", "roles", "unit", "unit_meta", "gold", "attention_note", "expected"]


def write_outputs(hits, units, plan, excl, out):
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "units.jsonl"), "w", encoding="utf-8") as f:
        for u in units:
            f.write(json.dumps(u, ensure_ascii=False) + "\n")
    with open(os.path.join(out, "hits.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HIT_COLUMNS)
        w.writeheader()
        for hid, rows in hits:
            rec = {"hit_id": hid, "plan_name": plan["name"], "n_items": len(rows)}
            for col in HIT_COLUMNS[3:]:
                rec[col] = json.dumps([r.get(col) for r in rows], ensure_ascii=False).replace("</", "<\\/")
            w.writerow(rec)
    m = {"plan": plan, "n_hits": len(hits), "n_units": len(units), "n_attention": sum(u["is_attention"] for u in units),
         "src_ids": sorted({u["src_id"] for u in units if u["src_id"] != "attention"}), "excluded": dict(excl), "columns": HIT_COLUMNS,
         "gold_available": any(u.get("gold") for u in units)}
    json.dump(m, open(os.path.join(out, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return m


def run(raw_path, plan, stats=None, out="prep_out"):
    data = json.load(open(raw_path, encoding="utf-8"))
    items = list(data.values()) if isinstance(data, dict) else data
    errs = validate_plan(plan, items[:20])
    if errs:
        raise SystemExit("plan 오류:\n  - " + "\n  - ".join(errs))
    rng = random.Random((plan.get("hit") or {}).get("seed", 0))
    chosen, excl = select_items(items, plan, stats)
    if not chosen:
        raise SystemExit(f"선택된 item 없음. 제외 사유: {dict(excl)}")
    rng.shuffle(chosen)
    if (plan.get("hit") or {}).get("sampling") == "balanced":
        chosen = balance(chosen, plan, rng)
    hits, units = build_hits(chosen, plan, rng)
    m = write_outputs(hits, units, plan, excl, out)
    print(f"[{plan['name']}] hits={m['n_hits']} units={m['n_units']} attention={m['n_attention']} gold={'yes' if m['gold_available'] else 'no'} excluded={m['excluded']}")
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw"); ap.add_argument("--plan", required=True); ap.add_argument("--stats"); ap.add_argument("--out", default="prep_out")
    a = ap.parse_args()
    stats = json.load(open(a.stats, encoding="utf-8")) if a.stats else None
    run(a.raw, load_plan(a.plan), stats, a.out)


if __name__ == "__main__":
    main()
