# 의회 문서 OCR 최적화 명세서

## 1. 문서 구조 특징 (Target Layout)

- **다단 구조 (Multi-column)**: 한 페이지 내 좌/우 2단 분할 본문
- **계층적 번호 체계**: 1. → 가. → 1) → 가) 행정 문서 규칙
- **표(Table) 밀집**: 예산안, 통계 등 선(Line)이 많은 복잡한 표
- **폰트**: 바탕체, 명조체 등 세리프(Serif) 계열 (자간 좁음)

## 2. Tesseract 핵심 설정

| 항목 | 값 | 비고 |
|------|-----|------|
| lang | kor+eng | |
| oem | 3 | LSTM + Legacy 결합 (구조 파악) |
| psm | 3 | 자동 레이아웃 (2단 분리) |
| preserve_interword_spaces | 1 | 띄어쓰기 유지 |
| colseg_only_ascii | 0 | 한글 컬럼 분리 활성화 |
| textord_table_find | 1 | 표 영역 감지 |
| textord_min_linesize | 1.1 | 작은 노이즈 무시 |

## 3. 필수 전처리

| 항목 | 값 |
|------|-----|
| DPI | 300 고정 |
| Deskew | 0.5도 이상 시 보정 |
| Border | 10px 흰색 테두리 |
| Binarize | Gaussian Adaptive Threshold (Otsu 대비 스캔본 음영 대응) |

## 4. 후처리 보정 규칙

| 패턴 | 교정 | 비고 |
|------|------|------|
| O(대문자) | 0(숫자) | 예산안 숫자, 숫자 구간에서만 |
| I(대문자) | 1(숫자) | 숫자 구간에서만 |
| 7. (줄 시작) | 1. | 계층 번호 오인식 |
| ㄴㄴM | LLM | 영문 약어 |
| 시 | AI | 한글 우선으로 인한 영문 파괴 (문맥 의존) |

## 5. AI Agent 구현 팁

- **병렬 처리**: ProcessPoolExecutor로 페이지 단위 병합 (속도 4배)
- **tessdata_best**: `/usr/share/tesseract-ocr/5/tessdata_best` 등 Best 모델 권장
