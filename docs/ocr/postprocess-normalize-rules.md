# Post-OCR 정규화 규칙 목록

세그먼트(줄/토큰) 파손 복구를 위한 규칙 테이블. 외부 API 없이 로컬에서만 적용.

## 적용 순서

1. NFC → 2. 줄바꿈 복구 → 3. 괄호 내부 정제 → 4. 토큰 치환 → 5. 가드레일

---

## 규칙 테이블

| rule_id | 설명 | 적용 조건 | 예시 |
|---------|------|-----------|------|
| nfc | NFC 유니코드 정규화 | 항상 적용 | 자모 분리 한글 → NFC 결합형 |
| bullet_remove | 단독 불릿 라인 제거 | 라인이 `^\s*[·∙•]\s*$` 패턴일 때 | `·` 단독 줄 → 제거 |
| kr_kr_merge | 한글-한글 사이 줄바꿈 제거 | 1~2글자 한글 조각이 연속될 때 | `스\n스로` → `스스로` |
| en_en_break_merge | 영문-영문 사이 줄바꿈 제거 | `(?<=[A-Za-z])\s*\n\s*(?=[A-Za-z])` | `L\nL\ne\nM\nm` → `LLeMm` |
| en_en_space_merge | 영문 단어 내부 공백 제거 | 짧은 토큰(≤3자) 또는 소문자 시작 토큰 앞 공백 | `Sel f-Ref lective` → `Self-Reflective` |
| paren_fix | 괄호 내부 정제 | `\( ... \)` 구간 | `(L\nL\ne\nM\nm)` → `(LLM)` |
| ocr_similar_en | 영문 토큰 OCR 유사문자 치환 | 알파벳/숫자 비율 60%+ | `A·I\|` → `AI` |

---

## 상세 설명

### nfc
- `unicodedata.normalize("NFC", text)` 적용
- 자모 분리된 한글을 결합형으로 통일

### bullet_remove
- `^\s*[·∙•]\s*$` 패턴의 라인 삭제
- 문장 단절 원인이 되는 단독 불릿 제거

### kr_kr_merge
- 1~2글자 한글 조각이 줄바꿈으로 쪼개진 경우만 병합
- 문단 구분(빈 줄 2개 이상), 번호/제목 라인은 보존
- 예: `스\n스로`, `기\n억`, `차\n단`

### en_en_break_merge
- 영문 글자 사이의 줄바꿈 제거
- 약어 복구: `L\nL\ne\nM\nm` → `LLeMm` (paren_fix에서 `LLM`으로 정규화)

### en_en_space_merge
- 영문 단어 내부에 끼어든 공백 제거
- 조건: 다음 토큰이 1~3자이거나 소문자로 시작할 때 (camelCase 조각 병합)

### paren_fix
- `\( ... \)` 내부: 줄바꿈/공백 제거, `|`→`I`, `0`↔`O` 교정
- 약어 맵: `LLeMm`→`LLM` 등

### ocr_similar_en
- 영문 비율 60% 이상 토큰에만 적용
- `·` 제거, `|`→`I` (영문 문맥)
- 한국어 문맥 토큰에는 미적용 (오탐 방지)

---

## 가드레일

- 라인당 변경 문자 비율 5% 초과 시 `flags`에 `guardrail` 메시지 추가
- 라인 수 변경 시 `guardrail: line_count_changed` 플래그

---

## diff 로그

각 규칙 적용 시 변경이 있으면 `DiffEntry` 기록:

- `rule_id`: 적용된 규칙
- `before`: 변경 전 (최대 200자)
- `after`: 변경 후 (최대 200자)
- `line_id`: (선택) 라인 번호
- `confidence`: (선택) 확신도

---

## 테스트 케이스

| 입력 | 기대 출력 |
|------|-----------|
| `초거대 언어 모델(L\nL\ne\nM\nm\n)` | `초거대 언어 모델(LLM)` |
| `Sel f-Ref lective Reliability` | `Self-Reflective Reliability` |
| `스\n스로` | `스스로` |
| `기\n억` | `기억` |
| `차\n단` | `차단` |
| `문장 앞.\n·\n문장 뒤.` | `문장 앞.\n문장 뒤.` (불릿 제거, 줄 유지) |
