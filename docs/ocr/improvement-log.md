# OCR 개선 이력 로그

프로젝트 전반에 걸쳐 OCR 품질·안정성·성능을 개선한 내용을 시간순으로 기록한다.
미니프로젝트 적용 시 이 로그를 참고하여 동일 이슈를 빠르게 해결할 것.

---

## 2026-02-25 | 한글 획 구분·한글 우선 가중치

- **배경**: 한글(기업, 보호, 자기 등)이 영문(JHA, BSE, DEE)으로 오인식
- **전처리**: Sharpen(자모 경계 선명화), Morphology close(끊긴 획 연결)
- **Tesseract**: language_model_penalty_non_dict_word=0.25, non_freq_dict_word=0.2
- **후처리**: JHA→기업, BSE→보호, DEE→자기, REHM→과정, SEAN→하드웨어, 20→보안/로그
- **문서**: `kor-eng-misrecognition-analysis.md`

---

## 2026-02-25 | 단일 열 문서 최적화 (PSM 6)

- **배경**: 실제 문서 확인 결과 단일 열, 2단 아님
- **PSM 6**: PSM 3 블록 순서 이슈 회피
- **kor+eng**: 영문 약어(Self-Reflective, PII, Hugging Face 등) 인식
- **노이즈 라인 제거**: `=`, `—`만 있는 줄 후처리에서 제거
- **kor+eng 실패 시 kor 폴백**

---

## 2026-02-25 | diff 분석 기반 품질 개선

- **원인**: image_to_data level 미필터, 전처리 누락, 표선 노이즈
- **image_to_data**: level==5(단어)만 사용, 표선 노이즈 블록("=", "—" 등) 필터
- **preprocess_minimal**: Gaussian Blur, Adaptive Threshold(11, C=2), 10px 흰 테두리, Deskew 0.5°
- **postprocess**: ㄴㄴM→LLM, 허깅 페미스→Hugging Face 패턴 추가
- **참고**: `diff-analysis-2026-02-25.md`

---

## 2026-02-25 | kor/eng 분리 2단 OCR

- **목표**: kor+eng 간섭 제거로 영문 인식률 향상
- **1단계**: kor 전용 `image_to_data`로 블록별 좌표·신뢰도 파악
- **2단계**: conf < 60 또는 ASCII 비율 ≥ 60% 영역만 crop
- **3단계**: crop 영역만 eng 전용 재인식 후 병합
- **파일**: `pdf_ocr.py`에 2단 OCR 로직 통합

---

## 2026-02-25 | OCR 후처리 (오탈자사전) 추가

- **postprocess.py**: 오인식→정답 매핑 사전 + 정규식 패턴
- **데이터 출처**: ocr-error-patterns, 실측 비교 데이터
- **적용**: _simple_ocr 결과에 `correct_ocr_text` 적용 (OCR 경로만)
- **매핑 예**: 0!!→PII, ㄴㄴ→LLM, 표준만→표준안, 개민→개인, 민증→인증 등

---

## 2026-02-25 | B 요원 감사 보고서 반영

- **90/180/270도 회전 보정**: `correct_orientation_rgb` 파이프라인 삽입 (render 직후)
- **Tesseract 경로**: `TESSERACT_CMD` 환경변수 지원, dotenv 로드
- **tessdata 미달**: 경고 메시지 강화, `TESSERACT_REQUIRE_BEST` 시 tessdata 미달이면 OCR 중단
- **예외 처리**: `pytesseract.TesseractError` 분리, 로깅 추가
- **crop_document_region**: crop_ratio < 0.5 시 crop_border 폴백 (과소 영역 방지)

---

## 2026-02-25 | OCR 속도 개선 — 정확도 상승 부수효과

- **early stop**: 400 → 450. enhance·preset 생략 확대 → 페이지당 ~10초 단축
- **PSM 13 제거**: 1차 후보 5개 → 4개. Tesseract 1회 감소
- **실측**: 한글 83.9%→89.2%, 영어 43.3%→64.9%. 속도 개선과 함께 정확도도 상승
- **가설**: enhance·preset이 일부 페이지에서 과처리로 품질 저하. early stop 450으로 1차 후보만 선택하는 쪽이 유리했을 가능성

