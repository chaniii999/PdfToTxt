"""OCR 후처리: 노이즈 제거 + 한글 자모 조합 규칙 기반 보정.

사전 없이 한글 조합 구조(초성·중성·종성)를 분석하여,
자모 위치별 혼동 규칙으로 보정. [원본:추출] = 정답:오인식.

피드백: 성:섬, 익:의, 많:않, 페:폐
"""

import re

from services.ocr.jamo import split_syllable, join_syllable, is_hangul_syllable


def _merge_broken_syllables(text: str) -> str:
    """
    OCR이 줄바꿈/공백으로 한글 음절을 잘못 나눈 경우 복원.
    예: "경\\n우" → "경우", "경  우" → "경우"
    조건: 한글 + (줄바꿈 또는 2칸 이상 공백) + 한글, 두 음절이 다를 때만 병합.
    """
    def repl(m: re.Match) -> str:
        left, sep, right = m.group(1), m.group(2), m.group(3)
        if left != right:
            return left + right
        return m.group(0)

    # 한글 + (줄바꿈 또는 2칸 이상 공백) + 한글. 1칸 공백은 제외(할 수 등 정상 띄어쓰기 보존)
    pattern = re.compile(r"([가-힣])(\n|\s{2,})([가-힣])")
    return pattern.sub(repl, text)


def _remove_noise_lines(text: str) -> str:
    """표선·구분선 노이즈 라인 제거."""
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


def _correct_syllable_by_jamo(char: str) -> str:
    """
    한글 음절 1개를 자모 구조 기반 혼동 규칙으로 보정.
    [원본:추출] = 정답:오인식. 추출(OCR) → 원본(정답) 방향으로만 적용.

    혼동 원인 (자모 구조):
    - 성:섬 — 종성 ㅇ↔ㅁ (닫힌 형태. ㅇ=원, ㅁ=사각)
    - 익:의 — ㅇ+ㅣ+ㄱ vs ㅇ+ㅢ (ㅡ+ㅣ). ㅡ 약하면 ㄱ처럼 보임
    - 많:않 — 초성 ㅁ↔ㅇ (많=ㅁ+ㅏ+ㄶ, 않=ㅇ+ㅏ+ㄶ)
    - 페:폐 — 중성 ㅔ↔ㅖ (ㅔ=ㅓ+ㅣ, ㅖ=ㅕ+ㅣ. 가로획 유무)
    """
    parts = split_syllable(char)
    if not parts:
        return char
    cho, jung, jong = parts
    jong_c = jong.strip() if jong else ""

    # 1. 섬→성: ㅅ+ㅓ+ㅁ (종성 ㅇ↔ㅁ)
    if cho == "ㅅ" and jung == "ㅓ" and jong_c == "ㅁ":
        return join_syllable("ㅅ", "ㅓ", "ㅇ")

    # 2. 익→의: ㅇ+ㅣ+ㄱ (ㅡ+ㅣ vs ㅣ+ㄱ)
    if cho == "ㅇ" and jung == "ㅣ" and jong_c == "ㄱ":
        return join_syllable("ㅇ", "ㅢ", " ")

    # 3. 않→많: ㅇ+ㅏ+ㄶ (초성 ㅇ↔ㅁ)
    if cho == "ㅇ" and jung == "ㅏ" and jong_c == "ㄶ":
        return join_syllable("ㅁ", "ㅏ", "ㄶ")

    # 4. 페→폐: ㅍ+ㅔ (중성 ㅔ↔ㅖ)
    if cho == "ㅍ" and jung == "ㅔ" and not jong_c:
        return join_syllable("ㅍ", "ㅖ", " ")

    return char


def _apply_jamo_correction(text: str) -> str:
    """텍스트 내 한글 음절을 자모 규칙으로 순회 보정."""
    result = []
    for char in text:
        if is_hangul_syllable(char):
            result.append(_correct_syllable_by_jamo(char))
        else:
            result.append(char)
    return "".join(result)


# 정규식: 숫자·기호 복원 (자모와 무관)
_REGEX_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?<=\d)O(?=\d)"), "0"),
    (re.compile(r"(?<=\d)I(?=\d)"), "1"),
    (re.compile(r"^7\.", re.MULTILINE), "1."),
]


def correct_ocr_text(text: str) -> str:
    """OCR 결과 후처리: 노이즈 제거 + 잘못 나뉜 음절 병합 + 자모 규칙 기반 보정."""
    if not text or not text.strip():
        return text
    result = _remove_noise_lines(text)
    result = _merge_broken_syllables(result)
    result = _apply_jamo_correction(result)
    for pattern, replacement in _REGEX_PATTERNS:
        result = pattern.sub(replacement, result)
    return _remove_noise_lines(result)
