#!/usr/bin/env python3
"""
analyze.py — raw RAG-evaluation JSON을 받아 annotation 설계용 리포트를 만든다.

    python analyze.py raw.json --out out_dir [--top-k 10] [--max-items N]

출력
    out_dir/report.md   사람이 읽는 리포트
    out_dir/stats.json  preprocess 단계가 읽는 기계용 통계

설계 원칙
    1. 스키마 인벤토리 / 축(axis) 인식 / 크기 분포는 어떤 JSON에도 동작한다 (generic 층).
    2. 라벨 분포, gt 포함률, 이상치 같은 분석은 해당 필드가 있을 때만 실행한다 (optional 층).
       필드가 없으면 그 섹션은 "skipped (no field X)"로 남기고 절대 죽지 않는다.
"""
import argparse, json, re, statistics as st, sys
from collections import Counter, defaultdict

# ---------- 축(axis) 인식 규칙 ----------
# "Chunk 3", "Atomic fact12", "Core subquery1" 같은 열거형 키 → 하나의 축으로 접는다.
ENUM_KEY_RE = re.compile(r"^(?P<name>[A-Za-z][A-Za-z _-]*?)\s*(?P<idx>\d+)$")
# 범주형 축(retriever/model/judge 이름)으로 볼 최대 distinct 키 수
CATEGORICAL_MAX_KEYS = 40


ENUM_NAMES = set()  # 1차 패스에서 학습: "Chunk", "Atomic fact", "Core subquery" ...


def learn_enum_names(items, min_distinct_idx=2):
    """말뭉치 전체에서 '<이름> <번호>' 키를 모아, 번호가 1부터 시작하고 distinct 번호가
    충분히 많은 이름만 열거형 축으로 인정한다. (BM25, GPT-5 같은 고유명사는 탈락)"""
    seen = defaultdict(set)

    def rec(node):
        if isinstance(node, dict):
            for k, v in node.items():
                m = ENUM_KEY_RE.match(str(k))
                if m:
                    seen[m.group("name").strip()].add(int(m.group("idx")))
                rec(v)
        elif isinstance(node, list):
            for v in node[:50]:
                rec(v)
    for it in items:
        rec(it)
    ENUM_NAMES.clear()
    ENUM_NAMES.update(n for n, idxs in seen.items() if min(idxs) == 1 and len(idxs) >= min_distinct_idx)
    return sorted(ENUM_NAMES)


def enum_name(key):
    m = ENUM_KEY_RE.match(str(key))
    if not m:
        return None
    nm = m.group("name").strip()
    return nm if nm in ENUM_NAMES else None


