# Analyze report — `test-close_ended_queries_R3_Qwen3-80B_GPT-5_reasoning.json`

items: **400**  ·  id field: `qid`  ·  top-k used: 10

## 1. 스키마 인벤토리 (generic)

### 1a. 최상위 필드

| field | present in items | type |
|---|---|---|
| qid | 400 | str |
| query | 400 | str |
| gt_answer | 400 | list |
| gt_chunk | 400 | list |
| retrieved_chunk | 400 | dict |
| model_prediction | 400 | dict |
| decomposed_query | 400 | dict/str |
| atomic_facts | 400 | dict |
| relevance_check | 400 | dict |
| relevance_check_text | 400 | dict |
| relevance_check_reasoning | 400 | dict |

### 1b. 범주형 축 (retriever / model / judge 등)

키 vocab이 작고 item마다 반복되는 dict. preprocess spec에서 선택 가능한 값이 된다.

- `$/retrieved_chunk` → ANCE (400), BM25 (400)
- `$/model_prediction` → ANCE (400), BM25 (400)
- `$/model_prediction/ANCE` → Llama3.3_70B (400), Llama3.1_8B (400), Llama3.2_3B (400), Qwen2.5_32B (400), Qwen2.5_7B (400), Qwen2.5_3B (400), Gemma3_27B (400), Gemma3_12B (400), Gemma3_4B (400), GPT-4o (400), GPT-4o-mini (400), GPT-oss_20B (400), Claude-Sonnet (400), Gemini-2.5-pro (400), Qwen3_4B (400), Qwen3_30B (400), GPT-5 (400)
- `$/model_prediction/BM25` → Llama3.3_70B (400), Llama3.1_8B (400), Llama3.2_3B (400), Qwen2.5_32B (400), Qwen2.5_7B (400), Qwen2.5_3B (400), Gemma3_27B (400), Gemma3_12B (400), Gemma3_4B (400), GPT-4o (400), GPT-4o-mini (400), GPT-oss_20B (400), Claude-Sonnet (400), Gemini-2.5-pro (400), Qwen3_4B (400), Qwen3_30B (400), GPT-5 (400)
- `$/atomic_facts` → BM25 (400)
- `$/atomic_facts/BM25` → Gemma3_27B (400), Gemma3_4B (400), GPT-oss_20B (400), Claude-Sonnet (400), Gemini-2.5-pro (400), Qwen3_4B (400), Qwen3_30B (400), GPT-5 (400)
- `$/relevance_check` → BM25 (400)
- `$/relevance_check/BM25` → GPT-5 (400)
- `$/relevance_check/BM25/GPT-5` → query_fact_relevance (400), chunk_fact_relevance (400), query_fact_coverage (400), query_chunk_coverage (400)
- `$/relevance_check/BM25/GPT-5/query_fact_relevance/<Core subquery N>` → selected_facts (631)
- `$/relevance_check_text` → BM25 (400)
- `$/relevance_check_text/BM25` → GPT-5 (400)
- `$/relevance_check_text/BM25/GPT-5` → query_fact_relevance (400), chunk_fact_relevance (400), query_fact_coverage (400), query_chunk_coverage (400)
- `$/relevance_check_reasoning` → BM25 (400)
- `$/relevance_check_reasoning/BM25` → GPT-5 (400)
- `$/relevance_check_reasoning/BM25/GPT-5` → chunk_fact_relevance (400), query_fact_coverage (400), query_chunk_coverage (400)
- `$/relevance_check/BM25/GPT-5/chunk_fact_relevance/<Chunk N>` → selected_facts (661)

### 1c. 열거형 축 — 학습된 이름: ['Atomic fact', 'Chunk', 'Core subquery']

