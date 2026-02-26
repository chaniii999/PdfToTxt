# OCR 인식률 개선 체크리스트

테스트 결과(한글 83.9%, 영어 43.3%) 기준. 인식률 개선을 위해 할 일 정리.

---

## 현재 오인식 요약

**한글**: ㅇ↔ㅁ(안→만, 인→민, 억→먹), ㅈ↔ㅅ(조→소), 전→천, 언어→먼어  
**영문**: LLM→Z(LM)CI, AI→Al, PII→0!!, Self-Reflective→MIE, Token→@  
**혼합**: 권익→de/MH, 스스로→AZO, 확신→BATE, 정보→FEE, 메커니즘→dF  
**기호·숫자**: 수월성→수뭘섬, 인류의→2150, 하드웨어→S32  

---

## 1. 환경·설정 (우선)

- [ ] **tessdata_best 검증** — kor 12MB+, eng 4.7MB+ 확인. 미달 시 교체
- [x] **DPI 350** — `_render_page(dpi=350)` 적용
- [x] **테두리 10px** — `add_ocr_border` 적용 여부 확인
- [x] **deskew** — `deskew_rgb` 적용 여부 확인

---

## 2. 전처리 (한글·자모 구분)

- [x] **sharpen 강화** — preset D, enhance_for_ocr의 sharpen 0.9 → 1.0 적용
- [x] **CLAHE** — enhance_for_ocr의 clip_limit 2.5 → 3.0 적용
- [x] **preset D 우선** — 한글 특화 preset이 A/B/C보다 먼저 시도되는지 확인

---

## 3. 후보·선택 로직

- [x] **early stop 450** — 속도 개선 (enhance·preset 생략 확대)
- [x] **PSM 13 제거** — 1차 후보 4개로 축소, 속도 개선
- [ ] **점수 공식** — `길이×(0.2+0.8×한글비율)` 유지. 한글 비율 가중 확인

---

## 4. 적용하지 말 것

- [ ] **영문 키워드 가산점** — LLM, AI, PII 등. 과거 품질 악화로 제거됨
- [ ] **lang_split** — kor/eng 분리 시도. 이전에 한글·영어 모두 악화됨

---

## 5. Tesseract 한계 (대안 검토)

kor+eng 혼용 시 한글을 Latin으로 읽는 경향은 Tesseract 한계.  
전처리·PSM만으로는 개선에 한계가 있으면:

- [ ] **후처리 치환** — ㄴㄴ→LLM, 0!!→PII 등. 도메인 특화 시 선택적 검토
- [ ] **LLM 후처리** — 요약·분석 단계에서 문맥 기반 보정
- [ ] **외부 OCR** — CLOVA, Upstage, PaddleOCR 등 한글 특화 엔진 검토

---

## 6. 테스트 순서

1. DPI 350 적용 후 `ocr_test.py` 실행
2. sharpen 1.0 적용 후 재테스트
3. early stop 400 적용 후 재테스트
4. PSM 13 추가 후 재테스트

각 단계마다 한글·영어 인식률을 기록해 비교

---

## 참고

- `docs/ocr/ocr-tuning-recommendations.md`: 세팅별 상세 권장
- `docs/ocr/ocr-misrecognition-encyclopedia.md`: 한글↔Latin 혼동 쌍
- `docs/ocr/improvement-log.md`: 과거 시도·교훈
