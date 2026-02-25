"""한글/영어 분리 처리: kor 1차 스캔 후 영어 블록만 eng로 재처리."""

from dataclasses import dataclass

import cv2
import numpy as np
import pytesseract
from PIL import Image


@dataclass
class WordInfo:
    """단어 단위 OCR 결과."""
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: int
    block_num: int
    line_num: int
    word_num: int


def _latin_ratio(text: str) -> float:
    """Latin(a-z, A-Z) 문자 비율 (0~1)."""
    chars = [c for c in text if c.strip()]
    if not chars:
        return 0.0
    latin = sum(1 for c in chars if "a" <= c <= "z" or "A" <= c <= "Z")
    return latin / len(chars)


def _is_hangul_char(c: str) -> bool:
    """한글 음절 여부."""
    return "\uac00" <= c <= "\ud7a3"


def _is_english_candidate(text: str, conf: int) -> bool:
    """영어 후보: Latin 비율 높거나, conf 낮음(kor가 영문을 오인식했을 가능성)."""
    t = text.strip()
    if not t:
        return False
    # Latin 비율 > 0.4 → 명확한 영문
    if _latin_ratio(t) > 0.4:
        return True
    # conf 낮음 → kor/kor+eng가 확신 못함. 영문을 숫자/한글로 오인식한 경우 Latin이 없을 수 있음
    if conf >= 0 and conf < 55:
        return True
    return False


def get_word_data(pil_img: Image.Image, lang: str, psm: str = "--psm 6 --oem 3") -> list[WordInfo]:
    """image_to_data 결과를 WordInfo 리스트로 반환."""
    try:
        data = pytesseract.image_to_data(pil_img, lang=lang, config=psm, output_type=pytesseract.Output.DICT)
    except Exception:
        return []

    words: list[WordInfo] = []
    for i in range(len(data["text"])):
        text = data["text"][i] or ""
        conf = int(data["conf"][i]) if data["conf"][i] else -1
        if not text.strip() and conf < 0:
            continue
        words.append(WordInfo(
            text=text,
            left=data["left"][i],
            top=data["top"][i],
            width=data["width"][i],
            height=data["height"][i],
            conf=conf,
            block_num=data["block_num"][i],
            line_num=data["line_num"][i],
            word_num=data["word_num"][i],
        ))
    return words


def _reading_order_key(w: WordInfo) -> tuple[int, int]:
    """물리적 위치 기반 읽기 순서. Tesseract block/line은 레이아웃에 따라 잘못될 수 있음."""
    return (w.top, w.left)


def identify_english_blocks(words: list[WordInfo]) -> list[tuple[int, int, tuple[int, int, int, int]]]:
    """
    영어 후보 단어를 인접 그룹으로 묶어 블록 반환.
    반환: [(start_idx, end_idx, (x, y, w, h)), ...]
    """
    if not words:
        return []

    sorted_words = sorted(words, key=_reading_order_key)
    n = len(sorted_words)

    blocks: list[tuple[int, int, tuple[int, int, int, int]]] = []
    i = 0

    while i < n:
        w = sorted_words[i]
        if not _is_english_candidate(w.text, w.conf):
            i += 1
            continue

        start = i
        min_x = w.left
        min_y = w.top
        max_r = w.left + w.width
        max_b = w.top + w.height

        j = i + 1
        while j < n:
            nw = sorted_words[j]
            # 같은 줄 또는 y 차이 1.5줄 이내면 인접으로 간주
            y_gap = abs(nw.top - sorted_words[j - 1].top)
            if not _is_english_candidate(nw.text, nw.conf):
                if y_gap > 40:  # 줄 바뀜이면 블록 종료
                    break
                j += 1
                continue

            min_x = min(min_x, nw.left)
            min_y = min(min_y, nw.top)
            max_r = max(max_r, nw.left + nw.width)
            max_b = max(max_b, nw.top + nw.height)
            j += 1

        if j > start:
            blocks.append((start, j, (min_x, min_y, max_r - min_x, max_b - min_y)))
        i = j

    return blocks