---

## 2026-02-25 | 인식률 개선 체크리스트 적용

- **sharpen**: preset D, enhance_for_ocr 0.9 → 1.0. 자모 경계 선명화 강화
- **CLAHE**: enhance_for_ocr clip_limit 2.5 → 3.0
- **early stop**: 450 → 400 (이후 450으로 복원, 속도 우선)
- **PSM 13**: 추가 후 제거 (속도 우선)
- **DPI**: 350 유지

---

## 2026-02-25 | 한글 특화 OCR 개선

- **enhance_for_ocr**: sharpen 0.7 → 0.9. 자모 경계 선명화로 ㅇ/ㅁ, ㅈ/ㅅ 등 혼동 완화
- **preset D 추가**: 한글 특화. sharpen(0.9) → CLAHE → Otsu → morphology close. 자모 경계 선명화 후 끊긴 획 연결
- **후보 순서**: preset D를 A/B/C보다 먼저 시도 (한글 8:영어 2 문서에 유리)
- **문서**: `ocr-strategy.md` preset D, sharpen 0.9 반영

---

## 2026-02-25 | 미사용 코드 정리

- **삭제**: `lang_split.py`, `layout.py`, `table_ocr.py`, `quality_gate.py`, `postprocess.py`
- **이유**: pdf_ocr 파이프라인에서 미참조. 코드베이스 단순화

---

## 2026-02-25 | 인식률 개선 집중 — 후처리 제거, 전처리·PSM 확장

- **후처리 제거**: `correct_ocr_text` 호출 제거. 인식률 개선에 집중
- **DPI 350**: 300 → 350. 소형 글자 인식 개선
- **PSM 확장**: PSM 4(단일 열), PSM 3(자동) 추가 후보
- **전처리 확장**: preset B, C 추가. enhance + preset A/B/C 모두 시도 후 최고 점수 선택
- **조기 종료**: 점수 450 초과 시 추가 시도 생략

---

## 2026-02-25 | OCR 품질 개선 (기술 지시서 반영)

- **tessdata_best 검증**: `tessdata_check.py` 추가. kor 10MB+, eng 4.5MB+ 확인. 미달 시 경고 로그 + NDJSON `tessdata_ok`/`tessdata_msg` 반환
- **_score_candidate 고도화**: 영문 핵심어(LLM, AI, PII, API 등) 포함 시 키워드당 +25점 가산. 한글비율 중심에서 영문 보존 반영
- **Deskew 재삽입**: `orientation.deskew_rgb()` 적용. I, L, 1 오인식 완화 목적. OCR 전단에 Hough deskew
- **후처리 패턴 확장**: `(ㄴㄴ)`→`(LLM)`, `(시)`→`(AI)`, `(미)`→`(PII)`, `ㄴㄴ`→`LLM`, `&I`→`AI` 추가

---

## 2026-02-25 | 한글/영어 분리 처리 (lang_split) — 비활성화

- **배경**: kor+eng 혼합 모드에서 영어 구간 오인식 다수 (AI→시, LLM→ㄴㄴ, PII→미 등). 영어 인식률 ~54%
- **조치**: `lang_split.py` 모듈 추가. kor/kor+eng 1차 → 영어 블록 감지 → eng 재처리 → 병합
- **결과**: 실측에서 한글 94%→34%, 영어 5%→0%로 품질 악화. 영어 블록 오판·병합 순서 이슈로 판단
- **롤백**: `pdf_ocr.py`에서 lang_split 비활성화. 기존 `_simple_ocr(kor+eng)` 단일 경로로 복귀
- **교훈**: word_data 기반 재구성은 한글 띄어쓰기·순서 이슈에 취약. 영어 블록 감지 정확도 개선 필요

---

## 2026-02-23 | 기본 OCR 파이프라인 구축

