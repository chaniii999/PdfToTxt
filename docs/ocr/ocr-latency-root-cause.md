# OCR 1페이지 3분 48초 지연 — 원인·해결방안

## 1. 전체 흐름 추적

```
POST /ocr (file)
  → api/ocr.py: content = await file.read()
  → extract_text_stream(content)
    → fitz.open() → total=1
    → yield "started"
    → use_parallel=False (total<2)
    → for idx in [0]:
        → asyncio.to_thread(_process_page_sync, page, 0, 1, force)
          → _render_page(page, DPI=300)           # [1] PDF→이미지 렌더
          → preprocess_minimal(rgb)               # [2] 전처리
          → _ocr_single(pil_img, rgb_original)    # [3] OCR
            → ocr_page_twostage(...)              # [4] 2단 OCR
          → correct_ocr_text(text)                 # [5] 후처리
    → yield page ndjson
    → yield "done"
```

---

## 2. 병목 구간별 원인

### [1] _render_page — DPI 300

| 항목 | 값 |
|------|-----|
| DPI | 300 (고정) |
| A4 300DPI | 2480×3508 ≈ 8.7M 픽셀 |
| 영향 | 해상도 높을수록 후속 단계 부담 증가 |

### [2] preprocess_minimal — 업스케일

| 항목 | 값 |
|------|-----|
| UPSCALE_FACTOR | 1.5 (기본, env: OCR_UPSCALE) |
| 결과 크기 | 3720×5262 ≈ 19.6M 픽셀 |
| 처리 | Grayscale → CLAHE → Sharpen → Otsu → Morphology → Border |
| 영향 | 이미지 2.25배, Tesseract 입력 크기 증가 |

### [3][4] ocr_page_twostage — Tesseract 다중 호출

| 호출 | 함수 | 대상 | 횟수 |
|------|------|------|------|
| 1 | image_to_string(kor) | 전체 이미지 | 1회 |
| 2 | image_to_data(kor) | 전체 이미지 | 1회 |
| 3 | _ocr_roi_eng(eng) | 의심후보 ROI | **N회** |

- **N = eng 의심후보 수**: 숫자, 특수문자, 자모만 있는 word 등
- 문서당 50~200+ 단어 가능 → N회 Tesseract eng 호출
- **호출당 1~3초** 가정 시, N=100이면 100~300초

### [5] correct_ocr_text

- typo_map, normalize 등 — 상대적으로 가벼움

---

## 3. 원인 요약

| # | 원인 | 기여도 |
|---|------|--------|
| 1 | **eng ROI N회 호출** (제한 없음) | 높음 |
| 2 | **image_to_string + image_to_data** 2회 (동일 이미지) | 중간 |
| 3 | **DPI 300 + UPSCALE 1.5** (이미지 과대) | 중간 |
| 4 | Tesseract subprocess 오버헤드 (호출마다) | 중간 |

---

## 4. 해결방안

### 4.1 eng ROI 호출 수 제한 (우선 적용)

```python
# ocr_twostage.py
ENG_ROI_MAX = int(os.environ.get("OCR_ENG_ROI_MAX", "20"))  # 기본 20개

# for w in words: 루프 내
if len(replacements) >= ENG_ROI_MAX:
    break
```

- 의심후보가 많아도 상위 N개만 eng OCR 수행
- N=20이면 eng 호출 20회로 제한 → 수십 초 절감 가능

### 4.2 image_to_data 1회로 통합

- image_to_data 1회 호출 후, block/line 정렬로 전체 텍스트 재구성
- image_to_string 제거 → Tesseract 1회 절감
- `docs/ocr/split-order-root-cause.md` 등 기존 논의 참고

### 4.3 DPI·업스케일 조정

```bash
# .env 또는 환경변수
OCR_DPI=200          # 300→200 (선택)
OCR_UPSCALE=1.0      # 1.5→1.0 (가장 효과 큼)
```

- UPSCALE 1.0: 이미지 크기 약 44% 감소
- DPI 200: 픽셀 수 약 44% 감소 (품질 저하 가능)

### 4.4 tessdata 버전

- `tessdata_best`: 정확도 높음, 느림
- `tessdata_fast`: 속도 우선
- `tessdata`: 기본

### 4.5 eng ROI 배치 (구조 변경)

- ROI crop들을 한 이미지로 합쳐 1회 eng OCR 후 bbox로 분리
- 구현 난이도 높음

---

## 5. 권장 적용 순서

1. **ENG_ROI_MAX=20** — ✅ 적용됨. eng 2차 호출 상한 (기본 20개)
2. **OCR_UPSCALE=1.0** — `OCR_UPSCALE=1.0` 환경변수로 속도 우선
3. **image_to_data 1회 통합** — kor 텍스트 재구성 로직 필요
4. DPI·tessdata — 품질/속도 트레이드오프 검토 후 적용

## 6. 적용된 수정 (2026-02-26)

- `ocr_twostage.py`: `ENG_ROI_MAX=20` 추가. eng 의심후보 20개 초과 시 2차 eng OCR 중단.
