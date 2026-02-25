"""tessdata_best 버전 검증. kor 12MB+, eng 4.7MB+ 권장."""

import os
import glob

MIN_KOR_MB = 10.0
MIN_ENG_MB = 4.5


def _find_tessdata_paths() -> list[str]:
    """tessdata 디렉터리 후보 경로 목록."""
    candidates = [
        "/usr/share/tesseract-ocr/5/tessdata",
        "/usr/share/tesseract-ocr/4.0/tessdata",
        "/usr/share/tesseract-ocr/4.00/tessdata",
        "/usr/share/tessdata",
        "/usr/local/share/tessdata",
    ]
    found = []
    for p in candidates:
        if os.path.isdir(p):
            found.append(p)
    # glob으로 tessdata 포함 경로 탐색
    for p in glob.glob("/usr/share/tesseract-ocr/*/tessdata"):
        if p not in found:
            found.append(p)
    return found


def verify_tessdata_best() -> tuple[bool, str]:
    """
    tessdata_best 사용 여부 검증.
    Returns: (통과 여부, 메시지)
    """
    paths = _find_tessdata_paths()
    if not paths:
        return False, "tessdata 디렉터리를 찾을 수 없음"

    kor_ok = False
    eng_ok = False
    details: list[str] = []

    for base in paths:
        kor_path = os.path.join(base, "kor.traineddata")
        eng_path = os.path.join(base, "eng.traineddata")

        if os.path.isfile(kor_path):
            size_mb = os.path.getsize(kor_path) / (1024 * 1024)
            kor_ok = size_mb >= MIN_KOR_MB
            details.append(f"kor: {size_mb:.1f}MB {'✓' if kor_ok else f'(권장 {MIN_KOR_MB}MB+)'}")
        if os.path.isfile(eng_path):
            size_mb = os.path.getsize(eng_path) / (1024 * 1024)
            eng_ok = size_mb >= MIN_ENG_MB
            details.append(f"eng: {size_mb:.1f}MB {'✓' if eng_ok else f'(권장 {MIN_ENG_MB}MB+)'}")
        if kor_ok and eng_ok:
            break

    if not details:
        return False, "kor.traineddata 또는 eng.traineddata를 찾을 수 없음"

    msg = "; ".join(details)
    if kor_ok and eng_ok:
        return True, f"tessdata_best 확인됨: {msg}"
    return False, f"tessdata_best 권장: {msg}. docs/ocr/setup-guide.md 참조"
