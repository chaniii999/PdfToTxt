"""OCR 후처리: kor 단독 OCR 결과에서 영문 약어 오인식 치환."""

import re

TERM_CORRECTIONS: dict[str, str] = {
    "ALLM": "LLM",
    "AALLM": "LLM",
    "A|": "AI",
    "AS": "AI",
    "O|": "이",
    "|": "I",
    "LL M": "LLM",
    "AL L": "ALL",
    "GPT 4": "GPT-4",
    "GPT 5": "GPT-5",
    "AP |": "API",
    "AP|": "API",
    "UR L": "URL",
    "HT TP": "HTTP",
    "HT ML": "HTML",
    "JS ON": "JSON",
    "NL P": "NLP",
    "PD F": "PDF",
    "OC R": "OCR",
    "SS H": "SSH",
    "SS L": "SSL",
    "FA Q": "FAQ",
    "ㄴㄴ": "LLM",
    "&I": "AI",
    "Token'S": "Token'을",
    "LIM": "LLM",
    "(LIM)": "(LLM)",
    "(PI )": "(PII)",
    "(PI)": "(PII)",
}

# 괄호 안 영문 오인식 복원 (AI→시, LLM→ㄴㄴ, PII→미)
PAREN_MISREAD_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\(ㄴㄴ\)"), "(LLM)"),
    (re.compile(r"\(시\)"), "(AI)"),
    (re.compile(r"\(미\)"), "(PII)"),
]

# 문맥 기반 영문 복원 (접근하는 시는 → 접근하는 AI는)
CONTEXT_AI_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"접근하는 시는"), "접근하는 AI는"),
    (re.compile(r"생성형 시 "), "생성형 AI "),
]

PATTERN_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bA\s*[|l1]\b"), "AI"),
    (re.compile(r"\bL\s*L\s*M\b"), "LLM"),
    (re.compile(r"\bA\s*P\s*[|l1]\b"), "API"),
    (re.compile(r"\bG\s*P\s*T\b"), "GPT"),
    (re.compile(r"\bP\s*D\s*F\b"), "PDF"),
    (re.compile(r"\bO\s*C\s*R\b"), "OCR"),
    (re.compile(r"\bS\s*S\s*H\b"), "SSH"),
    (re.compile(r"\bH\s*T\s*T\s*P\b"), "HTTP"),
    (re.compile(r"\bU\s*R\s*L\b"), "URL"),
    (re.compile(r"\bN\s*L\s*P\b"), "NLP"),
]

PIPE_IN_KOREAN_RE = re.compile(r"(?<=[\uac00-\ud7a3])\|(?=[\uac00-\ud7a3])")


def correct_ocr_text(text: str) -> str:
    """OCR 결과 텍스트에서 흔한 오인식 패턴을 보정."""
    for wrong, right in TERM_CORRECTIONS.items():
        text = text.replace(wrong, right)

    for pattern, replacement in PAREN_MISREAD_PATTERNS:
        text = pattern.sub(replacement, text)

    for pattern, replacement in PATTERN_RULES:
        text = pattern.sub(replacement, text)

    text = PIPE_IN_KOREAN_RE.sub("", text)

    return text
