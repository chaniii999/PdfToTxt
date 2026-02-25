# WSL에서 Python 인터프리터 인식하기

에디터(Cursor/VS Code)가 WSL의 conda 환경(py310)을 인식하고, import 린트 오류 없이 정상적인 오류 검사를 하려면 **프로젝트를 WSL에서 열어야** 합니다.

---

## 1. WSL에서 폴더 열기

1. `Ctrl+Shift+P` → **"WSL: Reopen Folder in WSL"** 실행
2. 프로젝트가 WSL Ubuntu 환경에서 다시 열림

---

## 2. 인터프리터 선택

1. `Ctrl+Shift+P` → **"Python: Select Interpreter"**
2. 목록에서 **py310** (miniconda3) 선택
3. 또는 **"Enter interpreter path..."** → `/home/chani/miniconda3/envs/py310/bin/python` 입력

---

## 3. 왜 이렇게 해야 하나?

| 상황 | 린터 동작 |
|------|-----------|
| Windows에서 폴더 열기 + WSL Python 선택 | Windows 쪽에서 린터 실행 → WSL site-packages를 못 찾음 → "could not be resolved" |
| **WSL에서 폴더 열기** + WSL Python | 린터가 WSL에서 실행 → 패키지 인식 → 정상 오류 검사 |

---

## 4. 경로가 다를 때

miniconda3 경로가 `/home/chani/miniconda3`가 아니라면:

- `.vscode/settings.json`의 `python.defaultInterpreterPath`를 본인 환경에 맞게 수정
- 또는 WSL 터미널에서 `which python` (py310 활성화 후) 실행해 정확한 경로 확인
