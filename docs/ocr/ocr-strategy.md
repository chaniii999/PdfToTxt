# OCR 인식 전략 문서 (AI Agent 보완용)

다른 AI agent가 OCR 품질 개선을 수행할 때 참고할 전략·구조·보완점 문서.

---

## 1. 프로젝트 개요

- **목적**: PDF(의회문서 30~50페이지) → 텍스트 추출. 이후 목차별 분할 → LLM 부분 요약 → 전체 요약 파이프라인으로 이어짐
- **대상 문서**: 한글 위주, 영문 약어·용어 혼재 (LLM, AI, PII, Hugging Face 등)
- **기술 스택**: Python, FastAPI, Tesseract 5, PyMuPDF(fitz), OpenCV, Pillow

---

## 2. 현재 파이프라인 흐름

```
PDF 업로드
    ↓
페이지별 순회
    ↓
scan_detect: 디지털 vs 스캔 판별
    ├─ PAGE_DIRECT → page.get_text("text") (직접 추출)
    └─ PAGE_OCR → _simple_ocr (후처리 없음, 인식률 우선)
```

### 2.1 스캔 판별 (scan_detect.py)

| 조건 | 결과 |
|------|------|
| 단어 10개 이상 + 텍스트 면적 5% 이상 + 평균 단어 길이 1.5 이상 + 이미지 면적 < 80% | `PAGE_DIRECT` (직접 추출) |
| 그 외 | `PAGE_OCR` (이미지 OCR) |

### 2.2 OCR 파이프라인 (_simple_ocr)

| 단계 | 입력 | Tesseract 호출 | 비고 |
|------|------|----------------|------|
| 0 | deskew 후 | - | 한글 특화: 10px 흰 테두리 추가 (`add_ocr_border`) |
| 1 | 원본 RGB | `image_to_string(lang, PSM 6)` | 전처리 없음 |
| 2 | Otsu 이진화 | PSM 6/4/3 | grayscale → Otsu, 다중 PSM 시도 |
| 3 | enhance | `image_to_string(lang, PSM 6)` | sharpen + CLAHE (점수 부족 시) |
| 4 | preset D/A/B/C | `image_to_string(lang, PSM 6)` | 한글 특화 D 우선, denoise/adaptive/morphology (점수 부족 시) |

- **선택 기준**: `길이 × (0.2 + 0.8×한글비율)` 최대값 (한글 오인식 Latin 억제)
- **조기 종료**: 점수 > 450이면 추가 시도 생략

---

## 3. 한글 OCR 특성 및 대응

### 3.1 한글 구조

- **자모 조합**: 52개 자모(초성·중성·종성) → 11,172개 완성형
- **특성**: 자모 경계가 뚜렷해야 정확한 글자 구분 가능. 끊긴 획·흐린 경계는 Latin 오인식 유발

### 3.2 자주 발생하는 오인식

| 한글 | Latin 오인식 | 비고 |
|------|--------------|------|
| ㅅ | s | 자모 유사 |
| ㅇ | O | 원형 |
| ㅁ | M | 사각형 |
| ㄴ | L, r | |
| kor+eng 혼용 | 한글을 Latin으로 읽는 경향 | Tesseract 한계 |

### 3.3 적용 전략

| 전략 | 구현 | 목적 |
|------|------|------|
| 테두리 추가 | `add_ocr_border(rgb, 10)` | 텍스트가 가장자리에 있을 때 인식 저하 방지 (Tesseract 권장) |
| DPI 350 | `_render_page(dpi=350)` | 글자 높이 20px 이상 확보, 11,172자 구분 |
| 한글 비율 가중 | `0.2 + 0.8×한글비율` | Latin 오인식 후보 억제, 한글 위주 선택 |
| sharpen(0.9) + CLAHE | `enhance_for_ocr` | 자모 경계 선명화 (한글 특화) |
| preset D | sharpen→CLAHE→Otsu→morph close | 한글 특화: 자모 경계 선명화 후 끊긴 획 연결 |
| morphology close | preset C, D | 끊긴 획 연결 (저대비/연한 글자) |

---

## 4. 주요 설정값

