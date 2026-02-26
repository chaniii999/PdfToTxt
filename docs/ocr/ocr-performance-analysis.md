# OCR 지연 원인 분석 (페이지당 ~23초)

---

## 1. 지연 원인 요약

**주요 원인**: Tesseract 호출 횟수. 페이지당 **5~10회** 순차 실행.

| 구간 | 예상 소요 | 비고 |
|------|-----------|------|
| render (350 DPI) | ~0.5초 | A4 ≈ 2480×3508 픽셀 |
| deskew_rgb | ~0.5초 | Hough 변환, Canny |
| add_ocr_border | ~0.1초 | 무시 가능 |
| **Tesseract 1차 5회** | **~10~15초** | rgb, otsu×4(PSM 6/4/3/13) |
| enhance + preset 4회 | **~8~12초** | score≤400일 때만. 전처리 + Tesseract 5회 추가 |
| **합계** | **~20~28초** | 23초는 이 범위 안 |

---

## 2. Tesseract 호출 구조

**1차 (항상)**: 5회
- rgb + PSM 6
- otsu + PSM 6
- otsu + PSM 4
- otsu + PSM 3
- otsu + PSM 13

**2차 (score ≤ 400일 때)**: 최대 5회
- enhance + PSM 6
- preset D + PSM 6
- preset A + PSM 6
- preset B + PSM 6
- preset C + PSM 6

→ **최대 10회** Tesseract 호출. kor+eng, 350 DPI A4 기준 1회당 약 2~3초.

---

## 3. 속도 개선 방안

### 3.1 즉시 적용 가능 (품질 영향 적음)

- **early stop 400 → 450**: 점수 450 이상이면 enhance·preset 생략. 1차 5회만 실행 → 약 10~12초로 단축.
- **PSM 13 제거**: 1차 후보 5개 → 4개. Tesseract 1회 감소.

### 3.2 품질과 타협

- **DPI 350 → 300**: 이미지 크기 약 25% 감소 → Tesseract 1회당 시간 단축.
- **preset 4개 → 2개**: D, A만 시도. B, C 제거.

### 3.3 구조 변경 (구현 부담)

- **1차 후보 병렬 실행**: `concurrent.futures.ThreadPoolExecutor`로 5개 동시 실행. Tesseract는 프로세스 기반이라 병렬화 가능. 5회 순차 ~12초 → 병렬 ~3~4초 수준으로 단축 가능.
- **preset 병렬 실행**: 2차 구간에서 4개 preset을 병렬 실행.

---

## 4. 권장 적용 순서

1. **early stop 400 → 450** (품질 유지, 속도 개선)
2. **PSM 13 제거** (실험용이었다면 제거)
3. **1차 후보 병렬화** (코드 변경 필요, 효과 큼)

---

## 6. 적용된 가성비 최적화 (2025-02)

| 항목 | 적용 | 예상 효과 |
|------|------|-----------|
| **1차 4개 병렬** | ThreadPoolExecutor | 12초 → 3~4초 |
| **early stop 500** | 450 → 500 | 2차 phase 진입 감소 |
| **preset D, A만** | B, C 제거 | 2차 Tesseract 4회 → 2회 |

---

## 5. 참고

- Tesseract `image_to_string`은 매번 새 프로세스 생성. kor+eng LSTM은 초기화 비용이 있음.
- tessdata_best(kor 12MB+) 로딩으로 첫 호출이 더 느릴 수 있음.