- `$/decomposed_query` → <Core subquery N> (399 items)
- `$/atomic_facts/BM25/Gemma3_27B` → <Atomic fact N> (400 items)
- `$/atomic_facts/BM25/Gemma3_4B` → <Atomic fact N> (400 items)
- `$/atomic_facts/BM25/GPT-oss_20B` → <Atomic fact N> (400 items)
- `$/atomic_facts/BM25/Claude-Sonnet` → <Atomic fact N> (400 items)
- `$/atomic_facts/BM25/Gemini-2.5-pro` → <Atomic fact N> (400 items)
- `$/atomic_facts/BM25/Qwen3_4B` → <Atomic fact N> (400 items)
- `$/atomic_facts/BM25/Qwen3_30B` → <Atomic fact N> (400 items)
- `$/atomic_facts/BM25/GPT-5` → <Atomic fact N> (400 items)
- `$/relevance_check/BM25/GPT-5/query_fact_relevance` → <Core subquery N> (400 items)
- `$/relevance_check/BM25/GPT-5/query_fact_coverage` → <Core subquery N> (400 items)
- `$/relevance_check/BM25/GPT-5/query_chunk_coverage` → <Chunk N> (302 items)
- `$/relevance_check_reasoning/BM25/GPT-5/chunk_fact_relevance` → <Chunk N> (400 items)
- `$/relevance_check_reasoning/BM25/GPT-5/chunk_fact_relevance/<Chunk N>` → <Atomic fact N> (4000 items)
- `$/relevance_check_reasoning/BM25/GPT-5/query_chunk_coverage` → <Chunk N> (400 items)
- `$/relevance_check_reasoning/BM25/GPT-5/query_chunk_coverage/<Chunk N>` → <Core subquery N> (4000 items)
- `$/relevance_check/BM25/GPT-5/chunk_fact_relevance` → <Chunk N> (292 items)

## 2. 크기 분포 — HIT 크기 결정용

item당 개수. `hist_top`은 (값: item 수).

| path | n | min | median | mean | max | hist_top |
|---|---|---|---|---|---|---|
| `$/gt_chunk[]` | 400 | 1 | 2.0 | 2.87 | 54 | 1:191, 2:131, 3:19, 4:10, 7:7, 8:6 |
| `$/decomposed_query/<Core subquery N>` | 399 | 1 | 1 | 1.58 | 5 | 1:239, 2:92, 3:66, 4:1, 5:1 |
| `$/atomic_facts/BM25/Gemma3_27B/<Atomic fact N>` | 400 | 1 | 1.0 | 1.43 | 9 | 1:296, 2:68, 3:20, 4:9, 5:3, 7:2 |
| `$/atomic_facts/BM25/Gemma3_4B/<Atomic fact N>` | 400 | 1 | 1.0 | 1.25 | 8 | 1:331, 2:49, 3:15, 4:4, 8:1 |
| `$/atomic_facts/BM25/GPT-oss_20B/<Atomic fact N>` | 400 | 1 | 1.0 | 1.21 | 19 | 1:362, 2:25, 4:4, 3:4, 5:3, 19:1 |
| `$/atomic_facts/BM25/Claude-Sonnet/<Atomic fact N>` | 400 | 1 | 2.0 | 2.36 | 12 | 1:156, 2:108, 3:73, 4:26, 5:12, 6:9 |
| `$/atomic_facts/BM25/Gemini-2.5-pro/<Atomic fact N>` | 400 | 1 | 1.5 | 1.99 | 14 | 1:200, 2:106, 3:58, 4:17, 5:8, 6:4 |
| `$/atomic_facts/BM25/Qwen3_4B/<Atomic fact N>` | 400 | 1 | 1.0 | 1.45 | 13 | 1:311, 2:50, 3:21, 4:7, 6:4, 5:4 |
| `$/atomic_facts/BM25/Qwen3_30B/<Atomic fact N>` | 400 | 1 | 1.0 | 1.42 | 7 | 1:308, 2:53, 3:20, 4:9, 5:5, 6:3 |
| `$/atomic_facts/BM25/GPT-5/<Atomic fact N>` | 400 | 1 | 1.0 | 1.19 | 5 | 1:350, 2:31, 3:16, 5:2, 4:1 |
| `$/relevance_check/BM25/GPT-5/query_fact_relevance/<Core subquery N>` | 400 | 1 | 1.0 | 1.58 | 5 | 1:240, 2:92, 3:66, 4:1, 5:1 |
| `$/relevance_check/BM25/GPT-5/query_fact_relevance/<Core subquery N>/selected_facts[]` | 631 | 0 | 1 | 0.65 | 3 | 1:368, 0:246, 2:12, 3:5 |
| `$/relevance_check/BM25/GPT-5/query_fact_coverage/<Core subquery N>` | 400 | 1 | 1.0 | 1.58 | 5 | 1:240, 2:92, 3:66, 4:1, 5:1 |
| `$/relevance_check/BM25/GPT-5/query_chunk_coverage/<Chunk N>` | 302 | 1 | 3.0 | 3.22 | 10 | 1:81, 2:65, 3:54, 4:29, 5:26, 6:16 |
| `$/relevance_check/BM25/GPT-5/query_chunk_coverage/<Chunk N>[]` | 972 | 1 | 1.0 | 1.17 | 4 | 1:843, 2:92, 3:36, 4:1 |
| `$/relevance_check_reasoning/BM25/GPT-5/chunk_fact_relevance/<Chunk N>/<Atomic fact N>` | 4000 | 1 | 1.0 | 1.19 | 5 | 1:3500, 2:310, 3:160, 5:20, 4:10 |
| `$/relevance_check_reasoning/BM25/GPT-5/query_chunk_coverage/<Chunk N>/<Core subquery N>` | 4000 | 1 | 1.0 | 1.58 | 5 | 1:2400, 2:920, 3:660, 4:10, 5:10 |
| `$/relevance_check/BM25/GPT-5/chunk_fact_relevance/<Chunk N>` | 292 | 1 | 2.0 | 2.26 | 10 | 1:136, 2:57, 3:51, 4:19, 5:13, 7:6 |
| `$/relevance_check/BM25/GPT-5/chunk_fact_relevance/<Chunk N>/selected_facts[]` | 661 | 1 | 1 | 1.1 | 5 | 1:610, 2:41, 3:7, 5:2, 4:1 |

