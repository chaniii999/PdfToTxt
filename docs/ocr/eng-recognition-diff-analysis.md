# 영어 인식 diff 분석 (언어학·시각적)

의회문서 표준안 OCR 비교 데이터 기반. 영어 80.6% → 개선 목표.

---

## 1. 오인식 패턴 분류

### 1.1 형태 유사 (L↔e, I↔|, P↔ㅁ)

| 원본 | 추출 | 시각적 원인 |
|------|------|-------------|
| LLM | Lem | L과 e(소문자) 혼동. L의 세로선+꺾임이 e의 곡선과 유사 |
| PII | 미I | P와 ㅁ(한글) 혼동. 둥근 부분+직선 형태 유사. kor+eng 혼용 시 P→ㅁ |
| AI | \| | A+I가 \|(파이프)로 합쳐짐. I(대문자)와 \| 형태 동일 |
| AI | 시 | A+I가 ㅅ+ㅣ(한글)로. kor 우선 시 Latin→한글 |

### 1.2 CamelCase 공백 손실

| 원본 | 추출 | 원인 |
|------|------|------|
| Self-Reflective Reliability | Self-ReflectiveReliability | 대문자 R 앞 공백 누락 |
| Safety Protocols | SafetyProtocols | 동일 |
| Kill-Switch | Kill-Switch | 하이픈 유지 (정상) |

### 1.3 한글→영문 혼동 (kor+eng 스크립트 오판)

| 원본 | 추출 | 원인 |
|------|------|------|
| Multi-layer | 삐'ti-layer | Multi→삐'ti. M→ㅁ+ㅃ, u→', l→t 등 |
| Hugging Face | 허깅폐이스깨400!ㅁ09 Face) | Hugging→한글+숫자+기호. 스크립트 혼재 |
| Read-Write Token | Read-Write Token'Sㅁ' | Token 뒤 'Sㅁ' 추가. ㅁ(자모) 오삽입 |

### 1.4 괄호 내부 약어

| 원본 | 추출 | 비고 |
|------|------|------|
| (LLM) | (Lem) | Lem→LLM 보정 필요 |
| (PII) | (미I) | 미I→PII 보정 필요 |

---

## 2. 개선 로직

### 2.1 typo_map (사전 치환)

- (Lem) → (LLM)
- 미I → PII
- Self-ReflectiveReliability → Self-Reflective Reliability
- SafetyProtocols → Safety Protocols
- 삐'ti-layer → Multi-layer
- 허깅폐이스깨 → Hugging
- 허깅페이스 → Hugging
- Token'Sㅁ' → Token

### 2.2 postprocess_normalize (규칙)

- paren_fix ACRONYM_MAP: Lem, Lemm 추가
- pipe_to_ai: `: | 모델` → `: AI 모델` (파이프가 AI 오인식)
- camelcase_space: 대문자 앞 공백 삽입 (CamelCase 경계)

### 2.3 eng_ocr_rules (2차 eng)

- ACRONYM_FIX: Lem, Lemm 추가

---

## 3. 적용 완료

| 파일 | 변경 |
|------|------|
| typo_map.txt | (Lem), 미I, Self-ReflectiveReliability, SafetyProtocols, 삐'ti-layer, 허깅폐이스깨, Token'Sㅁ', 접근하는 시는, 다충 |
| postprocess_normalize | ACRONYM_MAP Lem/Lemm, pipe_to_ai 규칙 |
| eng_ocr_rules | ACRONYM_FIX Lem/Lemm |