- **작업**: PDF → 이미지 렌더링(300 DPI) → Tesseract `image_to_string` → 텍스트 반환
- **구성**: PyMuPDF(`fitz`)로 페이지 렌더링, `pytesseract`로 OCR, FastAPI `StreamingResponse`로 NDJSON 스트리밍
- **설정**: `lang=kor+eng`, `--psm 6 --oem 3`, DPI 300
- **결과**: 디지털 PDF는 정상, 스캔본은 품질 불량

---

## 2026-02-23 | 디지털 PDF vs 스캔본 분기 처리 (scan_detect)

- **현상**: 디지털 PDF(텍스트 레이어 있음)도 이미지 OCR을 거쳐 품질 저하
- **원인**: 모든 페이지를 일괄 OCR 처리
- **조치**: `scan_detect.py` 모듈 추가. 페이지별로 단어 수(`get_text("words")`), 텍스트 면적 비율, 이미지 면적 비율을 분석하여 `PAGE_DIRECT`(직접 추출) vs `PAGE_OCR`(이미지 OCR) 분기
- **판별 기준**: 단어 10개 이상 + 텍스트 면적 5% 이상 + 평균 단어 길이 1.5 이상 → 직접 추출
- **효과**: 디지털 PDF는 `page.get_text()`로 깨끗한 텍스트, OCR은 스캔 페이지에만 적용

---

## 2026-02-23 | 스캔본 특화 전처리 파이프라인 구축

- **작업**: 스캔 문서의 OCR 품질 향상을 위한 다단계 전처리
- **구성 모듈**:
  - `preprocess.py`: 프리셋 A/B/C 이진화 (adaptive gaussian / CLAHE+adaptive / CLAHE+Otsu+morphology), 외곽 crop, 적응형 denoise
  - `orientation.py`: Tesseract OSD로 회전(0/90/180/270) 감지 + Hough 변환 deskew(±15도)
  - `layout.py`: 선 기반(Track 1) + 텍스트박스 기반(Track 2) 표/텍스트 영역 감지
  - `table_ocr.py`: 표 선 제거 후 셀 OCR + 텍스트박스 기반 마크다운 재구성 폴백
  - `quality_gate.py`: confidence 기반 품질 평가 + PSM/프리셋 변경 재시도
- **파이프라인**: 렌더 → grayscale → crop → 회전 보정 → deskew → 이진화 → 레이아웃 분석 → 영역별 OCR → 품질 게이트

---

## 2026-02-24 | 서버 크래시 수정 — TesseractError 에러 방어

- **현상**: PDF 업로드 시 서버 크래시, 프론트에서 "업로드중..." 멈춤
- **원인**: `layout.py` Track 2의 `image_to_data` 호출에서 `TesseractError: (-2, '')` 발생. 에러 처리 없어서 서버 프로세스 종료
- **조치**:
  - `layout.py`: Track 2 (`_find_table_regions_by_textbox`)에 `try/except` 추가
  - `table_ocr.py`: 셀 OCR, 폴백 경로에 `try/except` 추가
  - `pdf_ocr.py`: 페이지별 `try/except` — 한 페이지 실패해도 다른 페이지 계속 처리
  - `orientation.py`: OSD 감지 시 이미지 크기 검증 + PIL 변환
- **교훈**: Tesseract 외부 프로세스 호출은 항상 예외 처리 필수

---

## 2026-02-24 | 품질 게이트 재시도 과다 → 최대 3회 제한

- **현상**: OCR 처리가 극도로 느림 (페이지당 수십 초~분)
- **원인**: `quality_gate.py`에서 PSM 4개 × 프리셋 3개 = **12 조합**, 각각 `image_to_data` + `image_to_string` = **24회 Tesseract 호출** (한 텍스트 영역당)
- **조치**: 재시도 계획을 고정 3개로 제한 (PSM 6+A → PSM 6+B → PSM 4+A). `image_to_string` 별도 호출 제거
- **효과**: Tesseract 호출 횟수 최대 3회로 감소, 처리 속도 대폭 개선

---

## 2026-02-24 | 이미지 3중 crop 버그 수정 — 외계어 출력 해결