항상 일정한 크기: `$/gt_answer[]`=1, `$/retrieved_chunk/ANCE[]`=30, `$/retrieved_chunk/BM25[]`=30, `$/relevance_check_reasoning/BM25/GPT-5/chunk_fact_relevance/<Chunk N>`=10, `$/relevance_check_reasoning/BM25/GPT-5/chunk_fact_relevance/<Chunk N>/<Atomic fact N>[]`=2, `$/relevance_check_reasoning/BM25/GPT-5/query_chunk_coverage/<Chunk N>`=10, `$/relevance_check_reasoning/BM25/GPT-5/query_chunk_coverage/<Chunk N>/<Core subquery N>[]`=2

### 2b. 텍스트 길이 (문자 수) — 카드 UI 스크롤/폭 결정용

| path | n | min | median | mean | max |
|---|---|---|---|---|---|
| `$/query` | 400 | 16 | 63.0 | 73.32 | 260 |
| `$/gt_chunk[]` | 1144 | 4 | 596.5 | 762.28 | 4554 |
| `$/retrieved_chunk/ANCE[]` | 5000 | 69 | 602.0 | 594.75 | 1134 |
| `$/retrieved_chunk/BM25[]` | 5000 | 87 | 600.0 | 596.85 | 2042 |
| `$/model_prediction/ANCE/Gemma3_27B` | 400 | 1 | 55.0 | 75.24 | 579 |
| `$/model_prediction/ANCE/Gemma3_12B` | 400 | 1 | 40.5 | 57.37 | 360 |
| `$/model_prediction/ANCE/Gemma3_4B` | 400 | 2 | 45.0 | 62.05 | 380 |
| `$/model_prediction/ANCE/GPT-4o` | 400 | 1 | 98.5 | 116.03 | 701 |
| `$/model_prediction/ANCE/GPT-4o-mini` | 400 | 1 | 54.0 | 75.77 | 474 |
| `$/model_prediction/ANCE/Claude-Sonnet` | 400 | 2 | 157.5 | 177.91 | 804 |
| `$/model_prediction/ANCE/Gemini-2.5-pro` | 400 | 2 | 117.0 | 135.19 | 577 |
| `$/model_prediction/ANCE/Qwen3_4B` | 398 | 1 | 42.5 | 82.19 | 747 |
| `$/model_prediction/BM25/Gemma3_27B` | 400 | 1 | 56.0 | 77.12 | 788 |
| `$/model_prediction/BM25/Gemma3_12B` | 400 | 2 | 38.0 | 58.52 | 498 |
| `$/model_prediction/BM25/Gemma3_4B` | 400 | 2 | 49.0 | 65.54 | 545 |
| `$/model_prediction/BM25/GPT-4o` | 400 | 1 | 99.5 | 123.47 | 594 |
| `$/model_prediction/BM25/GPT-4o-mini` | 400 | 1 | 56.5 | 81.11 | 677 |
| `$/model_prediction/BM25/Claude-Sonnet` | 400 | 2 | 155.5 | 181.37 | 882 |
| `$/model_prediction/BM25/Gemini-2.5-pro` | 400 | 0 | 117.0 | 143.26 | 1020 |
| `$/model_prediction/BM25/Qwen3_4B` | 398 | 1 | 43.0 | 83.84 | 849 |
| `$/decomposed_query/<Core subquery N>` | 630 | 16 | 66.0 | 80.29 | 332 |
| `$/atomic_facts/BM25/Gemma3_27B/<Atomic fact N>` | 572 | 18 | 75.5 | 84.09 | 323 |
| `$/atomic_facts/BM25/Gemma3_4B/<Atomic fact N>` | 498 | 20 | 72.5 | 82.18 | 258 |
| `$/atomic_facts/BM25/GPT-oss_20B/<Atomic fact N>` | 485 | 19 | 74 | 80.89 | 261 |
| `$/atomic_facts/BM25/Claude-Sonnet/<Atomic fact N>` | 945 | 20 | 85 | 90.9 | 302 |
| `$/atomic_facts/BM25/Gemini-2.5-pro/<Atomic fact N>` | 794 | 23 | 76.0 | 83.97 | 271 |
| `$/atomic_facts/BM25/Qwen3_4B/<Atomic fact N>` | 579 | 20 | 80 | 87.09 | 326 |
| `$/atomic_facts/BM25/Qwen3_30B/<Atomic fact N>` | 567 | 20 | 80 | 87.94 | 243 |
| `$/atomic_facts/BM25/GPT-5/<Atomic fact N>` | 474 | 20 | 73.5 | 84.44 | 297 |
| `$/relevance_check_reasoning/BM25/GPT-5/chunk_fact_relevance/<Chunk N>/<Atomic fact N>[]` | 5000 | 2 | 57.0 | 108.13 | 422 |
| `$/relevance_check_reasoning/BM25/GPT-5/query_chunk_coverage/<Chunk N>/<Core subquery N>[]` | 5000 | 2 | 63.0 | 108.62 | 421 |

