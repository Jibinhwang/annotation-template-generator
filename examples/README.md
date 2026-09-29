# examples

`run_pipeline_v2.py`에 **prompt 한 문장**을 넣어 실제 LLM(qwen/qwen3.8-flash)으로 생성한 결과. 각 폴더에:

| 파일 | 내용 |
|---|---|
| `prompt.txt` | 입력한 문장 |
| `rationale.txt` | LLM이 그렇게 구성한 이유 (+ 그때 준 few-shot 예시) |
| `plan.json` | LLM이 쓴 task plan — 이것만으로 `--plan` 재실행 가능 |
| `preview.html` | 생성된 annotation 화면 (HIT 1개 포함, 더블클릭으로 열림, Submit 시 답 JSON 표시) |

| 폴더 | task | few-shot 조건 | gold |
|---|---|---|---|
| `1_completeness_conciseness` | subquery ↔ atomic fact 관련성 + Covered 여부 | 기본 예시 4개 | query_fact_relevance, query_fact_coverage |
| `2_groundedness` | passage ↔ atomic fact 지지 여부 | **다른 형식의 예시만** (pairwise, likert) | chunk_fact_relevance |
| `3_retrieval_coverage` | passage ↔ subquery 답변 여부 | 기본 예시 4개 | query_chunk_coverage |
| `4_new_task_gt_info_coverage` | passage가 정답 passage의 정보를 담는지 Yes/No + 누락 서술 | pairwise 예시 1개 (**같은 task 예시 없음**) | 없음 (데이터에 해당 라벨 없음) |

세 task의 gold는 원본 `relevance_check` 라벨과 200/200 일치 확인. `analyze_report.md`는 1단계 analyze가 raw JSON에서 뽑은 리포트.
`hits.csv` / `units.jsonl`(전체 데이터)은 용량과 데이터 재배포 문제로 포함하지 않음 — `--plan plan.json`으로 재생성하면 된다.
