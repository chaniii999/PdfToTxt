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
    └─ PAGE_OCR → _simple_ocr → correct_ocr_text
```

### 2.1 스캔 판별 (scan_detect.py)

| 조건 | 결과 |
|------|------|
| 단어 10개 이상 + 텍스트 면적 5% 이상 + 평균 단어 길이 1.5 이상 + 이미지 면적 < 80% | `PAGE_DIRECT` (직접 추출) |
| 그 외 | `PAGE_OCR` (이미지 OCR) |

### 2.2 OCR 파이프라인 (_simple_ocr)

| 단계 | 입력 | Tesseract 호출 | 비고 |
|------|------|----------------|------|
| 1 | 원본 RGB | `image_to_string(lang, PSM 6)` | 전처리 없음 |
| 2 | Otsu 이진화 | `image_to_string(lang, PSM 6)` | grayscale → Otsu |
| 3 | enhance | `image_to_string(lang, PSM 6)` | sharpen + CLAHE (점수 부족 시) |
| 4 | preset A | `image_to_string(lang, PSM 6)` | denoise + adaptive 이진화 (점수 부족 시) |
| 5 | Otsu | `image_to_string(lang, PSM 3)` | PSM 자동 (최종 폴백) |

- **선택 기준**: `길이 × (0.4 + 0.6×한글비율)` 최대값
- **조기 종료**: 점수 > 350이면 추가 시도 생략
- **최대 호출**: 5회 (실제로는 2~5회)

### 2.3 후처리 (postprocess.py)

- 고정 치환: `ALLM→LLM`, `A|→AI`, `LL M→LLM` 등
- 정규식: `\bL\s*L\s*M\b` → `LLM` 등
- 한글 사이 파이프 제거: `한|글` → `한글`

---

## 3. 주요 설정값

| 항목 | 값 | 위치 |
|------|-----|------|
| 언어 | `kor+eng` | `pdf_ocr.LANG` |
| PSM | `6` (블록), `3` (자동) | `pdf_ocr.PSM_*` |
| OEM | `3` (기본 LSTM) | `pdf_ocr.PSM_*` |
| DPI | 300 | `_render_page()` |
| Tesseract 경로 | `/usr/bin/tesseract` | `pdf_ocr.pytesseract.tesseract_cmd` |

---

## 4. 모듈 구조

```
services/ocr/
├── pdf_ocr.py       # 메인 파이프라인, _simple_ocr, extract_text_stream
├── scan_detect.py   # 디지털/스캔 판별
├── preprocess.py   # 전처리 (sharpen, CLAHE, preset A/B/C)
├── postprocess.py  # 후처리 치환 (영문 약어, 괄호 안 오인식)
├── orientation.py  # Deskew (Hough), pdf_ocr 전단 적용
├── tessdata_check.py # tessdata_best 검증
├── lang_split.py   # [비활성화] 한글/영어 분리 처리
├── layout.py       # 표/텍스트 영역 감지 (현재 pdf_ocr에서 미사용)
├── table_ocr.py    # 표 OCR (현재 pdf_ocr에서 미사용)
├── quality_gate.py # 품질 게이트 (현재 pdf_ocr에서 미사용)
└── orientation.py  # 회전/deskew (현재 pdf_ocr에서 미사용)
```

- **실제 사용**: `pdf_ocr`, `scan_detect`, `preprocess`, `postprocess`만 활성
- **미사용**: `layout`, `table_ocr`, `quality_gate`, `orientation` — 과거 복잡 파이프라인 잔재

---

## 5. 실측 인식률 (기준 문서)

| 구분 | 원본 | 추출 | 인식률 |
|------|------|------|--------|
| 한글 | 603자 | 560자 | **87.7%** |
| 영어 | 97자 | 52자 | **53.6%** |

- **영어 오인식 예**: AI→시, LLM→ㄴㄴ, PII→미, Self-Reflective Reliability→561([1-86[166119"6 861!1861111\, Hugging Face→허깅페미스대49109 6306)

---

## 6. 알려진 한계

1. **영어 인식률 낮음**: kor+eng 혼합 모드에서 영문 구간 오인식 다수
2. **한글 우선 선택**: `_score_candidate`가 한글 비율을 가중하므로, 영문이 많은 페이지에서 영문 품질이 희생될 수 있음
3. **image_to_data 미사용**: 한글에서 글자 단위 word 반환으로 띄어쓰기 깨짐 → `image_to_string`만 사용
4. **lang_split 비활성화**: 한글/영어 분리 처리 시도했으나 한글 94%→34%, 영어 5%→0%로 악화되어 롤백

---

## 7. 보완 요청 사항 (다음 AI Agent용)

### 7.1 영어 인식률 개선 (최우선)

- **현상**: LLM, AI, PII, Self-Reflective Reliability, Hugging Face, Read-Write Token 등 영문·약어 오인식
- **제약**: `image_to_data` 기반 word 재구성은 한글 띄어쓰기 이슈로 사용 불가 (improvement-log 참조)
- **요청**: kor+eng 단일 경로 유지 전제로, 영어 인식률 향상 방안 제안 및 구현

### 7.2 lang_split 재검토 (선택)

- **위치**: `services/ocr/lang_split.py` (현재 비활성)
- **이슈**: 영어 블록 감지(conf/Latin 휴리스틱) 부정확, word_data 기반 병합 시 한글 순서·띄어쓰기 깨짐
- **요청**: image_to_string 결과를 베이스로 유지하면서, 특정 영역만 eng로 재처리·치환하는 방식 검토

### 7.3 후처리 패턴 확장

- **위치**: `services/ocr/postprocess.py`
- **요청**: 실제 오인식 사례 수집 후 `TERM_CORRECTIONS`, `PATTERN_RULES`에 추가. 과도한 패턴은 오탐 위험

### 7.4 전처리/선택 로직 튜닝

- **위치**: `services/ocr/pdf_ocr.py` `_score_candidate`, `_simple_ocr`
- **요청**: 영문 비율이 높은 페이지에서도 품질이 나쁘지 않도록 선택 기준 재검토

### 7.5 tessdata 버전 확인

- **요청**: `tessdata_best` 사용 여부 확인 (kor 12 MB+, eng 4.7 MB+). fast 버전이면 교체 권장

---

## 8. 참고 문서

- `docs/ocr/improvement-log.md`: OCR 개선 이력, 교훈, 체크리스트
- `docs/ocr/setup-guide.md`: Tesseract 설치·설정
- `ocr_test.py`: 원본 vs 추출 인식률 계산 (한글/영어 분리)

---

## 9. 테스트 방법

```bash
# 인식률 계산 (원본 텍스트 vs OCR 결과)
python ocr_test.py "원본.txt" "추출.txt"

# API 서버 실행 후 PDF 업로드
uvicorn main:app --reload
# POST /ocr, multipart/form-data, file=xxx.pdf
```
