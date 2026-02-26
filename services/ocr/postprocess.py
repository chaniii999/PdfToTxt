"""Post-OCR 텍스트 정규화 파이프라인.

1. 오인식 패턴 치환 (자주 발생하는 wrong→right)
2. 사전 기반 보정 (typo_map.txt)
3. 금지 단어 패턴 탐지 (로깅/플래그)
"""

import logging
import re
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "postprocess"
_TYPO_MAP_PATH = _CONFIG_DIR / "typo_map.txt"
_PROHIBITED_PATH = _CONFIG_DIR / "prohibited_patterns.txt"


def _load_typo_map() -> list[tuple[str, str]]:
    """typo_map.txt 로드. wrong\tright. 긴 것 우선."""
    pairs: list[tuple[str, str]] = []
    if not _TYPO_MAP_PATH.exists():
        return pairs
    for line in _TYPO_MAP_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            wrong, right = line.split("\t", 1)
            if wrong and right:
                pairs.append((wrong.strip(), right.strip()))
    return sorted(pairs, key=lambda x: -len(x[0]))


def _load_prohibited_patterns() -> list[re.Pattern]:
    """금지 패턴 로드."""
    patterns: list[re.Pattern] = []
    if not _PROHIBITED_PATH.exists():
        return patterns
    for line in _PROHIBITED_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            patterns.append(re.compile(line))
        except re.error:
            logging.warning("postprocess: 잘못된 금지 패턴 무시: %s", line[:50])
    return patterns


# === 1. 오인식 패턴 치환 ===

def _merge_broken_syllables(text: str) -> str:
    """한글+줄바꿈/공백+한글 복원. 경\\n우 → 경우."""
    def repl(m: re.Match) -> str:
        left, right = m.group(1), m.group(3)
        return left + right if left != right else m.group(0)
    return re.sub(r"([가-힣])(\n|\s{2,})([가-힣])", repl, text)


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


_REGEX_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?<=\d)O(?=\d)"), "0"),
    (re.compile(r"(?<=\d)I(?=\d)"), "1"),
    (re.compile(r"^7\.", re.MULTILINE), "1."),
]


def _apply_stage1_patterns(text: str) -> str:
    """1단계: 오인식 패턴 치환 (기본 규칙 + regex)."""
    result = _remove_noise_lines(text)
    result = _merge_broken_syllables(result)
    for pattern, replacement in _REGEX_PATTERNS:
        result = pattern.sub(replacement, result)
    return _remove_noise_lines(result)


# === 2. 사전 기반 보정 ===

def _apply_stage2_dict(text: str, typo_map: list[tuple[str, str]]) -> str:
    """2단계: config/postprocess/typo_map.txt 기반 치환."""
    for wrong, right in typo_map:
        text = text.replace(wrong, right)
    return text


# === 3. 금지 단어 패턴 탐지 ===

def _apply_stage3_prohibited(text: str, patterns: list[re.Pattern]) -> tuple[str, list[str]]:
    """3단계: 금지 패턴 탐지. (텍스트, 탐지된 패턴 목록) 반환."""
    detected: list[str] = []
    for line in text.splitlines():
        for pat in patterns:
            if pat.search(line):
                detected.append(line[:80] + "..." if len(line) > 80 else line)
                break
    # 현재는 로깅만. 필요 시 마스킹/제거 로직 추가
    if detected:
        logging.debug("postprocess: 금지 패턴 탐지 %d건", len(detected))
    return text, detected


def correct_ocr_text(text: str) -> str:
    """Post-OCR 정제 파이프라인."""
    if not text or not text.strip():
        return text

    # 1. 오인식 패턴 치환
    result = _apply_stage1_patterns(text)

    # 2. 사전 기반 보정
    typo_map = _load_typo_map()
    result = _apply_stage2_dict(result, typo_map)

    # 3. 금지 패턴 탐지 (로깅)
    prohibited = _load_prohibited_patterns()
    result, _ = _apply_stage3_prohibited(result, prohibited)

    return result