## 3. 라벨 분포 (optional)

### `BM25/GPT-5` (400 items)

- query_fact_coverage: {'Covered': 337, 'Not covered': 294}
- query_fact_relevance: 평균 선택 비율 0.833, 전부 선택된 item 323, 절반 미만 선택 62
- chunk_fact_relevance: 판정 범위 Chunk 1..10, 지지 chunk 수 분포 {1: 136, 0: 108, 2: 57, 3: 51, 4: 19, 5: 13, 7: 6, 6: 4, 8: 4, 9: 1, 10: 1}
- query_chunk_coverage: subquery를 커버하는 chunk 수 분포 {0: 98, 1: 81, 2: 65, 3: 54, 4: 29, 5: 26, 6: 16, 8: 13, 7: 7, 9: 6, 10: 5}

### 3b. 라벨 후보 leaf (distinct 값 2~8개)

- `$/relevance_check/BM25/GPT-5/query_fact_relevance/<Core subquery N>/selected_facts[]` → {'Atomic fact1': 368, 'Atomic fact2': 25, 'Atomic fact3': 12, 'Atomic fact4': 2}
- `$/relevance_check/BM25/GPT-5/query_fact_coverage/<Core subquery N>` → {'Covered': 337, 'Not covered': 294}
- `$/relevance_check/BM25/GPT-5/query_chunk_coverage/<Chunk N>[]` → {'Core subquery1': 845, 'Core subquery3': 51, 'Core subquery2': 242, 'Core subquery4': 1}
- `$/relevance_check_reasoning/BM25/GPT-5/chunk_fact_relevance/<Chunk N>/<Atomic fact N>[]` → {'No': 4013, 'Yes': 727}
- `$/relevance_check_reasoning/BM25/GPT-5/query_chunk_coverage/<Chunk N>/<Core subquery N>[]` → {'No': 5171, 'Yes': 1139}
- `$/relevance_check/BM25/GPT-5/chunk_fact_relevance/<Chunk N>/selected_facts[]` → {'Atomic fact1': 603, 'Atomic fact2': 95, 'Atomic fact3': 22, 'Atomic fact4': 5, 'Atomic fact5': 2}