- **현상**: OCR 결과가 "ro ol 42 rr 119 미노 qo Fo mal" 같은 외계어
- **원인**: 이미지가 3번 crop됨
  1. `_ocr_page`에서 `crop_document_region()` 1차
  2. `preprocess_for_ocr()` 내부에서 2차 (함수 안에 crop 포함)
  3. 영역별 OCR에서 region crop 후 `preprocess_for_ocr()` 호출로 3차
  - Otsu 이진화 후 컨투어 탐지가 텍스트 블록 하나만 잡아서 나머지 다 잘려나감
- **조치**: `binarize()` 함수 신설 (crop 없이 이진화만 수행). `_ocr_page`에서 crop은 최초 1회만, 이후는 `binarize()`만 호출
- **교훈**: 전처리 함수가 내부에 crop을 포함하면, 호출 체인에서 다중 crop이 발생할 수 있음. crop과 이진화는 반드시 분리

---

## 2026-02-24 | 한 글자씩 띄어쓰기 문제 — image_to_data → image_to_string 전환

- **현상**: "본 표 준 만 은 2026 년 고 도 화 된" — 모든 글자 사이에 공백
- **원인**: `image_to_data`가 한글 각 글자를 개별 word로 반환. 이를 `" ".join()`으로 이어붙여서 글자마다 공백 삽입
- **조치**: 텍스트 추출을 `image_to_string`으로 전환. Tesseract가 자체 단어 그룹핑한 결과를 그대로 사용. `image_to_data`는 confidence 평가에만 사용
- **교훈**: 한국어 OCR에서 `image_to_data`의 word 단위 텍스트는 띄어쓰기가 깨짐. 텍스트 출력은 `image_to_string` 사용할 것

---

## 2026-02-24 | 과도한 전처리 제거 — "Less is more" 전략 채택

- **현상**: 복잡한 파이프라인(orientation → deskew → denoise → binarize → layout → region OCR)이 오히려 이미지를 망침
- **원인**: 각 전처리 단계가 글자를 뭉개거나 배경과 합치는 부작용. 특히 깨끗한 스캔본에서 불필요한 처리가 품질 저하 유발
- **조치**: OCR 파이프라인을 대폭 단순화
  - 1차: 원본 RGB 이미지 → `image_to_string` (전처리 없음)
  - 2차(텍스트 부족 시): grayscale + Otsu 이진화 → `image_to_string`
  - 3차(2차보다 나쁠 시): PSM 3(자동) 시도
  - 최대 Tesseract 호출 3회
- **교훈**: Tesseract는 깨끗한 이미지에서 가장 잘 동작함. 전처리는 원본이 안 될 때만 적용. 복잡한 파이프라인이 항상 좋은 것은 아님

---

## 2026-02-24 | 스트리밍 진행바 안 뜨는 문제 — sync → async generator 전환

- **현상**: 프론트에서 "업로드중..." 상태로 10초간 멈춘 후 결과가 한번에 표시
- **원인**: sync generator의 yield가 버퍼링되어 클라이언트에 즉시 전송 안 됨
- **조치**: `extract_text_stream`을 async generator로 변경. 각 페이지 yield 후 `await asyncio.sleep(0)`으로 event loop에 제어를 넘겨 즉시 flush
- **효과**: 페이지 처리 완료 시마다 진행바가 실시간 업데이트

---

## 2026-02-24 | tessdata 학습 데이터 교체 (1.6 MB → 12 MB)

- **현상**: 학습 데이터 교체 전에도 외계어 수준의 인식 결과
- **원인**: Ubuntu 패키지 매니저가 설치한 `kor.traineddata`가 **1.6 MB** (극도로 축소된 버전). `tessdata_best`는 약 12~20 MB
- **조치**: GitHub `tessdata_best` 저장소에서 한국어·영어 학습 데이터 교체
  ```bash
  sudo wget -O /usr/share/tesseract-ocr/5/tessdata/kor.traineddata \
    https://github.com/tesseract-ocr/tessdata_best/raw/main/kor.traineddata
  sudo wget -O /usr/share/tesseract-ocr/5/tessdata/eng.traineddata \
    https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata
  ```