def describe(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return {}
    d = {"n": len(vals), "min": min(vals), "max": max(vals),
         "mean": round(st.mean(vals), 2), "median": st.median(vals)}
    hist = Counter(vals)
    d["hist_top"] = dict(sorted(hist.items(), key=lambda kv: -kv[1])[:12])
    return d


# ---------- 1. generic 스키마 워커 ----------
class SchemaWalker:
    """모든 item을 훑어 경로별 타입/출현수/크기/문자열길이/열거키 패턴을 모은다."""

    def __init__(self):
        self.presence = Counter()             # path -> item 수
        self.types = defaultdict(Counter)     # path -> {type: count}
        self.sizes = defaultdict(list)        # path(list or enum dict) -> per-item len
        self.strlen = defaultdict(list)       # path -> string lengths (sampled)
        self.dict_keys = defaultdict(Counter)  # path -> literal key vocab (범주형 축 후보)
        self.enum_axes = defaultdict(Counter)  # path -> {enum name: count}
        self.leaf_values = defaultdict(Counter)  # path -> small-vocab leaf values (라벨 후보)

    def walk_item(self, item):
        self._seen = set()
        self._walk(item, "$")
        for p in self._seen:
            self.presence[p] += 1

    def _walk(self, node, path):
        self._seen.add(path)
        t = type(node).__name__
        self.types[path][t] += 1
        if isinstance(node, dict):
            names = {enum_name(k) for k in node}
            names.discard(None)
            if node and len(names) == 1 and all(enum_name(k) for k in node):
                # 열거형 dict: "Chunk N" 축
                nm = names.pop()
                self.enum_axes[path][nm] += 1
                self.sizes[path + f"/<{nm} N>"].append(len(node))
                for v in node.values():
                    self._walk(v, path + f"/<{nm} N>")
            else:
                for k, v in node.items():
                    self.dict_keys[path][str(k)] += 1
                    self._walk(v, path + "/" + str(k))
        elif isinstance(node, list):
            self.sizes[path + "[]"].append(len(node))
            for v in node[:50]:  # 스키마 파악엔 앞 50개면 충분
                self._walk(v, path + "[]")
        elif isinstance(node, str):
            if len(self.strlen[path]) < 5000:
                self.strlen[path].append(len(node))
            if len(node) <= 40:
                self.leaf_values[path][node] += 1
        else:
            self.leaf_values[path][repr(node)] += 1

    def categorical_axes(self, n_items):
        """키 vocab이 작고 item마다 반복되는 dict → retriever/model/judge 같은 범주형 축."""
        out = {}
        for path, vocab in self.dict_keys.items():
            if 1 <= len(vocab) <= CATEGORICAL_MAX_KEYS and self.presence[path] >= max(2, 0.05 * n_items):
                # 최상위 item 자체($)는 필드 목록이지 축이 아니므로 제외
                if path == "$":
                    continue
                # 대부분의 키가 여러 item에 걸쳐 반복되면 축으로 본다
                repeated = sum(1 for k, c in vocab.items() if c >= max(2, 0.05 * n_items))
                if repeated / len(vocab) >= 0.5:
                    out[path] = dict(vocab)
        return out

    def label_candidates(self):
        """distinct 값이 적은 문자열 leaf → 라벨(Covered/Not covered 등) 후보."""
        out = {}
        for path, vocab in self.leaf_values.items():
            total = sum(vocab.values())
            if 2 <= len(vocab) <= 8 and total >= 20:
                out[path] = dict(vocab)
        return out


# ---------- 2. optional 분석 (필드가 있을 때만) ----------
def get(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def analyze_relevance_checks(items, top_k):
    """relevance_check[retriever][judge][task] 구조를 가정하되, 없으면 None."""
    if not any("relevance_check" in it for it in items):
        return None
    res = {}
    for it in items:
        rc = it.get("relevance_check") or {}
        for retriever, judges in rc.items():
            if not isinstance(judges, dict):
                continue
            for judge, tasks in judges.items():
                if not isinstance(tasks, dict):
                    continue
                key = f"{retriever}/{judge}"
                r = res.setdefault(key, {
                    "n_items": 0,
                    "query_fact_coverage": Counter(),
                    "query_fact_relevance_frac_selected": [],
                    "chunk_fact_relevance_n_chunks_with_support": [],
                    "chunk_fact_relevance_max_chunk_idx": 0,
                    "query_chunk_coverage_n_chunks_covering": [],
                })
                r["n_items"] += 1
                for v in (tasks.get("query_fact_coverage") or {}).values():
                    r["query_fact_coverage"][str(v)] += 1
                # fact 총수: atomic_facts[retriever][judge]가 있으면 그걸 분모로
                facts = get(it, "atomic_facts", retriever, judge) or {}
                nf = len(facts)
                qfr = tasks.get("query_fact_relevance") or {}
                if nf and qfr:
                    sel = set()
                    for v in qfr.values():
                        sel |= set((v or {}).get("selected_facts") or [])
                    r["query_fact_relevance_frac_selected"].append(round(len(sel) / nf, 3))
                cfr = tasks.get("chunk_fact_relevance") or {}
                r["chunk_fact_relevance_n_chunks_with_support"].append(len(cfr))
                for ck in cfr:
                    m = ENUM_KEY_RE.match(ck)
                    if m:
                        r["chunk_fact_relevance_max_chunk_idx"] = max(r["chunk_fact_relevance_max_chunk_idx"], int(m.group("idx")))
                qcc = tasks.get("query_chunk_coverage") or {}
                r["query_chunk_coverage_n_chunks_covering"].append(len(qcc))
    # 요약
    for key, r in res.items():
        r["query_fact_coverage"] = dict(r["query_fact_coverage"])
        fr = r.pop("query_fact_relevance_frac_selected")
        r["query_fact_relevance"] = {
            "n": len(fr), "mean_frac_selected": round(st.mean(fr), 3) if fr else None,
            "items_all_selected": sum(f == 1.0 for f in fr),
            "items_under_half_selected": sum(f < 0.5 for f in fr),
        }
        r["chunk_fact_relevance"] = {
            "judged_chunk_range": f"Chunk 1..{r.pop('chunk_fact_relevance_max_chunk_idx')}",
            "n_chunks_with_support": describe(r.pop("chunk_fact_relevance_n_chunks_with_support")),
        }
        r["query_chunk_coverage"] = {"n_chunks_covering": describe(r.pop("query_chunk_coverage_n_chunks_covering"))}
    return res


def analyze_gt_in_topk(items, top_k):
    if not any("gt_chunk" in it and "retrieved_chunk" in it for it in items):
        return None
    out = {}
    for it in items:
        gts = it.get("gt_chunk") or []
        rc = it.get("retrieved_chunk") or {}
        if not isinstance(rc, dict):
            rc = {"_": rc}
        for retriever, chunks in rc.items():
            if not isinstance(chunks, list):
                continue
            o = out.setdefault(retriever, {"n": 0, f"gt_in_top{top_k}": 0, "gt_in_full_list": 0})
            o["n"] += 1
            if any(g in chunks[:top_k] for g in gts):
                o[f"gt_in_top{top_k}"] += 1
            if any(g in chunks for g in gts):
                o["gt_in_full_list"] += 1
    return out or None


def find_anomalies(items, walker, id_field):
    """(a) 타입이 다수와 다른 item, (b) 축 크기가 극단적인 item을 플래그."""
    flags = []
    # (a) 타입 불일치: 최상위 필드 기준 (예: decomposed_query가 dict여야 하는데 str)
    for field, tc in walker.types.items():
        if not field.startswith("$/") or field.count("/") != 1 or len(tc) < 2:
            continue
        major = tc.most_common(1)[0][0]
        key = field[2:]
        for it in items:
            if key in it and type(it[key]).__name__ != major:
                flags.append({"id": it.get(id_field), "path": field, "kind": "type",
                              "detail": f"{type(it[key]).__name__} (expected {major})"})
    # (b) 크기 극단치
    for path, sizes in walker.sizes.items():
        if len(sizes) != len(items):
            continue
        med = st.median(sizes) or 1
        for it, n in zip(items, sizes):
            if n >= 50 or n > 10 * med and n >= 8:
                flags.append({"id": it.get(id_field), "path": path, "kind": "size",
                              "detail": f"{n} (median {med})"})
    return flags


# ---------- 3. 리포트 ----------
def md_table(rows, headers):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def build_report(stats, src):
    L = [f"# Analyze report — `{src}`", "",
         f"items: **{stats['n_items']}**  ·  id field: `{stats['id_field']}`  ·  top-k used: {stats['top_k']}", ""]

    L += ["## 1. 스키마 인벤토리 (generic)", "", "### 1a. 최상위 필드", ""]
    L.append(md_table([(k, v["present_in_items"], "/".join(v["types"])) for k, v in stats["top_level_fields"].items()],
                      ["field", "present in items", "type"]))
    L += ["", "### 1b. 범주형 축 (retriever / model / judge 등)", "",
          "키 vocab이 작고 item마다 반복되는 dict. preprocess spec에서 선택 가능한 값이 된다.", ""]
    for path, vocab in stats["categorical_axes"].items():
        L.append(f"- `{path}` → " + ", ".join(f"{k} ({c})" for k, c in vocab.items()))
    L += ["", f"### 1c. 열거형 축 — 학습된 이름: {stats['enum_names_learned']}", ""]
    for path, names in stats["enum_axes"].items():
        L.append(f"- `{path}` → " + ", ".join(f"<{n} N> ({c} items)" for n, c in names.items()))

    L += ["", "## 2. 크기 분포 — HIT 크기 결정용", "",
          "item당 개수. `hist_top`은 (값: item 수).", ""]
    rows = []; const = []
    for path, d in stats["size_distributions"].items():
        if d["min"] == d["max"]:
            const.append(f"`{path}`={d['min']}"); continue
        rows.append((f"`{path}`", d["n"], d["min"], d["median"], d["mean"], d["max"],
                     ", ".join(f"{k}:{v}" for k, v in list(d["hist_top"].items())[:6])))
    L.append(md_table(rows, ["path", "n", "min", "median", "mean", "max", "hist_top"]))
    if const:
        L += ["", "항상 일정한 크기: " + ", ".join(const)]
    L += ["", "### 2b. 텍스트 길이 (문자 수) — 카드 UI 스크롤/폭 결정용", ""]
    rows = [(f"`{p}`", d["n"], d["min"], d["median"], d["mean"], d["max"]) for p, d in stats["text_lengths"].items()]
    L.append(md_table(rows, ["path", "n", "min", "median", "mean", "max"]))

    L += ["", "## 3. 라벨 분포 (optional)", ""]
    if stats["relevance_checks"] is None:
        L.append("_skipped (no `relevance_check` field)_")
    else:
        for key, r in stats["relevance_checks"].items():
            L += [f"### `{key}` ({r['n_items']} items)", "",
                  f"- query_fact_coverage: {r['query_fact_coverage']}",
                  f"- query_fact_relevance: 평균 선택 비율 {r['query_fact_relevance']['mean_frac_selected']}, "
                  f"전부 선택된 item {r['query_fact_relevance']['items_all_selected']}, 절반 미만 선택 {r['query_fact_relevance']['items_under_half_selected']}",
                  f"- chunk_fact_relevance: 판정 범위 {r['chunk_fact_relevance']['judged_chunk_range']}, "
                  f"지지 chunk 수 분포 {r['chunk_fact_relevance']['n_chunks_with_support'].get('hist_top')}",
                  f"- query_chunk_coverage: subquery를 커버하는 chunk 수 분포 {r['query_chunk_coverage']['n_chunks_covering'].get('hist_top')}", ""]
    L += ["### 3b. 라벨 후보 leaf (distinct 값 2~8개)", ""]
    for p, v in stats["label_candidates"].items():
        L.append(f"- `{p}` → {v}")
    L += ["", "### 3c. gt_chunk 포함률", ""]
    if stats["gt_in_topk"] is None:
        L.append("_skipped (no `gt_chunk`/`retrieved_chunk`)_")
    else:
        for r, o in stats["gt_in_topk"].items():
            L.append(f"- {r}: " + ", ".join(f"{k}={v}" for k, v in o.items()))

    L += ["", "## 4. 이상치 (제외/분할 후보)", ""]
    if not stats["anomalies"]:
        L.append("없음")
    else:
        L.append(md_table([(a["id"], a["kind"], f"`{a['path']}`", a["detail"]) for a in stats["anomalies"]],
                          ["id", "kind", "path", "detail"]))
    L += ["", "## 5. 설계 힌트 (자동 생성)", ""]
    L += [f"- {h}" for h in stats["hints"]]
    return "\n".join(L) + "\n"


def make_hints(stats):
    h = []
    for path, d in stats["size_distributions"].items():
        if "Atomic fact" in path and d["max"] > 8:
            h.append(f"`{path}` 최대 {d['max']}개 — fact 체크박스가 길어지므로 item당 fact 상한(예: 8) 또는 HIT 분할 필요")
        if "Core subquery" in path and d["max"] > 5:
            h.append(f"`{path}` 최대 {d['max']}개 — decomposition 실패 의심 item 존재, 이상치 표 확인")
    rc = stats["relevance_checks"] or {}
    for key, r in rc.items():
        qf = r["query_fact_relevance"]
        if qf["n"] and qf["items_all_selected"] / qf["n"] > 0.7:
            h.append(f"{key}: query_fact_relevance가 {qf['items_all_selected']}/{qf['n']} item에서 '전부 관련' — "
                     f"정보량 낮음. 절반 미만 선택된 {qf['items_under_half_selected']}개 item 우선 샘플링 권장")
        rng = r["chunk_fact_relevance"]["judged_chunk_range"]
        h.append(f"{key}: LLM 판정은 {rng} 범위만 존재 — 사람 annotation도 같은 top-k로 맞추는 게 비교 가능")
        z = r["chunk_fact_relevance"]["n_chunks_with_support"].get("hist_top", {}).get(0, 0)
        if z:
            h.append(f"{key}: top-k 안에 지지 chunk가 0개인 item {z}개 — groundedness task에서 negative-only item이 되므로 positive/negative 균형 샘플링 필요")
    gt = stats["gt_in_topk"] or {}
    for r, o in gt.items():
        k = [k for k in o if k.startswith("gt_in_top")][0]
        h.append(f"{r}: gt_chunk가 {k}에 포함된 item {o[k]}/{o['n']} — gt를 강제 포함할지 spec에서 결정 필요")
    nt = sum(a["kind"] == "type" for a in stats["anomalies"])
    if nt:
        h.append(f"타입 불일치 item {nt}건 (파싱 실패 흔적) — preprocess에서 반드시 exclude")
    if stats["anomalies"]:
        h.append(f"이상치 총 {len(stats['anomalies'])}건 — stats.json의 anomalies를 preprocess exclude 목록으로 넘김")
    return h


# ---------- main ----------
def load_items(path):
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, dict):
        # {id: item} 형태면 값들을 item으로, id는 _id로 보존
        items = []
        for k, v in data.items():
            if isinstance(v, dict):
                v = dict(v); v.setdefault("_id", k)
            items.append(v)
        return items
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--out", default="analyze_out")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--max-items", type=int, default=None)
    a = ap.parse_args()

    items = load_items(a.raw)
    if a.max_items:
        items = items[: a.max_items]
    if not items or not isinstance(items[0], dict):
        sys.exit("raw JSON은 dict 리스트(또는 {id: dict})여야 합니다.")

    id_field = next((f for f in ("qid", "id", "_id", "query_id") if f in items[0]), None)

    enum_names = learn_enum_names(items)
    w = SchemaWalker()
    for it in items:
        w.walk_item(it)

    top = {k: {"present_in_items": w.presence["$/" + k], "types": sorted(w.types["$/" + k])}
           for k in w.dict_keys["$"]}
    size_dists = {p: describe(v) for p, v in w.sizes.items() if len(v) >= 0.05 * len(items)}
    text_lengths = {p: describe(v) for p, v in w.strlen.items() if len(v) >= 20 and st.median(v) >= 30}

    stats = {
        "source": a.raw, "n_items": len(items), "id_field": id_field, "top_k": a.top_k,
        "top_level_fields": top,
        "enum_names_learned": enum_names,
        "categorical_axes": w.categorical_axes(len(items)),
        "enum_axes": {p: dict(c) for p, c in w.enum_axes.items()},
        "size_distributions": size_dists,
        "text_lengths": text_lengths,
        "label_candidates": w.label_candidates(),
        "relevance_checks": analyze_relevance_checks(items, a.top_k),
        "gt_in_topk": analyze_gt_in_topk(items, a.top_k),
        "anomalies": find_anomalies(items, w, id_field),
    }
    stats["hints"] = make_hints(stats)

    import os
    os.makedirs(a.out, exist_ok=True)
    json.dump(stats, open(os.path.join(a.out, "stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
    open(os.path.join(a.out, "report.md"), "w", encoding="utf-8").write(build_report(stats, os.path.basename(a.raw)))
    print(f"wrote {a.out}/report.md, {a.out}/stats.json  ({len(items)} items)")


if __name__ == "__main__":
    main()
