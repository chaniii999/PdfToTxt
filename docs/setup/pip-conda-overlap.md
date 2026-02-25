# pip vs conda 중복·충돌 점검

같은 환경에서 pip와 conda가 동시에 패키지를 설치하면 버전 충돌·의존성 꼬임이 발생할 수 있다.

---

## 1. py310 환경 현황 (WSL 기준)

py310에서는 **대부분 pip(pypi_0)** 로 설치되어 있어 conda/pip 중복은 거의 없다.
conda는 Python, openssl 등 시스템 라이브러리만 제공하고, 나머지는 pip로 설치된 상태.

---

## 2. conda·pip 둘 다 설치 가능한 패키지 (충돌 위험 순)

| 패키지 | 충돌 위험 | 이유 |
|--------|----------|------|
| **numpy** | 🔴 높음 | C 확장·ABI 호환. conda 2.3 vs pip 2.2 시 opencv/scipy 등 연쇄 오류 |
| **pillow** | 🔴 높음 | 이미지 바이너리. conda/pip 빌드가 달라 `ImportError` 가능 |
| **opencv-python-headless** | 🔴 높음 | numpy에 강하게 의존. numpy 충돌 시 바로 영향 |
| **pydantic** / **pydantic-core** | 🟡 중간 | FastAPI 의존. 마이너 버전 차이로 `ValidationError` 등 API 변경 |
| **pydantic-settings** | 🟡 중간 | pydantic과 버전 맞춰야 함 |
| **python-dotenv** | 🟢 낮음 | 순수 Python. 버전만 맞으면 대부분 호환 |
| **httpx** | 🟢 낮음 | 순수 Python |
| **setuptools** / **pip** / **wheel** | 🟡 중간 | 환경 관리 도구. conda가 관리하는 경우 pip로 덮어쓰면 꼬임 |
| **certifi** | 🟢 낮음 | 순수 Python |

---

## 3. py310에서 중복 시 충돌 가능성 있는 패키지 (요약)

**conda와 pip 둘 다 설치했을 때 문제되기 쉬운 패키지:**

```
numpy                    # C 확장, opencv/scipy 등 연쇄 의존
pillow                   # 이미지 바이너리
opencv-python-headless   # numpy 의존
pydantic                 # FastAPI 핵심
pydantic-core            # pydantic 내부
pydantic-settings        # pydantic 연동
setuptools / pip / wheel # 환경 관리
```

py310에서는 위 패키지가 모두 `pypi_0`(pip)로만 있어 현재는 충돌 없음.

---

## 4. 충돌 시 발생할 수 있는 현상

| 증상 | 원인 |
|------|------|
| `ImportError` / `ModuleNotFoundError` | pip가 conda 패키지를 덮어쓰거나, conda가 pip 패키지를 무시 |
| `AttributeError` | pydantic 등 마이너 버전 차이로 API 변경 |
| numpy 기반 라이브러리 오류 | numpy 2.2 vs 2.3 ABI 호환성 |
| `conda list`와 `pip list` 버전 불일치 | 같은 패키지가 두 설치 경로에 존재 |

---

## 5. 권장 원칙

**한 패키지는 한 쪽에서만 설치**

| 우선 | conda | pip |
|------|-------|-----|
| **conda** | numpy, scipy, opencv, pydantic 등 | — |
| **pip** | — | fastapi, uvicorn, pymupdf, pytesseract 등 |

**conda에 없는 패키지는 pip로 설치**

- fastapi, uvicorn, pymupdf, pytesseract, python-multipart 등은 conda 기본 채널에 없거나 구버전
- 이런 건 **pip**로 설치하는 게 맞음

**프로젝트 전용 환경은 pip만 사용**

- `py310` 같은 프로젝트용 env는 **pip만** 쓰고 conda 패키지 최소화
- `conda create -n py310 python=3.10` 후 `pip install -r requirements.txt`만 실행

---

## 6. 충돌 확인 방법 (WSL py310에서)

```bash
conda activate py310

# conda로 설치된 패키지 목록
conda list | grep -E "numpy|pillow|pydantic|python-dotenv|httpx"

# pip로 설치된 패키지 목록
pip list | grep -E "numpy|pillow|pydantic|python-dotenv|httpx"
```

**중복이 있으면** (같은 패키지가 conda list와 pip list 둘 다에 있으면):

- conda 쪽 제거: `conda remove numpy` 등
- pip로 통일: `pip install -r requirements.txt`

---

## 7. 요약

| 상황 | 조치 |
|------|------|
| py310 환경에서 프로젝트만 실행 | pip만 사용, conda 패키지 최소화 |
| `conda list`와 `pip list`에 같은 패키지가 둘 다 있음 | 한쪽만 남기기 (보통 pip 우선) |
| numpy/pydantic 관련 오류 | pip/conda 버전 충돌 의심 → 한쪽만 남기고 재설치 |
