# kor/eng 분리 2단 OCR 전략

kor+eng 동시 사용 시 발생하는 간섭(Interference)을 제거하고, 영문 인식률을 비약적으로 상승시키는 고급 기법.

## 개요

| 단계 | 내용 |
|------|------|
| **1단계** | kor 전용 + `image_to_data`로 텍스트 좌표·신뢰도 파악 |
| **2단계** | 신뢰도 낮거나 영문 의심 영역만 crop |
| **3단계** | crop된 영역만 eng 전용으로 재인식 |
| **효과** | kor+eng 간섭 제거 → 영문 인식률 향상 |

## 동작 흐름

```
전처리 이미지
    → pytesseract.image_to_data(lang=kor)  # 블록별 좌표, conf, text
    → 필터: conf < 60 OR ASCII 비율 ≥ 60%
    → 해당 블록 crop (8px 패딩)
    → pytesseract.image_to_string(lang=eng)  # crop별 eng 전용
    → 원본 kor 결과에서 해당 블록만 eng 결과로 치환
    → 병합
```

## 설정

| 항목 | 기본값 | 설명 |
|------|--------|------|
| `CONF_THRESHOLD` | 60 | 이하면 eng 재인식 대상 |
| `ENG_ASCII_RATIO` | 0.6 | ASCII 비율 이 이상이면 영문 의심 |
| `CROP_PADDING` | 8 | crop 시 여유 px |
| `HYBRID_OCR` | 1 | env: 0이면 기존 kor 단일 모드 |

## 파일

- `services/ocr/hybrid_ocr.py`: 2단 OCR 로직
- `services/ocr/pdf_ocr.py`: `HYBRID_OCR` 시 `ocr_page_hybrid` 호출

## 비활성화

```bash
HYBRID_OCR=0 python main.py
```

또는 `.env`에 `HYBRID_OCR=0` 설정.
