"""2차 eng OCR 인식 로직·분류 규칙.

한글 1차의 자모/조합 참조(user_words, user_patterns)와 유사하게,
영문 2차에서 알파벳·숫자·특수문자 형태 유사성 기반 보정.
"""

import re
from pathlib import Path
from typing import Any

# === 형태 유사 문자 (OCR 오인식 패턴) ===
# 한글: ㅇ↔ㅁ, ㅔ↔ㅖ 등 → 영문: I↔l, O↔0, |→I 등

# 영문 내부 | → I (파이프 오인식)
_PIPE_TO_I = re.compile(r"(?<=[A-Za-z])\|(?=[A-Za-z])")

# 숫자 구간 O → 0, I → 1 (문맥 의존, postprocess에서 처리)
# 영문 구간 0 → O, 1 → l (약어 PII, AI 등)
_DIGIT_O_TO_LETTER = re.compile(r"(?<![0-9])0(?![0-9])")  # 단독 0 → O (주의: 과도 적용 방지)
# 실제로는 영문 토큰 내부에서만. postprocess_normalize의 ocr_similar_en과 연계

# 알파벳-숫자 혼동 (영문 토큰 내). 한글 ㅇ↔ㅁ처럼 형태 유사 보정
# 0→O: CO0L→COOL 등. P0II는 ACRONYM_FIX에서 처리
_ENG_OCR_SIMILAR: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?<=[A-Za-z])\|(?=[A-Za-z])"), "I"),  # P|I → PII
    (re.compile(r"(?<=[A-Z])1(?=[A-Z])"), "I"),  # P1I → PII (대문자 사이 1→I)
    (re.compile(r"(?<=[A-Za-z])0(?=[A-Za-z])"), "O"),  # S0 → SO (0↔O 혼동)
]

# 도메인 약어 맵 (OCR 오인식 → 정답)
_ACRONYM_FIX: dict[str, str] = {
    "P0II": "PII",
    "P|I": "PII",
    "0!!": "PII",
    "Al": "AI",  # I↔l 혼동
    "LLeMm": "LLM",
    "LLeM": "LLM",
    "Llm": "LLM",
    "Lem": "LLM",  # L↔e 시각 혼동
    "Lemm": "LLM",
    "ㄴㄴM": "LLM",
    "Z(LM)": "LLM",
}

# 도메인 단어 목록 (config에서 로드, fallback)
_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "tesseract"
_ENG_WORDS_PATH = _CONFIG_DIR / "eng_user_words.txt"
_eng_words_cache: list[str] | None = None


def _get_eng_domain_words() -> list[str]:
    """eng_user_words.txt 로드. 도메인 단어 우선 매칭용."""
    global _eng_words_cache
    if _eng_words_cache is not None:
        return _eng_words_cache
    words: list[str] = []
    if _ENG_WORDS_PATH.exists():
        for line in _ENG_WORDS_PATH.read_text(encoding="utf-8").splitlines():
            w = line.strip()
            if w and not w.startswith("#"):
                words.append(w)
    _eng_words_cache = words
    return _eng_words_cache


def postprocess_eng_result(raw: str) -> str:
    """
    eng OCR 원시 결과에 형태 유사 문자 보정 적용.
    - 도메인 약어 맵(정확 일치) 우선
    - | → I, 0 → O (영문 내부, 문맥 한정)
    """
    if not raw or not raw.strip():
        return raw
    text = raw.strip()
    if text in _ACRONYM_FIX:
        return _ACRONYM_FIX[text]
    for pat, repl in _ENG_OCR_SIMILAR:
        text = pat.sub(repl, text)
    return _ACRONYM_FIX.get(text, text)


def is_valid_eng_result(text: str) -> bool:
    """
    eng OCR 결과가 '진짜 영어'인지 검증.
    한글 오인식을 영문으로 잘못 채택하는 것 방지.
    """
    if not text or len(text) < 2:
        return False
    # 한글(완성형·자모) 포함 시 거부
    if re.search(r"[\uac00-\ud7a3\u3130-\u318f\u1100-\u11ff]", text):
        return False
    # 숫자만 있으면 거부 (영문 단어 아님)
    if re.match(r"^[0-9]+$", text):
        return False
    # 알파벳 비율이 너무 낮으면 거부 (특수문자·숫자 과다)
    alpha = sum(1 for c in text if c.isalpha())
    if alpha / len(text) < 0.5:
        return False
    # 의심 패턴: 3자 이하 + 숫자/특수문자 혼합 (한글→Latin 오인식 가능성)
    if len(text) <= 3 and re.search(r"[0-9!@#$%^&*]", text):
        return False
    return True


def classify_eng_candidate(kor_text: str, eng_text: str) -> str | None:
    """
    eng OCR 결과 채택 여부 판정. 채택 시 보정된 eng_text, 거부 시 None.
    - 한글 포함 거부
    - 도메인 단어 우선 (유사 매칭 시 채택)
    - 형태 보정 후 검증
    """
    if not eng_text:
        return None
    corrected = postprocess_eng_result(eng_text)
    if not is_valid_eng_result(corrected):
        return None
    domain_words = _get_eng_domain_words()
    # 도메인 단어와 유사하면 채택 (대소문자 무시)
    corrected_lower = corrected.lower()
    for dw in domain_words:
        if dw.lower() in corrected_lower or corrected_lower in dw.lower():
            return corrected
    # 일반 영문: 알파벳 비율, 길이 등 검증 통과 시 채택
    return corrected


def get_eng_tesseract_config(base_config: str) -> str:
    """
    eng OCR용 Tesseract config. user_words, user_patterns 추가.
    """
    cfg = base_config
    if _ENG_WORDS_PATH.exists():
        cfg += f" -c user_words_file={_ENG_WORDS_PATH}"
    eng_patterns = _CONFIG_DIR / "eng_user_patterns.txt"
    if eng_patterns.exists():
        cfg += f" -c user_patterns_file={eng_patterns}"
    return cfg.strip()