| 항목 | 값 | 위치 |
|------|-----|------|
| 언어 | `kor+eng` | `pdf_ocr.LANG` |
| PSM | `6` (블록), `4` (열), `3` (자동) | `pdf_ocr.PSM_*` |
| OEM | `3` (기본 LSTM) | `pdf_ocr.PSM_*` |
| DPI | 350 | `_render_page()` |
| 테두리 | 10px 흰색 | `preprocess.add_ocr_border` |
| Tesseract 경로 | `/usr/bin/tesseract` | `pdf_ocr.pytesseract.tesseract_cmd` |

---

## 5. 모듈 구조

```
services/ocr/
├── pdf_ocr.py       # 메인 파이프라인, _simple_ocr, extract_text_stream
├── scan_detect.py   # 디지털/스캔 판별
├── preprocess.py   # 전처리 (sharpen, CLAHE, preset A/B/C)
├── orientation.py  # Deskew (Hough), pdf_ocr 전단 적용
└── tessdata_check.py # tessdata_best 검증
```

---

## 6. 실측 인식률 (기준 문서)

| 구분 | 원본 | 추출 | 인식률 |
|------|------|------|--------|
| 한글 | 603자 | 560자 | **87.7%** |
| 영어 | 97자 | 52자 | **53.6%** |

- **영어 오인식 예**: AI→시, LLM→ㄴㄴ, PII→미, Self-Reflective Reliability→561([1-86[166119"6 861!1861111\, Hugging Face→허깅페미스대49109 6306)

---

## 7. 알려진 한계

1. **영어 인식률 낮음**: kor+eng 혼합 모드에서 영문 구간 오인식 다수
2. **한글 우선 선택**: `_score_candidate`가 한글 비율을 가중하므로, 영문이 많은 페이지에서 영문 품질이 희생될 수 있음
3. **image_to_data 미사용**: 한글에서 글자 단위 word 반환으로 띄어쓰기 깨짐 → `image_to_string`만 사용
4. **후처리 미사용**: 인식률 개선에 집중, 치환 로직 제거

---

## 8. 보완 요청 사항 (다음 AI Agent용)

### 8.1 영어 인식률 개선 (최우선)

- **현상**: LLM, AI, PII, Self-Reflective Reliability, Hugging Face, Read-Write Token 등 영문·약어 오인식
- **제약**: `image_to_data` 기반 word 재구성은 한글 띄어쓰기 이슈로 사용 불가 (improvement-log 참조)
- **요청**: kor+eng 단일 경로 유지 전제로, 영어 인식률 향상 방안 제안 및 구현

### 8.2 전처리/선택 로직 튜닝

- **위치**: `services/ocr/pdf_ocr.py` `_score_candidate`, `_simple_ocr`
- **요청**: 영문 비율이 높은 페이지에서도 품질이 나쁘지 않도록 선택 기준 재검토

### 8.3 tessdata 버전 확인

- **요청**: `tessdata_best` 사용 여부 확인 (kor 12 MB+, eng 4.7 MB+). fast 버전이면 교체 권장

---

## 9. 참고 문서

- `docs/ocr/ocr-pipeline.md`: **OCR 파이프라인 흐름** (단계별 처리 순서, 튜닝 참고)
- `docs/ocr/ocr-error-patterns.md`: **실측 오인식 패턴** (유형 A: 비슷한 글자 헷갈림, 유형 B: 한글→Latin 오인식)
- `docs/ocr/ocr-misrecognition-encyclopedia.md`: **오인식 백과사전** (한글↔Latin 형태 유사 쌍, 글자 단위)
- `docs/ocr/ocr-improvement-checklist.md`: **인식률 개선 체크리스트** (할 일 정리)
- `docs/ocr/improvement-log.md`: OCR 개선 이력, 교훈, 체크리스트
- `docs/ocr/setup-guide.md`: Tesseract 설치·설정
- `ocr_test.py`: 원본 vs 추출 인식률 계산 (한글/영어 분리)

---

## 10. 테스트 방법

```bash
# 인식률 계산 (원본 텍스트 vs OCR 결과)
python ocr_test.py "원본.txt" "추출.txt"

# API 서버 실행 후 PDF 업로드
uvicorn main:app --reload
# POST /ocr, multipart/form-data, file=xxx.pdf
```
