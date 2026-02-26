# OCR 프로세스 검토 보고서 (B 요원)

**작성자**: Cursor B 요원 (프로젝트 사전 지식 없음)  
**검토 대상**: PdfToTxt OCR 파이프라인 전체  
**검토 일**: 2026-02-25

---

## 1. 프로세스 개요 요약

PDF 업로드 → 페이지별 scan_detect(디지털/스캔 판별) → 스캔본: render(350 DPI) → deskew → 테두리 추가 → 다중 후보(rgb, otsu×3 PSM) Tesseract 호출 → 점수 기반 최적 선택 → 점수≤450 시 enhance·preset 4종 추가 시도

---

## 2. 치명적 이슈

### 2.1 90/180/270도 회전 보정 미적용

`orientation.py`에 `detect_orientation`, `correct_orientation` 함수가 있으나 **파이프라인에서 호출되지 않음**.  
현재는 Hough 기반 `deskew_rgb`(±15도 미세 기울기)만 적용됨.

**영향**: 스캔본이 90도·180도·270도 회전된 경우 OCR이 거의 실패함.  
**권장**: render 직후 `correct_orientation` 또는 Tesseract OSD 기반 회전 보정을 파이프라인에 삽입.

### 2.2 Tesseract 경로 하드코딩 

`pdf_ocr.py` 27행: `pytesseract.tesseract_cmd = "/usr/bin/tesseract"`

**영향**: Windows, macOS, Docker 등 다른 환경에서 실행 시 경로 불일치로 오류 발생.  
**권장**: 환경변수 또는 `config`에서 읽어오도록 변경.

### 2.3 tessdata 미달 시 경고만 수행

`verify_tessdata_best()`가 실패해도 **경고 로그만 남기고 OCR은 계속 진행**됨.

**영향**: fast 버전(1.6MB kor 등) 사용 시 인식률이 크게 떨어지는데, 사용자는 원인 파악이 어려움.  
**권장**: tessdata 미달 시 OCR 실행을 중단하거나, 명시적 경고/에러 반환을 고려.

---

## 3. 개선 필요

### 3.1 예외 처리 과다

`_ocr_string`에서 `except Exception`으로 모든 예외를 잡아 빈 문자열 반환.  
Tesseract 프로세스 실패, 메모리 부족 등 실제 오류가 숨겨질 수 있음.

**권장**: `TesseractError` 등 구체적 예외 처리 후, 나머지는 로깅 후 재발생시키거나 별도 처리.

### 3.2 preprocess_for_ocr의 crop_document_region

preset D/A/B/C에서 `crop_document_region`으로 문서 영역만 잘라 사용.  
컨투어 탐지가 텍스트 블록 하나만 잡으면 **나머지 영역이 잘려나** improvement-log에 기록된 3중 crop 버그와 유사한 위험이 있음.

**권장**: crop 실패 시 전체 이미지 사용 또는 crop 비활성화 옵션 검토.

### 3.3 API 업로드 크기 제한 없음

`api/ocr.py`에서 업로드 파일 크기 제한이 없음.  
대용량 PDF(수십 MB) 업로드 시 메모리·처리 시간 이슈 가능.

### 3.4 미사용 함수

- `orientation.detect_orientation`, `correct_orientation` — 정의만 있음
- `preprocess.binarize_for_ocr_no_crop` — 정의만 있음

**권장**: 사용 계획이 없으면 제거하거나, 사용처를 명확히 문서화.

---

## 4. 기존 상식과 다른 점

### 4.1 image_to_data 미사용

일반적으로 Tesseract confidence, bbox 등으로 품질 평가·후처리에 `image_to_data`를 많이 사용함.  
이 프로젝트는 **`image_to_string`만 사용**.

**이유**: improvement-log에 따르면 한글에서 `image_to_data`의 word 단위 반환이 띄어쓰기를 깨뜨림.  
**판단**: 문서화된 합리적 선택. 단, 문서에 명시해 두는 것이 좋음.

### 4.2 후처리 없음

일반 OCR 파이프라인에서는 후처리(오타 교정, 패턴 치환)를 많이 사용함.  
이 프로젝트는 **후처리 미사용**.

**이유**: improvement-log에 따르면 인식률 우선 전략으로 후처리 제거.  
**판단**: 전략적 선택. 단, LLM→ㄴㄴ, PII→0!! 등 오인식은 여전히 남음.

### 4.3 점수 기반 후보 선택

여러 전처리·PSM 조합을 돌리고 **텍스트 길이×한글비율**로 점수화해 최적 결과를 선택하는 방식.

**특이점**: 실제 OCR 품질 지표(confidence, edit distance 등)가 아닌 휴리스틱 점수 사용.  
**판단**: 문서화된 실험 결과(early stop 450 등)에서 개선 효과가 있었음. 다만, 점수 공식이 문서에 명확히 남아 있어야 함.

### 4.4 회전 보정: OSD 대신 Hough만 사용

Tesseract OSD로 0/90/180/270도 회전을 감지하는 기능이 있으나, **파이프라인에는 Hough deskew만** 사용됨.

**판단**: 90도 회전 문서는 처리되지 않음. 치명적 이슈 2.1과 동일.

---

## 5. 권장 조치 우선순위

| 우선순위 | 항목 | 유형 | 적용 |
|----------|------|------|------|
| 1 | 90/180/270도 회전 보정 파이프라인 삽입 | 치명적 | ✅ correct_orientation_rgb 삽입 |
| 2 | Tesseract 경로 환경변수/설정화 | 치명적 | ✅ TESSERACT_CMD 환경변수 |
| 3 | tessdata 미달 시 경고 강화 또는 오류 반환 | 치명적 | ✅ TESSERACT_REQUIRE_BEST 옵션, 경고 메시지 강화 |
| 4 | 예외 처리 구체화 | 개선 | ✅ TesseractError 분리, 로깅 |
| 5 | 미사용 함수 정리 또는 문서화 | 개선 | - |
| 6 | crop_document_region 실패 시 폴백 검토 | 개선 | ✅ crop_ratio < 0.5 시 crop_border 폴백 |

---

## 6. 참고

- `docs/ocr/improvement-log.md`: 과거 시도·교훈
- `docs/ocr/ocr-strategy.md`: 전략·설정
- `docs/ocr/ocr-performance-analysis.md`: 성능 분석
