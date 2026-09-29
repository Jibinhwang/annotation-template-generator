# annotation-template-generator

**raw 평가 JSON + 자연어 한 문장 → MTurk annotation 템플릿(HTML) + 업로드용 데이터, end-to-end 자동 생성.**

```
python run_pipeline_v2.py raw.json --prompt "chunk 하나를 보여주고 atomic fact 중 그 chunk가 지지하는 걸 전부 고르게 하자. BM25 top-10, HIT 20개" --out runs/groundedness --open
```

이 한 줄이 데이터 구조 분석 → 의도 해석(LLM) → 데이터 정제·HIT 조립 → HTML 생성까지 수행하고, 끝나면 annotator가 보게 될 화면(`preview.html`)이 브라우저로 열린다.

---

## 1. 문제

RAG 평가 데이터(query / decomposed subquery / retrieved chunk / atomic fact / LLM 판정)에 대해 사람 annotation을 받으려면, 매번 (1) JSON을 뜯어 원하는 관계를 뽑아 HIT 단위로 자르고 (2) 그에 맞는 MTurk HTML을 손으로 만들어야 했다. 이 저장소는 그 두 작업을 **"무엇을 물을지"를 적은 문장 하나**로 대체한다.

| 입력 | 출력 |
|---|---|
| raw JSON (구조를 미리 알 필요 없음) | `hits.csv` — MTurk 업로드용 데이터 (1행 = 1 HIT, LLM 라벨 gold 포함) |
| prompt — annotation 목적 (한국어/영어) | `template.html` — MTurk 템플릿, `preview.html` — 로컬 미리보기 |

---

## 2. 전체 로직

```
raw.json ──① analyze.py──▶ stats.json ─┐
                                       ├──② plan_from_prompt.py (LLM)──▶ plan.json  ←(사람 승인: --confirm)
prompt ────────────────────────────────┘
raw.json + plan.json ──③ preprocess_v2.py──▶ hits.csv, units.jsonl, manifest.json
hits.csv + plan.json ──④ render_v2.py─────▶ template.html (MTurk) / preview.html (로컬)
```

핵심 원칙은 **LLM은 판단만 하고 실행은 하지 않는다**는 것이다. LLM이 쓰는 것은 `plan.json` 하나뿐이고, 데이터를 자르고 HTML을 그리는 일은 전부 결정론적 코드가 plan을 읽어서 수행한다. 그래서 같은 입력이면 같은 결과가 나오고, 틀리면 plan.json 한 곳만 고쳐 `--plan`으로 다시 돌리면 된다.

### ① analyze — 데이터를 모른 채로 구조를 읽는다 (`analyze.py`)

JSON을 재귀로 훑으며 경로(path)마다 통계를 모은다. 필드 이름을 가정하지 않으므로 다른 구조의 JSON에도 동작한다.

- **열거형 축** 학습: `Chunk 3`, `Atomic fact2`, `Core subquery1` 처럼 "이름+번호" 키 묶음을 데이터에서 찾아 하나의 축으로 인식 (번호가 1부터 시작하고 2개 이상일 때만 — `BM25`, `GPT-5` 같은 고유명사는 제외)
- **범주형 축**: item마다 반복되는 dict 키(retriever 이름, 모델 이름) → plan에서 선택 가능한 값
- 크기 분포(item당 subquery/fact/chunk 수), 텍스트 길이, 라벨 후보, gt 포함률
- **이상치**: 타입이 다수와 다른 item(예: `decomposed_query`가 dict가 아니라 str), 크기 극단치 → preprocess가 자동 제외

출력 `report.md`(사람용) / `stats.json`(다음 단계용). 필드가 없으면 해당 섹션만 skip하고 절대 죽지 않는다.

### ② plan_from_prompt — 의도를 실행 명세로 번역한다 (`plan_from_prompt.py`, `plan.py`)

LLM(OpenRouter, 기본 `qwen/qwen3.8-flash`)에게 네 가지를 준다: plan 스키마, ①에서 만든 데이터 컨텍스트(경로 목록을 plan 문법으로 + 실제 item 샘플 + **gold 후보 경로와 값 예시**), few-shot 예시 plan 4개, 사용자 prompt. LLM은 `{"plan": ..., "rationale": ...}`를 돌려준다.

plan 하나에 들어가는 것:

| 항목 | 의미 | 예 |
|---|---|---|
| `roles` | 데이터 안의 역할 → 경로 | `facts: atomic_facts.BM25.GPT-5{}` |
| `unit` | annotation 항목 1개의 단위 | `single of passages` / `pair` / `item` |
| `display` | 맥락 카드, 좌/우 카드에 무엇을 놓을지 | left = 현재 passage, right = fact 목록 |
| `questions` | 질문들 — 위젯, 반복 단위, 옵션, **gold 경로** | multi_select over facts, gold = `relevance_check…chunk_fact_relevance` |
| `instructions` | annotator용 설명문 (summary, definitions, howto, tip) | |
| `hit`, `filters`, `attention` | HIT 크기·샘플링, 제외 규칙, attention check 규칙 | |

