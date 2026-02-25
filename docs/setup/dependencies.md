# 라이브러리 설정 이유

`requirements.txt`에 포함된 각 패키지를 선택한 이유와 역할을 정리합니다.

---

## API 서버

### FastAPI (`fastapi`)
- **이유**: 비동기 지원, 자동 OpenAPI 문서, 타입 힌트 기반 검증, 성능이 좋아서 API 서버로 사용.
- **역할**: PDF 업로드·OCR 실행·요약 요청 등 REST API 엔드포인트 제공. 의회문서 처리 요청을 받고 결과를 반환하는 진입점.

### Uvicorn (`uvicorn[standard]`)
- **이유**: ASGI 서버로 FastAPI가 권장하는 실행기. `[standard]`는 웹소켓·HTTP/2 등 추가 의존성 포함.
- **역할**: FastAPI 앱을 실제로 실행해 HTTP 요청을 처리. 개발·운영 모두 동일하게 사용 가능.

---

## PDF · 이미지

### PyMuPDF (`pymupdf`)
- **이유**: PDF를 페이지 단위로 이미지(픽셀)로 변환할 때 사용. `pdf2image`는 Poppler(OS별 별도 설치)가 필요해 Windows에서 설정이 번거로움. PyMuPDF는 추가 바이너리 없이 pip만으로 동작.
- **역할**: 의회문서 PDF(30~50페이지)를 페이지별로 열어서 래스터 이미지로 변환. 이 이미지를 Tesseract OCR에 넘김.

### Pillow (`Pillow`)
- **이유**: Python에서 가장 널리 쓰이는 이미지 처리 라이브러리. Tesseract 입력 전에 이미지 리사이즈·이진화·노이즈 제거 등 전처리에 필요.
- **역할**: OCR 인식률 개선을 위한 전처리(해상도 조정, 그레이스케일·이진화). PyMuPDF로 만든 이미지를 PIL Image로 다루기 쉬움.

---

## OCR (Tesseract)

### pytesseract (`pytesseract`)
- **이유**: Tesseract OCR 엔진의 Python 바인딩. 공개·무료이고 한글 지원이 가능해 의회문서 텍스트 추출에 적합.
- **역할**: 페이지 이미지에서 텍스트를 추출. 추출된 텍스트를 목차 파싱·섹션 분할 후 LLM 요약 단계로 전달.  
- **참고**: Tesseract 엔진과 한글 데이터(`kor.traineddata`)는 OS별로 별도 설치 필요. 이 패키지는 엔진을 “호출”만 함.

---

## 설정 · 환경

### pydantic-settings (`pydantic-settings`)
- **이유**: FastAPI와 같은 Pydantic 기반. 환경 변수·`.env`를 타입 안전하게 로드하고 검증할 수 있음.
- **역할**: Tesseract 경로, LLM API 키, 서버 포트 등 설정을 코드 밖(.env)에서 관리. 하드코딩 없이 환경별로 값만 바꿔 사용.

### python-dotenv (`python-dotenv`)
- **이유**: `.env` 파일을 읽어 `os.environ`에 넣어 주는 표준적인 방식. pydantic-settings와 함께 쓰면 로컬 개발 시 편함.
- **역할**: 프로젝트 루트의 `.env`를 로드해 환경 변수로 사용. API 키·경로 등을 버전 관리에 넣지 않고 로컬에서만 설정.

---

## LLM 요약

### httpx (`httpx`)
- **이유**: 비동기 HTTP 클라이언트. FastAPI와 같은 async 환경에서 LLM API 호출 시 블로킹 없이 사용 가능. `requests`는 동기 전용.
- **역할**: OpenAI 호환 API 또는 그 외 LLM API에 HTTP 요청. 섹션별 부분 요약·전체 요약 호출 시 사용.

### openai (`openai`)
- **이유**: OpenAI 공식 클라이언트. OpenAI API뿐 아니라 OpenAI 호환 API(다른 LLM 서비스)에도 사용 가능.
- **역할**: LLM에 “이 텍스트를 요약해 달라”는 요청을 보내고 응답을 파싱. 목차별 부분 요약 후 최종 전체 요약까지 같은 인터페이스로 처리.

---

## 요약 표

| 패키지 | 선택 이유 요약 | 프로젝트 내 역할 |
|--------|----------------|-------------------|
| fastapi | 비동기·타입·문서화·성능 | REST API 진입점 |
| uvicorn | FastAPI 권장 ASGI 서버 | 앱 실행·HTTP 처리 |
| pymupdf | Poppler 없이 PDF→이미지, Windows 친화 | 페이지별 이미지 변환 |
| Pillow | 표준적인 이미지 처리 | OCR 전처리 |
| pytesseract | Tesseract Python 연동 | 이미지 → 텍스트 추출 |
| pydantic-settings | 타입 안전 설정 관리 | 환경 변수·설정 로드 |
| python-dotenv | .env 로드 | 로컬 설정 분리 |
| httpx | 비동기 HTTP 클라이언트 | LLM API 비동기 호출 |
| openai | OpenAI·호환 API 클라이언트 | 부분/전체 요약 요청 |

테스트 추가 시 `pytest`, `pytest-asyncio`를 requirements에 넣어 사용하면 됩니다.