- **결과**: `kor.traineddata` 1.6 MB → 12 MB (7.5배), `eng.traineddata` 4.0 MB → 4.7 MB
- **교훈**: Tesseract 설치 후 반드시 `tessdata_best` 버전으로 교체할 것. 파일 크기로 fast/best 구분 가능

---

## 2026-02-24 | kor 단독 OCR + 영문 약어 후처리 치환

- **현상**: `kor+eng` 동시 사용 시 한글/영문 혼동 발생. "(LLM)" → "ALLM)O|", "AI" → "A|" 또는 "AS" 등
- **원인**: Tesseract가 두 스크립트를 동시 로드하면 비슷한 형태의 글자를 다른 스크립트로 오인식. 특히 `|`와 `I`, 한글 모음과 영문 글자 사이에서 혼동 빈번
- **조치**:
  1. OCR 언어를 `kor+eng` → **`kor` 단독**으로 변경. 한글 인식 정확도 우선
  2. `postprocess.py` 모듈 신설 — OCR 결과에 후처리 적용:
     - **고정 치환 테이블**: `ALLM→LLM`, `A|→AI`, `AP|→API` 등 자주 틀리는 약어 매핑
     - **정규식 패턴**: 글자 사이 공백이 끼어든 약어 복원 (`L L M→LLM`, `A P I→API` 등)
     - **한글 사이 파이프 제거**: `한|글` → `한글` (한글 문맥에서 `|`는 거의 오인식)
  3. `pdf_ocr.py`에서 OCR 결과에 `correct_ocr_text()` 적용
- **후속**: `kor` 단독 사용 시 영문이 숫자로 변환되는 부작용 확인. `kor+eng`로 복원하되 `tessdata_best`(12 MB) + 후처리 조합으로 운용. `tessdata_best` 적용 전에는 혼동이 심했으나 학습 데이터 교체 후 크게 개선
- **교훈**: `kor` 단독은 영문이 아예 없는 문서에만 유효. 영문 약어가 포함된 문서는 `kor+eng` + 후처리가 최선. 핵심은 학습 데이터 품질(`tessdata_best`)이며, 후처리 패턴은 실제 오인식 사례를 수집하며 점진적으로 추가할 것

---

## 2026-02-25 | 기본 OCR 인식률 개선 (전처리·선택 로직)

- **목적**: 후처리 치환 대신 Tesseract 기본 인식 품질 향상
- **조치**:
  1. **preprocess.py**: `sharpen()`, `enhance_contrast_clahe()`, `enhance_for_ocr()` 추가
  2. **pdf_ocr.py**: 선택 기준 `길이 × (0.4 + 0.6×한글비율)` 적용
  3. **속도 최적화**: Tesseract 호출 최대 4회로 축소. 점수 350 초과 시 조기 종료. DPI 300 유지

---

## 적용 시 체크리스트 (미니프로젝트용)

### 환경 설정
- [ ] Tesseract 설치 후 **`tessdata_best`** 버전 학습 데이터 교체 (kor 12 MB+, eng 4.7 MB+)
- [ ] `pytesseract.tesseract_cmd` 경로를 환경에 맞게 설정 (또는 `.env`로 관리)
- [ ] Python 3.10+, OpenCV headless, PyMuPDF, Pillow 설치

### OCR 파이프라인
- [ ] 디지털 PDF / 스캔본 자동 분기 (scan_detect)
- [ ] 1차 시도: 원본 이미지 그대로 `image_to_string`
- [ ] 2차 시도: grayscale + Otsu 이진화 (1차 결과가 부족할 때만)
- [ ] 텍스트 추출은 `image_to_string` 사용 (`image_to_data`는 한글 띄어쓰기 깨짐)
- [ ] OCR 언어는 `kor+eng` + `tessdata_best` 조합 사용 (영문 포함 문서 기준)
- [ ] 후처리 미사용 (인식률 우선 전략)
- [ ] Tesseract 호출에는 반드시 `try/except` 적용

### 프론트/API
- [ ] NDJSON 스트리밍으로 페이지별 진행 표시
- [ ] async generator + `await asyncio.sleep(0)`으로 실시간 flush
- [ ] 페이지별 에러 발생 시 건너뛰고 계속 처리 (전체 중단 금지)
