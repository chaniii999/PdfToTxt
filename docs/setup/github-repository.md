# GitHub 저장소 만들기

PdfToTxt 프로젝트를 GitHub에 올리기 위한 단계입니다.

## 0. Git 사용자 이름·이메일 설정 (최초 1회)

커밋 시 "누가" 남겼는지 기록하기 위해, **한 번만** 아래를 설정합니다.  
(이미 설정했다면 생략해도 됩니다.)

```powershell
# 전역 설정 (이 PC의 모든 Git 저장소에 적용)
git config --global user.name "본인이름"
git config --global user.email "github에_등록한_이메일@example.com"
```

- **user.name**: GitHub 표시 이름 또는 원하는 이름 (예: `Hong Gildong`)
- **user.email**: GitHub 계정에 등록된 이메일을 쓰는 것이 좋습니다. (비공개 이메일 사용 시 GitHub에서 제공하는 `...@users.noreply.github.com` 도 가능)

**이 프로젝트에만** 다르게 쓰고 싶다면 `--global` 대신 프로젝트 폴더에서:

```powershell
cd c:\chan\repo\PdfToTxt
git config user.name "본인이름"
git config user.email "본인이메일@example.com"
```

설정 확인:

```powershell
git config --global user.name
git config --global user.email
```

## 1. GitHub에서 새 저장소 생성

1. [GitHub](https://github.com) 로그인 후 우측 상단 **+** → **New repository** 클릭.
2. 설정:
   - **Repository name**: `PdfToTxt` (또는 원하는 이름)
   - **Description**: (선택) 예: `의회문서 PDF → OCR → LLM 요약 파이프라인`
   - **Public** / **Private** 선택
   - **Add a README file**, **.gitignore**, **license**는 **체크하지 않음** (로컬에 이미 있음)
3. **Create repository** 클릭.
4. 생성된 페이지에서 **저장소 URL**을 복사합니다.
   - HTTPS: `https://github.com/<사용자명>/PdfToTxt.git`
   - SSH: `git@github.com:<사용자명>/PdfToTxt.git`

## 2. 로컬에서 Git 초기화 및 푸시

프로젝트 루트(`c:\chan\repo\PdfToTxt`)에서 터미널(PowerShell 또는 CMD)을 연 뒤 아래 순서대로 실행합니다.

```powershell
# 1) 프로젝트 폴더로 이동
cd c:\chan\repo\PdfToTxt

# 2) Git 저장소 초기화 (이미 되어 있으면 생략)
git init

# 3) 모든 파일 스테이징 (.gitignore 적용됨)
git add .

# 4) 첫 커밋
git commit -m "chore: GitHub 연동을 위해 저장소 초기화 및 프로젝트 기반 추가함"

# 5) 기본 브랜치 이름을 main으로 (필요 시)
git branch -M main

# 6) 원격 저장소 연결 (URL을 본인 저장소 주소로 바꿀 것)
git remote add origin https://github.com/<사용자명>/PdfToTxt.git

# 7) 푸시
git push -u origin main
```

- **이미 `git init`이 되어 있고 다른 원격(origin)이 있다면**  
  `git remote add origin ...` 대신 `git remote set-url origin https://github.com/<사용자명>/PdfToTxt.git` 로 주소만 바꿀 수 있습니다.
- **SSH를 쓰는 경우**  
  `https://github.com/...` 대신 `git@github.com:<사용자명>/PdfToTxt.git` 를 사용하면 됩니다.

## 3. 푸시 시 인증

- **HTTPS**: 푸시 시 GitHub 로그인 또는 Personal Access Token 입력이 필요할 수 있습니다.
- **SSH**: SSH 키를 GitHub에 등록해 두었다면 `git@github.com:...` 주소로 푸시할 때 별도 비밀번호 없이 동작합니다.

이후 작업은 `COMMIT_CONVENTION.md`의 커밋 규칙을 따라 진행하면 됩니다.
