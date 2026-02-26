# 2차 eng OCR 인식 로직·분류 규칙

한글 1차의 자모/조합 참조(user_words, user_patterns)와 유사하게, 영문 2차에서 알파벳·숫자·특수문자 형태 유사성 기반 보정.

---

## 1. 구조 대비

| 1차 kor | 2차 eng |
|---------|---------|
| user_words (의견, 익명, 폐기) | eng_user_words (LLM, PII, Token) |
| user_patterns (원본:, 의:, 폐:) | eng_user_patterns (Read-Write, 약어) |
| 자모 혼동 (ㅇ↔ㅁ, ㅔ↔ㅖ) | 형태 유사 (0↔O, \|→I, 1↔I) |
| jamo-confusion-rules | eng_ocr_rules (postprocess_eng_result) |

---

## 2. 인식 로직

### 2.1 Tesseract eng 전용 설정

- `config/tesseract/eng_user_words.txt`: 도메인 단어 (LLM, PII, AI, Token, Hugging Face 등)
- `config/tesseract/eng_user_patterns.txt`: 약어·복합어 패턴
- `_ocr_roi_eng` 호출 시 `get_eng_tesseract_config()`로 eng 전용 config 주입

### 2.2 형태 유사 문자 보정 (postprocess_eng_result)

| OCR 출력 | 보정 | 비고 |
|----------|------|------|
| P0II | PII | 0↔O (숫자-알파벳 혼동) |
| P\|I | PII | \|→I (파이프 오인식) |
| P1I | PII | 1↔I (대문자 사이) |
| Al | AI | I↔l (대소문자 혼동) |
| 0!! | PII | 도메인 약어 맵 |
| LLeMm, ㄴㄴM | LLM | 약어 맵 |

### 2.3 분류 규칙 (classify_eng_candidate)

**채택 조건**

- 한글(완성형·자모) 미포함
- 알파벳 비율 ≥ 50%
- 3자 이하 + 숫자/특수문자 과다 시 거부 (한글→Latin 오인식 의심)
- 도메인 단어와 유사 시 우선 채택

**거부 조건**

- 숫자만
- 한글 포함
- 알파벳 비율 < 50%

---

## 3. 구현 파일

- `services/ocr/eng_ocr_rules.py`: postprocess_eng_result, is_valid_eng_result, classify_eng_candidate
- `services/ocr/ocr_twostage.py`: _ocr_roi_eng에 eng config 적용, classify_eng_candidate로 채택 판정
- `config/tesseract/eng_user_words.txt`
- `config/tesseract/eng_user_patterns.txt`
