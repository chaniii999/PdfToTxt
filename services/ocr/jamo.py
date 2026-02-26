"""한글 자모 분리·조합. 유니코드 완성형(U+AC00~D7A3) 기준."""

# 초성 19, 중성 21, 종성 28 (빈칸 포함). 유니코드 한글 음절 블록 순서.
_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"  # [0]=빈칸

_HANGUL_BASE = 0xAC00
_CHO_COUNT = 19
_JUNG_COUNT = 21
_JONG_COUNT = 28
_BLOCK_SIZE = _JUNG_COUNT * _JONG_COUNT  # 588


def split_syllable(char: str) -> tuple[str, str, str] | None:
    """
    한글 음절을 (초성, 중성, 종성)으로 분리.
    한글이 아니면 None 반환.
    """
    if len(char) != 1:
        return None
    code = ord(char)
    if not (0xAC00 <= code <= 0xD7A3):
        return None
    base = code - _HANGUL_BASE
    jong = base % _JONG_COUNT
    base //= _JONG_COUNT
    jung = base % _JUNG_COUNT
    cho = base // _JUNG_COUNT
    return (_CHO[cho], _JUNG[jung], _JONG[jong])


def join_syllable(cho: str, jung: str, jong: str) -> str:
    """초성·중성·종성으로 한글 음절 조합."""
    try:
        ci = _CHO.index(cho)
        ji = _JUNG.index(jung)
        ki = _JONG.index(jong) if jong else 0
        return chr(_HANGUL_BASE + ci * _BLOCK_SIZE + ji * _JONG_COUNT + ki)
    except (ValueError, IndexError):
        return ""


def is_hangul_syllable(char: str) -> bool:
    """완성형 한글 음절 여부."""
    return len(char) == 1 and 0xAC00 <= ord(char) <= 0xD7A3