### 3c. gt_chunk 포함률

- ANCE: n=400, gt_in_top10=216, gt_in_full_list=258
- BM25: n=400, gt_in_top10=251, gt_in_full_list=302

## 4. 이상치 (제외/분할 후보)

| id | kind | path | detail |
|---|---|---|---|
| finqa_test_817 | type | `$/decomposed_query` | str (expected dict) |
| nq_test_363 | size | `$/gt_chunk[]` | 54 (median 2.0) |
| nq_test_535 | size | `$/gt_chunk[]` | 21 (median 2.0) |
| nq_test_271 | size | `$/gt_chunk[]` | 28 (median 2.0) |
| nq_test_560 | size | `$/gt_chunk[]` | 26 (median 2.0) |
| nq_test_1280 | size | `$/gt_chunk[]` | 44 (median 2.0) |
| newsqa_test_238 | size | `$/atomic_facts/BM25/GPT-oss_20B/<Atomic fact N>` | 19 (median 1.0) |
| newsqa_test_410 | size | `$/atomic_facts/BM25/GPT-oss_20B/<Atomic fact N>` | 11 (median 1.0) |
| newsqa_test_238 | size | `$/atomic_facts/BM25/Qwen3_4B/<Atomic fact N>` | 13 (median 1.0) |
| newsqa_test_557 | size | `$/atomic_facts/BM25/Qwen3_4B/<Atomic fact N>` | 13 (median 1.0) |

## 5. 설계 힌트 (자동 생성)

- `$/atomic_facts/BM25/Gemma3_27B/<Atomic fact N>` 최대 9개 — fact 체크박스가 길어지므로 item당 fact 상한(예: 8) 또는 HIT 분할 필요
- `$/atomic_facts/BM25/GPT-oss_20B/<Atomic fact N>` 최대 19개 — fact 체크박스가 길어지므로 item당 fact 상한(예: 8) 또는 HIT 분할 필요
- `$/atomic_facts/BM25/Claude-Sonnet/<Atomic fact N>` 최대 12개 — fact 체크박스가 길어지므로 item당 fact 상한(예: 8) 또는 HIT 분할 필요
- `$/atomic_facts/BM25/Gemini-2.5-pro/<Atomic fact N>` 최대 14개 — fact 체크박스가 길어지므로 item당 fact 상한(예: 8) 또는 HIT 분할 필요
- `$/atomic_facts/BM25/Qwen3_4B/<Atomic fact N>` 최대 13개 — fact 체크박스가 길어지므로 item당 fact 상한(예: 8) 또는 HIT 분할 필요
- BM25/GPT-5: query_fact_relevance가 323/400 item에서 '전부 관련' — 정보량 낮음. 절반 미만 선택된 62개 item 우선 샘플링 권장
- BM25/GPT-5: LLM 판정은 Chunk 1..10 범위만 존재 — 사람 annotation도 같은 top-k로 맞추는 게 비교 가능
- BM25/GPT-5: top-k 안에 지지 chunk가 0개인 item 108개 — groundedness task에서 negative-only item이 되므로 positive/negative 균형 샘플링 필요
- ANCE: gt_chunk가 gt_in_top10에 포함된 item 216/400 — gt를 강제 포함할지 spec에서 결정 필요
- BM25: gt_chunk가 gt_in_top10에 포함된 item 251/400 — gt를 강제 포함할지 spec에서 결정 필요
- 타입 불일치 item 1건 (파싱 실패 흔적) — preprocess에서 반드시 exclude
- 이상치 총 10건 — stats.json의 anomalies를 preprocess exclude 목록으로 넘김
