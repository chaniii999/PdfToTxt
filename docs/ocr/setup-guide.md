# OCR 환경 설정 가이드

새 프로젝트에서 Tesseract OCR을 빠르게 세팅하기 위한 단계별 가이드.
각 단계를 순서대로 밟으면 한글+영문 혼합 문서 OCR이 바로 동작한다.

---

## Step 1. Tesseract 설치

### Ubuntu / WSL

```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-kor
```

### 설치 확인

```bash
tesseract --version
# tesseract 5.x.x 이상이면 OK
```

---

## Step 2. 학습 데이터 교체 (필수)

기본 설치 시 포함된 학습 데이터는 축소 버전(1~4 MB)이라 인식률이 매우 낮다.
**반드시 `tessdata_best`로 교체할 것.**

### tessdata 경로 확인

```bash
ls -lh /usr/share/tesseract-ocr/*/tessdata/kor.traineddata
```

### best 버전 다운로드

```bash
# 한국어 (12 MB+)
sudo wget -O /usr/share/tesseract-ocr/5/tessdata/kor.traineddata \
  https://github.com/tesseract-ocr/tessdata_best/raw/main/kor.traineddata

# 영어 (4.7 MB+)
sudo wget -O /usr/share/tesseract-ocr/5/tessdata/eng.traineddata \
  https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata
```

> **경로 주의**: Tesseract 버전에 따라 `/5/` 부분이 `/4.00/` 등 다를 수 있음. `ls`로 먼저 확인.

### 교체 확인

```bash
ls -lh /usr/share/tesseract-ocr/5/tessdata/kor.traineddata
# 12M 이상이면 best 버전

ls -lh /usr/share/tesseract-ocr/5/tessdata/eng.traineddata
# 4.7M 이상이면 best 버전
```

### 크기 기준표

| 종류 | kor | eng |
|------|-----|-----|
| 패키지 기본 (사용 금지) | ~1.6 MB | ~4.0 MB |
| `tessdata_fast` | ~11 MB | ~4.0 MB |
| **`tessdata_best` (권장)** | **~12 MB** | **~4.7 MB** |

---

## Step 3. Python 라이브러리 설치

```bash
pip install pytesseract Pillow PyMuPDF opencv-python-headless numpy
```

| 라이브러리 | 역할 |
|-----------|------|
| `pytesseract` | Tesseract Python 바인딩 |
| `Pillow` | 이미지 객체 변환 (Tesseract 입력) |
| `PyMuPDF` (`fitz`) | PDF → 이미지 렌더링 |
| `opencv-python-headless` | 이진화, 노이즈 제거 등 전처리 |
| `numpy` | 이미지 배열 처리 |

---

## Step 4. Tesseract 경로 설정

코드에서 Tesseract 실행 파일 경로를 명시한다.

```python
import pytesseract

# Linux / WSL
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# Windows (직접 설치한 경우)
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

> **권장**: 하드코딩 대신 환경변수(`TESSERACT_CMD`)나 `.env`로 관리.

### 경로를 모를 때

```bash
which tesseract          # Linux / WSL
where tesseract.exe      # Windows
```

---

## Step 5. 기본 OCR 테스트

```python
from PIL import Image
import pytesseract

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

img = Image.open("test_scan.png")
text = pytesseract.image_to_string(img, lang="kor+eng", config="--psm 6 --oem 3")
print(text)
```

정상 동작하면 다음 단계로.

---

## Step 6. 권장 OCR 설정값

| 설정 | 권장값 | 설명 |
|------|--------|------|
| `lang` | `kor+eng` | 한글+영문 혼합 문서 |
| `--psm` | `6` (단일 블록) 또는 `3` (자동) | 문서 레이아웃에 따라 선택 |
| `--oem` | `3` (LSTM 기본) | 한글에 LSTM이 가장 유리 |
| DPI | `300` | Tesseract 권장. 과도한 DPI는 속도만 저하 |

### PSM 모드 참고

| PSM | 설명 | 용도 |
|-----|------|------|
| 3 | 자동 페이지 분할 | 레이아웃이 복잡할 때 |
| 4 | 가변 크기 단일 컬럼 | 다단 문서 |
| 6 | 균일한 텍스트 블록 | 일반 문서 (기본 추천) |
| 7 | 한 줄 텍스트 | 짧은 영역 |
| 11 | 희소 텍스트 | 텍스트가 드문드문할 때 |

---

## Step 7. PDF → OCR 파이프라인

### 디지털 PDF / 스캔본 분기

```
PDF 페이지
  ├─ 텍스트 레이어 있음 (단어 10개+) → page.get_text() 직접 추출
  └─ 텍스트 없음/부족 → 이미지 렌더링 → Tesseract OCR