def _crop_with_padding(img: np.ndarray, x: int, y: int, w: int, h: int, pad: int = 5) -> np.ndarray:
    """이미지에서 영역 crop, 패딩 적용."""
    h_img, w_img = img.shape[:2]
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(w_img, x + w + pad)
    y2 = min(h_img, y + h + pad)
    return img[y1:y2, x1:x2]



def run_split_ocr(rgb: np.ndarray, ocr_string_fn) -> str:
    """
    한글 1차 스캔 → 영어 블록 감지 → eng 재처리 → 병합.
    ocr_string_fn(pil, lang) 시그니처.
    """
    pil = Image.fromarray(rgb)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    pil_bin = Image.fromarray(binary)

    # kor 1차: image_to_string (메인 텍스트용). bbox는 kor+eng로 (영문 일부 인식돼 감지에 유리)
    kor_text = ocr_string_fn(pil_bin, "kor")
    words = get_word_data(pil_bin, "kor+eng")

    blocks = identify_english_blocks(words)
    if not blocks:
        return kor_text

    eng_results: dict[int, str] = {}
    for bi, (start, end, (x, y, w, h)) in enumerate(blocks):
        if w < 10 or h < 10:
            continue
        crop = _crop_with_padding(rgb, x, y, w, h)
        crop_pil = Image.fromarray(crop)
        eng_text = ocr_string_fn(crop_pil, "eng").strip()
        # eng 결과가 영문으로 보일 때만 사용 (한글 블록 오판 시 잘못된 치환 방지)
        if eng_text and len(eng_text) >= 2 and _latin_ratio(eng_text) > 0.15:
            eng_results[bi] = eng_text

    merged = _merge_with_kor_base(words, blocks, eng_results)
    # 병합 결과가 비정상적으로 짧으면 kor_text로 폴백
    if len(merged.strip()) < 20 and len(kor_text.strip()) > 50:
        return kor_text
    return merged


def _needs_space_before(prev: WordInfo, curr: WordInfo) -> bool:
    """한글 연속 시 공백 없음(image_to_data 글자 단위 이슈), 영문/경계 시 공백."""
    if not prev.text or not curr.text:
        return False
    p, c = prev.text[-1], curr.text[0]
    # 연속 한글 단일 글자 → 공백 없음
    if _is_hangul_char(p) and _is_hangul_char(c):
        return False
    # 이전이 Latin/숫자/괄호로 끝나거나 현재가 Latin으로 시작 → 공백
    return True


def _merge_with_kor_base(
    words: list[WordInfo],
    blocks: list[tuple[int, int, tuple[int, int, int, int]]],
    eng_results: dict[int, str],
) -> str:
    """
    word_data 기반 재구성. 영어 블록은 eng 결과로 치환.
    한글 연속 구간은 공백 없이 이어붙임.
    """
    if not words:
        return ""

    sorted_words = sorted(words, key=_reading_order_key)
    word_to_block: dict[int, int] = {}
    for bi, (start, end, _) in enumerate(blocks):
        for idx in range(start, end):
            word_to_block[idx] = bi

    LINE_TOLERANCE = 15  # 같은 줄로 볼 y 픽셀 차이
    result_parts: list[str] = []
    prev_top = -999
    prev_word: WordInfo | None = None

    def _same_line(wa: WordInfo, wb: WordInfo) -> bool:
        return abs(wa.top - wb.top) <= LINE_TOLERANCE

    for i, w in enumerate(sorted_words):
        block_idx = word_to_block.get(i, -1)

        if block_idx >= 0 and block_idx in eng_results:
            if i == blocks[block_idx][0]:
                if prev_word and not _same_line(prev_word, w):
                    result_parts.append("\n")
                elif prev_word and _same_line(prev_word, w) and _needs_space_before(prev_word, w):
                    result_parts.append(" ")
                result_parts.append(eng_results[block_idx])
            prev_word = w
            prev_top = w.top
            continue

        if prev_word and not _same_line(prev_word, w):
            result_parts.append("\n")
        elif prev_word and _same_line(prev_word, w) and _needs_space_before(prev_word, w):
            result_parts.append(" ")
        result_parts.append(w.text)
        prev_word = w
        prev_top = w.top

    return "".join(result_parts)