나온 plan은 코드가 검증한다 — 구조, 경로가 실제 샘플 item에서 값을 돌려주는지, gold 경로가 살아있는지. 실패하면 오류(비슷한 실제 경로 힌트 포함)를 LLM에 되돌려 최대 2회 고치게 하고, 시도마다 응답을 `2_plan/attempts/`에 남긴다. `--confirm`이면 요약을 보여주고 사람이 승인해야 진행한다.

### ③ preprocess_v2 — plan대로 데이터를 자른다 (`preprocess_v2.py`, `jsonpath.py`)

1. item마다 `roles` 경로를 해석해 `{question, subqueries, facts, passages, gt}` 값을 만든다
2. 필터: 이상치 id 제외, fact가 너무 많은 item 제외 등
3. `unit` 규칙대로 항목을 만든다 — `single of passages`면 passage 10개 → 항목 10개
4. **gold**: 질문의 gold 경로를 항목 인덱스(몇 번째 passage/subquery)에 맞춰 찾아 사람 답과 같은 형식(fact 인덱스 리스트, `"Covered"`)으로 변환
5. gold가 있으면 positive item ≈70%로 **균형 샘플링**
6. HIT으로 묶고(보통 query 1개의 항목들 = HIT 1개), HIT마다 **attention check** 삽입 — 항목의 passage(또는 fact)를 *다른 데이터셋* item 것으로 바꿔 정답이 자명하게 만들고 정답을 `expected`에 기록

### ④ render_v2 — plan대로 화면을 그린다 (`render_v2.py`, `theme.py`)

외형(Instructions 패널 → 진행률 → 항목 탭 → 맥락 카드 → 좌/우 카드 → 질문 → Submit)은 기존 랩 템플릿을 따르고, 내용은 전부 plan에서 읽는다. 위젯은 `multi_select`(None 옵션, 상호배제) / `single_choice` / `likert` / `free_text`. 모든 필수 질문에 답해야 Submit이 켜지고, 답은 `input_answers` 하나에 JSON으로 묶여 나간다.

- `template.html`: 데이터 자리에 `${roles}`, `${unit}` 자리표시자 → MTurk가 `hits.csv` 행으로 채움
- `preview.html`: HIT 1개를 인라인 → 더블클릭으로 열림, Submit하면 답 JSON 표시
- **보안**: template에는 `roles / unit / hit_id`만 들어간다. `src_id / is_attention / gold / expected`는 CSV에만 있어 작업자가 소스를 봐도 attention 위치와 정답을 알 수 없다. MTurk 결과에는 input 컬럼이 따라오므로 `item_idx`로 join하면 된다.

---

## 3. 처음 받은 사람이 돌려보는 순서

### 3-1. 요구사항
- Python 3.9 이상. 외부 패키지 없음 (표준 라이브러리만 사용).
- LLM 단계(②)를 쓰려면 OpenRouter API 키. plan 파일을 직접 주면(`--plan`) 키 없이도 전부 동작.

### 3-2. 파일 배치

저장소를 받은 직후 이렇게 놓는다 (`data/`, `.env`, `runs/`는 git에 올라가지 않음):

```
annotation-template-generator/
├─ run_pipeline_v2.py, analyze.py, plan.py, ...      ← 코드 (저장소에 포함)
├─ plans/                                            ← 예시 plan 7개 (저장소에 포함)
├─ .env                 ← 직접 생성: .env.example 복사 후  OPENROUTER_API_KEY=sk-or-...  한 줄
├─ data/                ← 직접 생성: raw JSON을 여기에 둔다
│   └─ test-close_ended_queries_R3_Qwen3-80B_GPT-5_reasoning.json   (예)
└─ runs/                ← 실행하면 자동 생성: 결과물
```

```powershell
git clone https://github.com/<id>/annotation-template-generator.git
cd annotation-template-generator
copy .env.example .env        # 메모장으로 열어 키 입력 (cmd: notepad .env)
mkdir data                    # raw JSON 파일을 data\ 안으로 복사
```

### 3-3. raw JSON이 갖춰야 할 형태

최상위가 **dict의 리스트**(또는 `{id: dict}`)이면 ① analyze는 어떤 구조든 돌아간다. plan을 LLM이 제대로 쓰려면 아래 역할을 하는 필드가 있어야 한다 (이름은 달라도 됨 — LLM이 경로를 찾는다):

| 역할 | 이 데이터에서의 경로 | 비고 |
|---|---|---|
| 질문 | `query` | 스칼라 |
| sub-question 목록 | `decomposed_query` = `{"Core subquery1": ..., ...}` | 번호 키 dict → `{}` 로 접근 |
| atomic fact 목록 | `atomic_facts.<retriever>.<model>` = `{"Atomic fact1": ..., ...}` | |
| 검색된 passage 목록 | `retrieved_chunk.<retriever>` = `[str, ...]` | |
| (선택) LLM 라벨 | `relevance_check.<retriever>.<model>.{query_fact_relevance, chunk_fact_relevance, query_fact_coverage, query_chunk_coverage}` | 있으면 gold로 붙음 |
| (선택) 정답 passage | `gt_chunk` = `[str, ...]` | pairwise attention 등에 사용 |