```

- `PyMuPDF`의 `page.get_text("words")`로 단어 수, 텍스트 면적 비율 확인
- 디지털 PDF는 OCR 없이 직접 추출이 훨씬 빠르고 정확함

### OCR 순서 (스캔본)

```
1차: 원본 RGB 이미지 → image_to_string (전처리 없음)
  ├─ 텍스트 충분 (20자+) → 완료
  └─ 텍스트 부족 ↓
2차: grayscale + Otsu 이진화 → image_to_string
  ├─ 1차보다 나음 → 완료
  └─ 아직 부족 ↓
3차: PSM 3 (자동 분할) 시도 → 완료
```

### 핵심 원칙

- **텍스트 추출은 `image_to_string`** 사용. `image_to_data`는 한글 각 글자를 개별 word로 반환해서 띄어쓰기가 깨짐
- **전처리는 최소한만**. Tesseract는 깨끗한 이미지에서 가장 잘 동작. 과도한 전처리(denoise, adaptive threshold 등)가 오히려 품질 저하 유발
- **Tesseract 호출은 반드시 `try/except`로 감싸기**. 외부 프로세스 실행이라 다양한 에러 발생 가능

---

## Step 8. 후처리 (영문 약어 보정)

`kor+eng` 사용 시 한글/영문 혼동이 발생할 수 있다. OCR 결과에 후처리를 적용한다.

### 주요 오인식 패턴

| 원본 | 오인식 | 원인 |
|------|--------|------|
| AI | A\| 또는 AS | \|와 I 혼동 |
| LLM | ALLM | A가 붙음 |
| API | AP\| | \|와 I 혼동 |
| 이 | O\| | 한글 → 영문+기호 |
| SSH | 55H | S와 5 혼동 |

### 후처리 구현

```python
import re

CORRECTIONS = {
    "ALLM": "LLM",
    "A|": "AI",
    "AP|": "API",
}

PATTERNS = [
    (re.compile(r"\bA\s*[|l1]\b"), "AI"),
    (re.compile(r"\bL\s*L\s*M\b"), "LLM"),
    (re.compile(r"\bA\s*P\s*[|l1]\b"), "API"),
]

# 한글 사이의 | 는 오인식
PIPE_IN_KOREAN = re.compile(r"(?<=[\uac00-\ud7a3])\|(?=[\uac00-\ud7a3])")

def correct_ocr_text(text: str) -> str:
    for wrong, right in CORRECTIONS.items():
        text = text.replace(wrong, right)
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    text = PIPE_IN_KOREAN.sub("", text)
    return text
```

> 실제 오인식 사례를 수집하며 `CORRECTIONS`와 `PATTERNS`를 점진적으로 추가한다.

---

## Step 9. (선택) 특정 글꼴로 Fine-tuning

의회문서 등 글꼴이 정해진 문서를 주로 처리한다면, 해당 글꼴로 Tesseract를 추가 학습시켜 인식률을 높일 수 있다.

### 준비

```bash
# tesstrain, langdata 클론
git clone https://github.com/tesseract-ocr/tesstrain.git
git clone https://github.com/tesseract-ocr/langdata_lstm.git

# 글꼴 디렉터리 생성
mkdir -p ~/fonts
```

### 글꼴 수집

```bash
# WSL에서 Windows 글꼴 복사
cp /mnt/c/Windows/Fonts/malgun*.ttf ~/fonts/     # 맑은 고딕
cp /mnt/c/Windows/Fonts/batang.ttc ~/fonts/      # 바탕체

