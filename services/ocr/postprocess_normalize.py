"""Post-OCR 세그먼트 파손 복구 정규화.

줄/토큰 파손 복원, 괄호 내부 정제, 영문 약어 복구.
규칙 테이블 기반, 외부 API 없음, diff 로그 출력.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

# === 설정 ===
CHANGE_RATIO_LIMIT = 0.05  # 라인당 변경 5% 초과 시 가드레일

# === 패턴 (규칙에서 사용) ===
BULLET_PATTERN = re.compile(r"^\s*[·∙•]\s*$", re.MULTILINE)
PAREN_INNER = re.compile(r"\(([^()]*)\)")
EN_EN_BREAK = re.compile(r"(?<=[A-Za-z])\s*\n\s*(?=[A-Za-z])")


@dataclass
class DiffEntry:
    """diff 로그 항목."""

    rule_id: str
    before: str
    after: str
    line_id: int | None = None
    confidence: float | None = None


@dataclass
class NormalizeRule:
    """정규화 규칙 정의."""

    rule_id: str
    description: str
    condition: str
    example: str
    apply_fn: Callable[[str], str]


# === 규칙 적용 함수들 ===


def _apply_nfc(text: str) -> str:
    """NFC 정규화. 자모 분리 문제 선제 해결."""
    return unicodedata.normalize("NFC", text)


# OCR이 공백을 ·(U+00B7)로 오인식하는 패턴. 단어 사이 · → 공백
SPACE_DOT_PATTERN = re.compile(
    r"([가-힣A-Za-z0-9])\s*[·∙]\s*([가-힣A-Za-z0-9])"
)


def _fix_space_dot(text: str) -> str:
    """단어 사이 ·(중점)를 공백으로 치환. OCR 공백 오인식 보정."""
    def repl(m: re.Match) -> str:
        return m.group(1) + " " + m.group(2)

    prev = ""
    while prev != text:
        prev = text
        text = SPACE_DOT_PATTERN.sub(repl, text)
    return text


def _remove_bullet_lines(text: str) -> str:
    """단독 기호/불릿 라인 제거."""
    lines = text.split("\n")
    kept = [line for line in lines if not BULLET_PATTERN.match(line)]
    return "\n".join(kept)


def _merge_kr_kr_breaks(text: str) -> str:
    """한글-한글 사이 불필요한 줄바꿈 제거. 1~2글자 조각만 병합(스스로, 기억, 차단)."""
    lines = text.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            result.append(line)
            i += 1
            continue
        if re.match(r"^[가-힣]{1,2}$", stripped) and i + 1 < len(lines):
            next_stripped = lines[i + 1].strip()
            if next_stripped and re.match(r"^[가-힣]+$", next_stripped):
                chunk = [stripped]
                j = i + 1
                while j < len(lines) and lines[j].strip():
                    s = lines[j].strip()
                    if re.match(r"^[가-힣]{1,2}$", s):
                        chunk.append(s)
                        j += 1
                    else:
                        break
                if len(chunk) >= 2:
                    result.append("".join(chunk))
                    i = j
                    continue
        result.append(line)
        i += 1
    return "\n".join(result)


def _merge_en_en_breaks(text: str) -> str:
    """영문-영문 사이 줄바꿈 제거. L\\nL\\nM -> LLM."""
    def repl(_m: re.Match) -> str:
        return ""
    return EN_EN_BREAK.sub(repl, text)


def _merge_en_en_spaces(text: str) -> str:
    """영문 단어 내부 공백 제거. Sel f-Ref lective -> Self-Reflective."""
    tokens = re.split(r"(\s+)", text)
    result = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if re.match(r"^\s+$", t):
            space = t
            if i + 1 < len(tokens):
                next_tok = tokens[i + 1]
                if re.match(r"^[A-Za-z\-]+$", next_tok):
                    prev = result[-1] if result else ""
                    if prev and re.match(r"[A-Za-z\-]+$", prev):
                        prev_ends_alpha = bool(re.search(r"[A-Za-z]$", prev))
                        next_short = len(next_tok) <= 3
                        next_lower = next_tok[0].islower() if next_tok else False
                        if prev_ends_alpha and (next_short or next_lower):
                            result.append(next_tok)
                            i += 2
                            continue
            result.append(space)
            i += 1
        else:
            result.append(t)
            i += 1
    return "".join(result)


# 약어 복구: LLeMm -> LLM 등 (괄호 내부)
ACRONYM_MAP = {
    "LLeMm": "LLM", "LLeM": "LLM", "Llm": "LLM",
    "Lem": "LLM", "Lemm": "LLM",  # L↔e 시각 혼동
}


def _fix_paren_content(text: str) -> str:
    """괄호 내부 파손 복구: 줄바꿈/공백 제거, OCR 유사문자 치환."""

    def repl(m: re.Match) -> str:
        inner = m.group(1)
        inner = re.sub(r"[\s\n]+", "", inner)
        inner = inner.replace("|", "I")
        inner = re.sub(r"0(?=[A-Za-z])", "O", inner)
        inner = re.sub(r"(?<=[A-Za-z])0", "O", inner)
        inner = ACRONYM_MAP.get(inner, inner)
        if len(inner) >= 3 and re.match(r"^[A-Za-z]+$", inner):
            upper = sum(1 for c in inner if c.isupper())
            if upper >= len(inner) - 1:
                inner = inner.upper()
        return "(" + inner + ")"

    return PAREN_INNER.sub(repl, text)


# AI→| 오인식: "편향 감사: | 모델" → "편향 감사: AI 모델"
PIPE_TO_AI = re.compile(r":\s*\|(\s*모델)")


def _fix_pipe_to_ai(text: str) -> str:
    """콜론 뒤 단독 | 를 AI로. (AI→| OCR 오인식)."""
    def repl(m: re.Match) -> str:
        return ": AI" + m.group(1)
    return PIPE_TO_AI.sub(repl, text)


def _fix_ocr_similar_in_en(text: str) -> str:
    """영문 비율 60%+ 토큰에서 OCR 유사문자 치환. 줄 구조 유지."""

    def fix_token(t: str) -> str:
        non_space = [c for c in t if not c.isspace()]
        if not non_space:
            return t
        alpha_digit = sum(1 for c in non_space if c.isalnum())
        if alpha_digit / len(non_space) < 0.6:
            return t
        t = t.replace("·", "")
        t = re.sub(r"(?<=[A-Za-z])\|(?=[A-Za-z])", "I", t)
        return t

    lines = text.split("\n")
    return "\n".join(
        " ".join(fix_token(w) for w in line.split()) for line in lines
    )


# === 규칙 테이블 ===
RULES: list[NormalizeRule] = [
    NormalizeRule(
        rule_id="nfc",
        description="NFC 유니코드 정규화",
        condition="항상 적용",
        example="자모 분리 한글 → NFC 결합형",
        apply_fn=_apply_nfc,
    ),
    NormalizeRule(
        rule_id="space_dot_fix",
        description="단어 사이 ·(중점) → 공백 치환",
        condition="OCR 공백 오인식 보정",
        example="단어·단어 → 단어 단어",
        apply_fn=_fix_space_dot,
    ),
    NormalizeRule(
        rule_id="bullet_remove",
        description="단독 불릿 라인 제거",
        condition="라인이 ^\\s*[·∙•]\\s*$ 패턴일 때",
        example="· 단독 줄 → 제거",
        apply_fn=_remove_bullet_lines,
    ),
    NormalizeRule(
        rule_id="kr_kr_merge",
        description="한글-한글 사이 줄바꿈 제거",
        condition="(?<=[가-힣])\\s*\\n\\s*(?=[가-힣])",
        example="스\\n스로 → 스스로",
        apply_fn=_merge_kr_kr_breaks,
    ),
    NormalizeRule(
        rule_id="en_en_break_merge",
        description="영문-영문 사이 줄바꿈 제거",
        condition="(?<=[A-Za-z])\\s*\\n\\s*(?=[A-Za-z])",
        example="L\\nL\\ne\\nM\\nm → LLeMm",
        apply_fn=_merge_en_en_breaks,
    ),
    NormalizeRule(
        rule_id="en_en_space_merge",
        description="영문 단어 내부 공백 제거",
        condition="짧은 토큰(≤3자) 또는 소문자 시작 토큰 앞 공백",
        example="Sel f-Ref lective → Self-Reflective",
        apply_fn=_merge_en_en_spaces,
    ),
    NormalizeRule(
        rule_id="paren_fix",
        description="괄호 내부 정제",
        condition="\\( ... \\) 구간",
        example="(L\\nL\\ne\\nM\\nm) → (LLM)",
        apply_fn=_fix_paren_content,
    ),
    NormalizeRule(
        rule_id="pipe_to_ai",
        description="콜론 뒤 | → AI (AI 오인식)",
        condition=": | 모델 문맥",
        example="편향 감사: | 모델 → 편향 감사: AI 모델",
        apply_fn=_fix_pipe_to_ai,
    ),
    NormalizeRule(
        rule_id="ocr_similar_en",
        description="영문 토큰 OCR 유사문자 치환",
        condition="알파벳/숫자 비율 60%+",
        example="A·I| → AI",
        apply_fn=_fix_ocr_similar_in_en,
    ),
]


def _apply_rule(
    text: str,
    rule: NormalizeRule,
    diff_log: list[DiffEntry] | None,
) -> str:
    """규칙 적용. diff_log가 None이 아니면 변경 시 로그 기록."""
    after = rule.apply_fn(text)
    if diff_log is not None and after != text:
        diff_log.append(
            DiffEntry(rule_id=rule.rule_id, before=text[:200], after=after[:200])
        )
    return after


def _check_guardrail(
    original_line: str, result_line: str, line_id: int
) -> tuple[bool, str | None]:
    """변경량 가드레일. 라인당 5% 초과 시 검토 필요 플래그."""
    if not original_line.strip():
        return True, None
    orig_len = len(original_line)
    if orig_len == 0:
        return True, None
    diff_count = sum(1 for a, b in zip(original_line, result_line) if a != b)
    diff_count += abs(len(original_line) - len(result_line))
    ratio = diff_count / orig_len
    if ratio > CHANGE_RATIO_LIMIT:
        return False, f"line_{line_id}: change_ratio={ratio:.2%} > {CHANGE_RATIO_LIMIT}"
    return True, None


def normalize_text(
    text: str,
    collect_diff: bool = False,
) -> tuple[str, list[str], list[DiffEntry]]:
    """
    Post-OCR 세그먼트 파손 복구 정규화.

    적용 순서: NFC → 줄바꿈 복구 → 괄호 내부 정제 → 토큰 치환 → 가드레일

    Args:
        text: 입력 텍스트
        collect_diff: True면 diff_log 수집 (디버깅용). 기본 False로 추출 속도 우선.

    Returns:
        (normalized_text, flags, diff_log)
    """
    flags: list[str] = []
    diff_log: list[DiffEntry] = [] if collect_diff else []

    if not text or not text.strip():
        return text, flags, diff_log

    original_lines = text.split("\n")
    result = text
    log = diff_log if collect_diff else None

    for rule in RULES:
        result = _apply_rule(result, rule, log)

    result_lines = result.split("\n")
    for i, (orig, res) in enumerate(zip(original_lines, result_lines)):
        ok, msg = _check_guardrail(orig, res, i)
        if not ok and msg:
            flags.append(msg)

    if len(result_lines) != len(original_lines):
        flags.append("guardrail: line_count_changed")

    return result.strip(), flags, diff_log


def get_rules_doc() -> list[dict]:
    """규칙 목록을 문서화용 dict로 반환."""
    return [
        {
            "rule_id": r.rule_id,
            "description": r.description,
            "condition": r.condition,
            "example": r.example,
        }
        for r in RULES
    ]
