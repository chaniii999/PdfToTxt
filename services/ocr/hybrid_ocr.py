"""kor/eng 분리 2단 OCR: kor 전용 1차 → 저신뢰도·영문 의심 영역만 eng 재인식."""

import logging
from typing import Any

import numpy as np
from PIL import Image
import pytesseract

# 신뢰도 임계값: 이하면 eng 재인식 대상
CONF_THRESHOLD = 60
# 영문 의심: ASCII 비율 이 이상이면 eng 재인식
ENG_ASCII_RATIO = 0.6
# crop 시 패딩 (px)
CROP_PADDING = 8

KOR_CONFIG = (
    "--oem 1 --psm 3 "
    "-c preserve_interword_spaces=1 -c tessedit_do_invert=0"
)
ENG_CONFIG = (
    "--oem 3 --psm 6 "
    "-c preserve_interword_spaces=1 -c tessedit_do_invert=0"
)


def _looks_like_english(text: str) -> bool:
    """텍스트가 영문일 가능성이 높으면 True."""
    if not text or len(text) < 2:
        return False
    ascii_cnt = sum(1 for c in text if c.isascii() and (c.isalpha() or c.isdigit()))
    return ascii_cnt / len(text) >= ENG_ASCII_RATIO


def _should_recheck_with_eng(block: dict[str, Any]) -> bool:
    """저신뢰도 또는 영문 의심 시 eng 재인식 대상."""
    conf = block.get("conf", 0)
    text = block.get("text", "").strip()
    if conf >= 0 and conf < CONF_THRESHOLD:
        return True
    if text and _looks_like_english(text):
        return True
    return False


def _get_blocks_from_data(pil_img: Image.Image, word_only: bool = True) -> list[dict[str, Any]]:
    """image_to_data로 블록(좌표, 신뢰도, 텍스트) 목록 반환. word_only=True면 level 5만."""
    try:
        data = pytesseract.image_to_data(
            pil_img,
            lang="kor",
            config=KOR_CONFIG,
            output_type=pytesseract.Output.DICT,
        )
    except pytesseract.TesseractError as e:
        logging.warning("kor image_to_data 오류: %s", str(e)[:150])
        return []

    n = len(data["text"])
    blocks: list[dict[str, Any]] = []
    for i in range(n):
        level = int(data["level"][i]) if "level" in data else 5
        if word_only and level != 5:
            continue
        text = (data["text"][i] or "").strip()
        conf_str = data["conf"][i]
        conf = int(conf_str) if isinstance(conf_str, str) and conf_str != "-1" else int(conf_str) if isinstance(conf_str, (int, float)) else 0
        left = int(data["left"][i])
        top = int(data["top"][i])
        width = int(data["width"][i])
        height = int(data["height"][i])
        if width < 2 or height < 2:
            continue
        blocks.append({
            "left": left,
            "top": top,
            "width": width,
            "height": height,
            "conf": conf,
            "text": text,
            "line_num": int(data["line_num"][i]),
            "word_num": int(data["word_num"][i]),
        })
    return blocks


def _crop_region(img: np.ndarray, block: dict[str, Any], padding: int = CROP_PADDING) -> np.ndarray:
    """블록 좌표로 이미지 영역 crop. 패딩 적용."""
    h, w = img.shape[:2]
    left = block["left"]
    top = block["top"]
    width = block["width"]
    height = block["height"]
    x1 = max(0, left - padding)
    y1 = max(0, top - padding)
    x2 = min(w, left + width + padding)
    y2 = min(h, top + height + padding)
    return img[y1:y2, x1:x2]


def _ocr_crop_eng(crop_img: np.ndarray) -> str:
    """crop된 이미지를 eng 전용으로 OCR."""
    try:
        pil = Image.fromarray(crop_img)
        return pytesseract.image_to_string(
            pil,
            lang="eng",
            config=ENG_CONFIG,
        ).strip()
    except pytesseract.TesseractError as e:
        logging.debug("eng crop OCR 오류: %s", str(e)[:100])
        return ""


# 표선·구분선 노이즈 블록 (단일/짧은 문자)
NOISE_BLOCK_PATTERN = frozenset({"=", "—", "|", "·", "==", "—"})


def _is_noise_block(text: str) -> bool:
    """표선·구분선 등 노이즈로 인식된 블록 여부."""
    t = text.strip()
    if not t or len(t) > 4:
        return False
    return t in NOISE_BLOCK_PATTERN or all(c in "=—|-|·" for c in t)


def _merge_blocks_with_eng(
    blocks: list[dict[str, Any]],
    eng_results: dict[int, str],
) -> str:
    """블록 순서대로 텍스트 병합. eng 재인식 결과로 치환."""
    parts: list[str] = []
    prev_line = -1
    for idx, block in enumerate(blocks):
        text = eng_results.get(idx, block["text"])
        if not text or _is_noise_block(text):
            continue
        line_num = block.get("line_num", 0)
        if prev_line >= 0 and line_num != prev_line:
            parts.append("\n")
        elif parts and parts[-1] != "\n":
            parts.append(" ")
        parts.append(text)
        prev_line = line_num
    return "".join(parts).strip()


def ocr_page_hybrid(img_binary: np.ndarray) -> str:
    """
    kor 1차 → 저신뢰도·영문 의심 영역만 crop → eng 재인식 → 병합.
    img_binary: 전처리된 이진 이미지 (H, W) 또는 (H, W, C).
    """
    pil_img = Image.fromarray(img_binary)

    blocks = _get_blocks_from_data(pil_img, word_only=True)
    if not blocks:
        logging.info("hybrid: level 5 블록 0개 → image_to_string 폴백")
        try:
            result = pytesseract.image_to_string(
                pil_img,
                lang="kor",
                config="--oem 1 --psm 6 -c preserve_interword_spaces=1",
            ).strip()
            if not result:
                logging.warning("hybrid 폴백 image_to_string도 빈 결과")
            return result
        except pytesseract.TesseractError as e:
            logging.warning("hybrid 폴백 Tesseract 오류: %s", str(e)[:100])
            return ""

    to_recheck = [(i, b) for i, b in enumerate(blocks) if _should_recheck_with_eng(b)]
    eng_results: dict[int, str] = {}

    for idx, block in to_recheck:
        crop = _crop_region(img_binary, block)
        if crop.shape[0] < 5 or crop.shape[1] < 5:
            continue
        eng_text = _ocr_crop_eng(crop)
        if eng_text:
            eng_results[idx] = eng_text
            logging.debug("hybrid eng 치환: idx=%d conf=%d '%s' → '%s'", idx, block["conf"], block["text"][:20], eng_text[:20])

    merged = _merge_blocks_with_eng(blocks, eng_results)
    if not merged:
        logging.info("hybrid: 병합 결과 빈 문자열 → image_to_string 폴백")
        try:
            return pytesseract.image_to_string(
                pil_img,
                lang="kor",
                config="--oem 1 --psm 6 -c preserve_interword_spaces=1",
            ).strip()
        except pytesseract.TesseractError:
            return ""
    return merged
