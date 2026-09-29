"""
jsonpath.py — plan이 데이터 위치를 가리킬 때 쓰는 아주 작은 경로 문법.

    query                          → item["query"]
    retrieved_chunk.BM25           → item["retrieved_chunk"]["BM25"]      (리스트 그대로)
    retrieved_chunk.BM25[]         → 그 리스트의 원소들 (반복)
    retrieved_chunk.BM25[:10]      → 앞 10개
    retrieved_chunk.BM25[2]        → 3번째 원소
    decomposed_query{}             → {"Core subquery1":..,"Core subquery2":..} 를 번호순 리스트로
    atomic_facts.BM25.GPT-5{}      → 위와 같음 (키에 '-'나 공백 있어도 됨; '.'만 구분자)
    passages[].text                → 리스트 각 원소의 text (반복 후 계속 내려감, 결과는 평평한 리스트)

resolve(item, path) → 값 (반복이 있으면 list, 없으면 스칼라/컨테이너). 없는 경로는 None.
"""
import re

SEG = re.compile(r"^(?P<name>[^\[\]{}]+)?(?P<op>\[\]|\[:\d+\]|\[\d+\]|\{\})?$")
ENUM_NUM = re.compile(r"(\d+)$")


def enum_sorted(d):
    """{'Chunk 1':..,'Chunk 10':..,'Chunk 2':..} → 번호순 값 리스트."""
    def key(k):
        m = ENUM_NUM.search(str(k))
        return int(m.group(1)) if m else 10**9
    return [d[k] for k in sorted(d, key=key)]


def normalize(path):
    """'$/a/b/<Chunk N>' → 'a.b{}',  'a.b/c' → 'a.b.c'.  analyze 리포트 표기와 LLM의 슬래시 실수를 흡수."""
    p = str(path).strip()
    if p.startswith("$/"):
        p = p[2:]
    elif p == "$":
        return ""
    p = re.sub(r"/<[^>]+ N>", "{}", p)          # /<Chunk N> → {}
    p = re.sub(r"\.<[^>]+ N>", "{}", p)
    p = p.replace("/", ".")
    p = re.sub(r"\.\[", "[", p).replace(".{}", "{}")   # 'a.[]' → 'a[]'
    return p


def parse(path):
    path = normalize(path)
    segs = []
    for raw in path.split("."):
        m = SEG.match(raw)
        if not m:
            raise ValueError(f"bad path segment {raw!r} in {path!r}")
        segs.append((m.group("name"), m.group("op")))
    return segs


def _apply(node, name, op):
    if name is not None:
        if not isinstance(node, dict) or name not in node:
            return None, False
        node = node[name]
    if op is None:
        return node, False
    if op == "{}":
        if not isinstance(node, dict):
            return None, False
        return enum_sorted(node), True
    if op == "[]":
        return (list(node) if isinstance(node, list) else None), True
    if op.startswith("[:"):
        k = int(op[2:-1])
        return (list(node[:k]) if isinstance(node, list) else None), True
    i = int(op[1:-1])
    return ((node[i] if isinstance(node, list) and i < len(node) else None), False)


def resolve(item, path):
    """반복(op)이 하나라도 있으면 list를, 없으면 그 값을 돌려준다. 못 찾으면 None."""
    nodes, iterated = [item], False
    for name, op in parse(path):
        nxt = []
        for n in nodes:
            v, it = _apply(n, name, op)
            if v is None:
                continue
            if it:
                iterated = True
                nxt.extend(v)
            else:
                nxt.append(v)
        nodes = nxt
        if not nodes:
            return [] if iterated else None
    return nodes if iterated else (nodes[0] if nodes else None)


def is_list_path(path):
    return any(op in ("[]", "{}") or (op or "").startswith("[:") for _, op in parse(path))
