# Post-OCR 정제 파이프라인

OCR 결과에 적용되는 텍스트 정규화 단계. `services/ocr/postprocess.py`의 `correct_ocr_text()`가 담당한다.

---

## 1. 오인식 패턴 치환

- **노이즈 라인 제거**: 표선·구분선만 있는 줄 제거 (`=`, `—`, `|` 등)
- **음절 병합**: `경\n우` → `경우` (줄바꿈/2칸 이상 공백 시 한글 음절 복원)
- **자모 보정**: 섬→성, 않→많 (자모 구조 기반 규칙)
- **숫자 오인식**: `O`→`0`, `I`→`1` (숫자 사이에서만), `7.`→`1.` (목차 번호)

---

## 2. 사전 기반 보정

`config/postprocess/typo_map.txt`에서 `wrong\tright` 쌍을 로드해 치환한다.

- 형식: 한 줄에 `잘못된텍스트\t올바른텍스트`
- `#`으로 시작하는 줄은 주석
- 긴 패턴 우선 적용

---

## 3. 금지 단어 패턴 탐지

`config/postprocess/prohibited_patterns.txt`에 정규식 패턴을 한 줄에 하나씩 정의한다.

- 탐지 시 `logging.debug`로 로깅
- 필요 시 마스킹·제거 로직 확장 가능

---

## 4. 세그먼트 파손 복구 (postprocess_normalize)

`services/ocr/postprocess_normalize.py`의 `normalize_text()`가 담당. 줄/토큰 파손 복원.

- **NFC 정규화**: 자모 분리 한글 → 결합형
- **한글 줄바꿈 복구**: `스\n스로` → `스스로` (1~2글자 조각만)
- **영문 줄바꿈/공백 복구**: `L\nL\ne\nM\nm` → `LLM`, `Sel f-Ref lective` → `Self-Reflective`
- **단독 불릿 라인 제거**: `·` 단독 줄 삭제
- **괄호 내부 정제**: `(L\nL\ne\nM\nm)` → `(LLM)`
- **가드레일**: 라인당 변경 5% 초과 시 플래그

상세 규칙은 `docs/ocr/postprocess-normalize-rules.md` 참조.

---

## 설정 파일

| 경로 | 용도 |
|------|------|
| `config/postprocess/typo_map.txt` | 오인식→정답 치환 사전 |
| `config/postprocess/prohibited_patterns.txt` | 금지 패턴 정규식 목록 |