# 나눔 글꼴 (설치 안 되어 있으면)
sudo apt install fonts-nanum
cp /usr/share/fonts/truetype/nanum/*.ttf ~/fonts/

# 설치된 한글 글꼴 확인
fc-list :lang=ko
```

### 훈련 데이터 생성

```bash
cd tesstrain/src
python -m tesstrain \
  --langdata_dir ~/langdata_lstm \
  --linedata_only \
  --fonts_dir ~/fonts \
  --lang kor \
  --maxpages 50 \
  --save_box_tiff \
  --distort_image \
  --fontlist "Malgun Gothic" "NanumMyeongjo" "Batang" \
  --output_dir ~/train_kor
```

### Fine-tuning 실행

```bash
# 기존 모델에서 LSTM 추출
combine_tessdata -e /usr/share/tesseract-ocr/5/tessdata/kor.traineddata ~/kor.lstm

# fine-tuning (30분~2시간)
lstmtraining \
  --continue_from ~/kor.lstm \
  --model_output ~/kor_custom \
  --traineddata /usr/share/tesseract-ocr/5/tessdata/kor.traineddata \
  --train_listfile ~/train_kor/kor.training_files.txt \
  --max_iterations 2000
```

### 커스텀 모델 적용

```bash
# traineddata 파일 생성
lstmtraining \
  --stop_training \
  --continue_from ~/kor_custom_checkpoint \
  --traineddata /usr/share/tesseract-ocr/5/tessdata/kor.traineddata \
  --model_output ~/kor_custom.traineddata

# Tesseract에 배치
sudo cp ~/kor_custom.traineddata /usr/share/tesseract-ocr/5/tessdata/
```

### 코드에서 사용

```python
LANG = "kor_custom+eng"  # 커스텀 한국어 + 영어
```

---

## 트러블슈팅 빠른 참조

| 증상 | 원인 | 해결 |
|------|------|------|
| 외계어 출력 | tessdata가 축소 버전 (1~4 MB) | `tessdata_best`로 교체 |
| 한 글자씩 띄어쓰기 | `image_to_data` 사용 | `image_to_string`으로 변경 |
| 서버 크래시 | Tesseract 호출 에러 미처리 | `try/except` 추가 |
| 영문이 숫자로 변환 | `kor` 단독 사용 | `kor+eng` 사용 |
| 한글/영문 혼동 (AI→A\|) | 스크립트 혼동 | 후처리 치환 패턴 적용 |
| 처리 극도로 느림 | OCR 재시도 과다 | 재시도 최대 3회 제한 |
| 진행바 안 뜸 | sync generator 버퍼링 | async generator + `sleep(0)` |
| 이미지 잘려서 인식 불량 | 전처리에서 다중 crop | crop은 1회만, 이진화와 분리 |

---

## 전체 체크리스트

### 환경

- [ ] Tesseract 5.x 설치
- [ ] `tessdata_best` 교체 (kor 12 MB+, eng 4.7 MB+)
- [ ] `pytesseract.tesseract_cmd` 경로 설정
- [ ] Python 3.10+, pytesseract, Pillow, PyMuPDF, OpenCV headless, numpy 설치

### OCR 파이프라인

- [ ] 디지털 PDF / 스캔본 자동 분기
- [ ] 1차: 원본 이미지 → `image_to_string`
- [ ] 2차: Otsu 이진화 (1차 부족 시만)
- [ ] `kor+eng` + `tessdata_best` 조합
- [ ] 후처리(`postprocess`) 적용
- [ ] Tesseract 호출에 `try/except` 적용

### API/스트리밍

- [ ] NDJSON 스트리밍으로 페이지별 진행 표시
- [ ] async generator + `await asyncio.sleep(0)`
- [ ] 페이지별 에러 시 건너뛰고 계속 처리

### (선택) 품질 강화

- [ ] 특정 글꼴 fine-tuning
- [ ] 후처리 패턴 지속 수집·추가
