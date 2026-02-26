"""OCR 후처리: 오탈자사전 기반 오인식 치환."""

import re
from typing import Sequence

# 오인식 → 정답 매핑 (ocr-misrecognition-encyclopedia, ocr-error-patterns, 실측 데이터 기반)
# 긴 패턴을 먼저 적용하려면 길이 내림차순 정렬
OCR_TYPO_MAP: dict[str, str] = {
    # 영문 약어
    "0!!": "PII",
    "| !": "PII",
    "민|": "PII",
    "ㄴㄴ": "LLM",
    "Z(LM)CI": "LLM",
    "Z(LM)": "LLM",
    "Z2AKAA": "킬스위치",
    "ZARA": "킬스위치",
    "2AAXI": "킬스위치",
    "Al": "AI",
    "Sel f-Reflective": "Self-Reflective",
    "Bead-Write": "Read-Write",
    "10<60": "Token",
    "Token@": "Token",
    # 한글 오인식 (ㅇ↔ㅁ, ㅈ↔ㅅ 등)
    "표준만": "표준안",
    "먼어": "언어",
    "천반메": "전반",
    "척용": "적용",
    "수뭘섬": "수월성",
    "만전": "안전",
    "개민": "개인",
    "파민튜닝": "파인튜닝",
    "가줌치": "가중치",
    "소정": "조정",
    "기먹": "기억",
    "기먹메서": "기억에서",
    "민증": "인증",
    "말고리즘": "알고리즘",
    "밤식": "방식",
    "감제": "강제",
    "부재예": "부재에",
    "경우메도": "경우에도",
    "데이터메": "데이터에",
    "즉각적민": "즉각적인",
    "암호화되며야": "암호화되어야",
    "접근 제여": "접근 제어",
    "위변소": "위변조",
    "블록체민": "블록체인",
    # 한글→Latin 오인식
    "MIE": "신뢰성",
    "REE": "답변",
    "AZO": "스스로",
    "BATE": "확신",
    "FEE": "정보",
    "dF": "성찰",
    "LAE": "감사",
    "DEY": "모델",
    "B29": "모델",
    "ASE": "인증",
    "stg": "학습",
    "쿨가": "불가",
    "Md": "생성",
    "과정예서": "과정에서",
    "메커니즘몰": "메커니즘을",
    "의샤결정": "의사결정",
    "민종": "인종",
    "겸무": "경우",
    "모널": "모델은",
    "2150": "인류의",
    "보만": "보안",
    "가이드라민": "가이드라인",
    "S32": "전원을",
    "Us": "독립적",
    "허깅페미스대409109": "허깅페이스",
    "812 H 0l A": "허깅페이스",
    "228": "발급한",
    "모는": "모든",
    "및힐": "잊힐",
    # 글자(음절) 단위 오인식 (encyclopedia ㅈ↔ㅅ 정↔청, 사↔샤, 감↔같 등)
    "청보": "정보",
    "같사": "감사",
    "의샤": "의사",
    "적민": "적인",
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
