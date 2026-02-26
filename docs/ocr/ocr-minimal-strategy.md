# OCR 최소 전략 (한글 문서 특화)

1~2초/페이지 목표. 기본 프로세스만 유지하고 과도한 전처리 제거.

---

## 1. DPI

- **300 고정**. 350, 400, 600 사용 금지.
- 변환 직후 `image.shape` 로그 출력.

---

## 2. Tesseract 옵션

| 항목 | 값 |
|------|-----|
| --oem | 1 |
| --psm | 6 |
| -l | kor |
| preserve_interword_spaces | 1 |
| tessedit_do_invert | 0 |

- psm 3 사용 금지.
- OEM 0, 2 사용 금지.

---

## 3. 전처리 (최소)

**유지**
- Grayscale 변환
- Otsu threshold
- Deskew (회전 각도 1도 이상일 때만)

**제거**
- bilateralFilter
- adaptiveThreshold
- morphology
- 과도한 blur

---

## 4. 디스크 I/O

- PNG 저장/재로딩 없음.
- 메모리에서 바로 Tesseract로 전달.
- 임시 파일 생성 금지.

---

## 5. OCR 호출

- 페이지당 pytesseract 단일 호출.
- 다중 PSM/후보 제거.

---

## 6. 성능 로깅

- 페이지 번호
- 이미지 크기 (shape)
- 처리 시간
- DPI
- PSM

3초 초과 시 병목 경고 로그.

---

## 7. 목표

- DPI 300 / A4 / 한글 95%
- **1~2초/페이지**
- 3초 초과 시 병목 분석

---

## 8. 테스트

- 동일 의회문서 5페이지 고정 샘플 사용.
- 전처리 제거 전/후 처리 시간 비교.