### 3-4. 실행

```powershell
# A. prompt로 (LLM이 plan 작성 → 요약 확인 → y → 끝까지)
python run_pipeline_v2.py data\test-close_ended_queries_R3_Qwen3-80B_GPT-5_reasoning.json --prompt "chunk 하나를 보여주고 atomic fact 중 그 chunk가 지지하는 걸 전부 고르게 하자. BM25 top-10, HIT 20개" --out runs\groundedness --confirm --open

# B. 미리 쓴 plan으로 (LLM·키 없이)
python run_pipeline_v2.py data\test-close_ended_queries_R3_Qwen3-80B_GPT-5_reasoning.json --plan plans\groundedness_multiselect.json --out runs\groundedness --open

# LLM 사용량·비용 확인
python llm_client.py
```

`--open`을 붙이면 끝나자마자 `preview.html`이 브라우저로 열린다. 붙이지 않았으면 `runs\groundedness\4_render\preview.html`을 더블클릭.
문장 예시는 `prompts_examples.txt`에 있다.

### 3-5. 산출물 `runs/이름/`
```
1_analyze/report.md, stats.json
2_plan/plan.json, prompt.txt, rationale.txt, attempts/
3_prep/hits.csv, units.jsonl, manifest.json
4_render/template.html, preview.html, preview_all/
pipeline_summary.json
```
- **MTurk 업로드** = `4_render/template.html`(Design Layout에 붙여넣기) + `3_prep/hits.csv`(Publish Batch에서 업로드).
- 문구나 설정을 고치고 싶으면 `2_plan/plan.json`을 편집한 뒤 `--plan runs\이름\2_plan\plan.json` 으로 재실행 (LLM 재호출 없음).
- 단계별로 따로 돌릴 수도 있다: `analyze.py raw --out d` → `plan_from_prompt.py raw "…" --stats d/stats.json --out plan.json` → `preprocess_v2.py raw --plan plan.json --stats d/stats.json --out p` → `render_v2.py p/hits.csv --plan plan.json --out r`.

### 검증된 prompt (`prompts_examples.txt`)

| 목적 | prompt | 결과 |
|---|---|---|
| completeness / conciseness | subquery 하나를 보여주고 atomic fact 중 관련 있는 걸 전부 고르게 하고, 그 fact들이 subquery를 Covered하는지 Not covered인지 고르게 하자 | unit=subquery, multi_select + Covered/Not covered, gold 2개 |
| groundedness / verifiableness | chunk 하나를 보여주고 atomic fact 중 그 chunk가 지지하는 걸 전부 고르게 하자 | unit=passage, multi_select(facts), gold |
| retriever 평가 | chunk 하나를 보여주고 subquery 중 그 chunk가 답하는 걸 전부 고르게 하자 | unit=passage, multi_select(subqueries), gold |
| (형식 확장 예) | passage 두 개를 나란히 보여주고 어느 쪽이 질문에 더 잘 답하는지 고르게 하자 | unit=pair, single_choice A/B, gold 없음 |

세 task 모두 실제 LLM으로 생성해 확인: gold가 원본 라벨과 200/200 일치, attention·완료 게이트·제출 JSON 정상. 호출당 비용 ≈ $0.001–0.003.

---

## 4. 파일

| 파일 | 역할 |
|---|---|
| `run_pipeline_v2.py` | ①~④ 순서 실행, `pipeline_summary.json` |
| `analyze.py` | 스키마·축·분포·이상치 리포트 (범용) |
| `plan.py` | plan 스키마(docstring)·검증·예시 로딩 |
| `plan_from_prompt.py` | prompt + stats → plan (LLM, 검증 재시도, 시도 로그) |
| `jsonpath.py` | plan 경로 문법 (`a.b`, `list[]`, `list[:k]`, `enum{}`) |
| `preprocess_v2.py` | 역할 추출 → 필터 → unit → gold → 샘플링 → HIT → attention |
| `render_v2.py`, `theme.py` | plan → template.html / preview.html |
| `llm_client.py` | OpenRouter 호출, `.env` 로딩, 사용량·비용 로그, 빈 응답/잘림 처리 |
| `plans/*.json` | 예시 plan 7개 (few-shot 겸 회귀 테스트) |

## 5. 한계와 다음 단계

- gold는 LLM이 plan에 경로를 적어야 붙는다. 데이터 컨텍스트에 gold 후보를 명시해 두었지만, 빠뜨리면 `--confirm`에서 보고 plan.json에 추가하면 된다.
- 위젯 4종. 순위 매기기·텍스트 하이라이트 등은 추가 구현 필요.
- Instructions의 정의("Supported", "Covered" 등)는 LLM 초안이다. 랩의 기준 문서가 있으면 plan에 고정해 넣는 것이 맞다.
- MTurk 결과 채점(attention 통과율, 사람–LLM 일치도, 작업자 간 일치도)은 아직 없다 — `units.jsonl`의 gold/expected와 `input_answers`를 `item_idx`로 join하면 된다.
