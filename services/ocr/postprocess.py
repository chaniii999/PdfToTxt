"""OCR 후처리: 노이즈 라인 제거만. 자모 치환 비활성화(한글 손상 이슈)."""


def _remove_noise_lines(text: str) -> str:
    """표선·구분선 노이즈 라인 제거 (=, —, | 만 있는 줄)."""
    lines = text.splitlines()
    kept = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            kept.append(line)
            continue
        if all(c in "=—|-|· \t" for c in stripped):
            continue
        kept.append(line)
    return "\n".join(kept)


def correct_ocr_text(text: str) -> str:
    """OCR 결과 후처리. 현재는 노이즈 라인 제거만."""
    if not text or not text.strip():
        return text
    return _remove_noise_lines(text)
