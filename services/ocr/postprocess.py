"""OCR 후처리: 오탈자사전 기반 오인식 치환."""

import re
from typing import Sequence

# 오인식 → 정답 매핑 (ocr-misrecognition-encyclopedia, ocr-error-patterns, 실측 데이터 기반)
# 긴 패턴을 먼저 적용하려면 길이 내림차순 정렬
OCR_TYPO_MAP: dict[str, str] = {
    # 영문 약어
    "0!!": "PII",
}

# 정규식 패턴 (단어 경계, 공백 삽입 등)
OCR_TYPO_PATTERNS: Sequence[tuple[re.Pattern, str]] = (
    (re.compile(r"\bAl\b"), "AI"),
    (re.compile(r"0!!"), "PII"),
    (re.compile(r"\|\s*!"), "PII"),
    (re.compile(r"L\s*L\s*M"), "LLM"),
    (re.compile(r"Read-Write\s+10<60"), "Read-Write Token"),
    (re.compile(r"Read-Write\s+Token@"), "Read-Write Token"),
    (re.compile(r"de\s+보호"), "권익 보호"),
    (re.compile(r"MH\s+가치"), "상위 가치"),
)


def _build_sorted_replacements() -> list[tuple[str, str]]:
    """긴 패턴 우선 적용을 위해 (오인식, 정답) 리스트 반환."""
    return sorted(OCR_TYPO_MAP.items(), key=lambda x: -len(x[0]))


def correct_ocr_text(text: str) -> str:
    """오탈자사전 기반 OCR 결과 후처리."""
    if not text or not text.strip():
        return text

    result = text
    for wrong, correct in _build_sorted_replacements():
        if wrong in result:
            result = result.replace(wrong, correct)

    for pattern, replacement in OCR_TYPO_PATTERNS:
        result = pattern.sub(replacement, result)

    return result
