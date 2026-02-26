"""2-pass OCR: 전체 PSM 6 → 저신뢰/의심 토큰 ROI만 PSM 10/7/8 재시도."""

import os
import re
from typing import Any

from PIL import Image
import pytesseract

OCR_TESSERACT_TIMEOUT = int(os.environ.get("OCR_TESSERACT_TIMEOUT", "120"))  # 0=무제한

# 의/익/폐/페 의심 패턴 (문맥상 이상 시 재시도)
_SUSPICIOUS_CHARS = re.compile(r"[의익폐페]")
CONF_THRESHOLD = 70  # 이하면 ROI 재시도


def _parse_image_to_data(data: str) -> list[dict[str, Any]]:
    """pytesseract image_to_data TSV 파싱. level 5(단어)만 반환."""
    lines = data.strip().split("\n")
    if not lines:
        return []
    header = lines[0].split("\t")
    words = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        try:
            level = int(parts[0])
            if level != 5:
                continue
            block_num = int(parts[1])
            line_num = int(parts[2])
            word_num = int(parts[3])
            left = int(parts[6])
            top = int(parts[7])
            width = int(parts[8])
            height = int(parts[9])
            conf = int(parts[10]) if parts[10] != "-1" else 0
            text = parts[11].strip()
            words.append({
                "block_num": block_num, "line_num": line_num, "word_num": word_num,
                "left": left, "top": top, "width": width, "height": height,
                "conf": conf, "text": text,
            })
        except (ValueError, IndexError):
            continue
    return words


def _ocr_roi(pil_img: Image.Image, box: tuple[int, int, int, int], psm: int, base_config: str) -> str:
    """ROI 영역만 잘라서 OCR."""
    left, top, w, h = box
    if w < 2 or h < 2:
        return ""
    crop = pil_img.crop((left, top, left + w, top + h))
    config = f"{base_config} --psm {psm}"
    try:
        return pytesseract.image_to_string(
            crop, lang="kor", config=config,
            timeout=OCR_TESSERACT_TIMEOUT if OCR_TESSERACT_TIMEOUT > 0 else 0,
        ).strip()
    except Exception:
        return ""


def ocr_page_twopass(pil_img: Image.Image, tess_config: str, lang: str = "kor") -> str:
    """
    1차: PSM 6 image_to_data
    2차: conf < 70 또는 (의/익/폐/페 포함 + 짧은 토큰) 시 ROI만 PSM 10/8 재시도
    """
    config_psm6 = tess_config
    _timeout = OCR_TESSERACT_TIMEOUT if OCR_TESSERACT_TIMEOUT > 0 else 0
    try:
        data = pytesseract.image_to_data(
            pil_img, lang=lang, config=config_psm6, timeout=_timeout,
        )
    except Exception:
        return pytesseract.image_to_string(
            pil_img, lang=lang, config=config_psm6, timeout=_timeout,
        ).strip()

    words = _parse_image_to_data(data)
    if not words:
        return pytesseract.image_to_string(
            pil_img, lang=lang, config=config_psm6, timeout=_timeout,
        ).strip()

    # block_num, line_num, word_num 순 정렬
    words.sort(key=lambda w: (w["block_num"], w["line_num"], w["word_num"]))

    base_config = re.sub(r"--psm\s+\d+", "", tess_config).strip()
    result_parts: list[str] = []
    prev_block, prev_line = -1, -1

    for w in words:
        text = w["text"]
        conf = w["conf"]
        box = (w["left"], w["top"], w["width"], w["height"])

        need_retry = conf < CONF_THRESHOLD or (
            _SUSPICIOUS_CHARS.search(text) and len(text) <= 2
        )
        if need_retry and w["width"] >= 2 and w["height"] >= 2:
            psm = 10 if len(text) <= 1 else 8
            retry_text = _ocr_roi(pil_img, box, psm, base_config)
            if retry_text:
                text = retry_text

        # 줄바꿈: block/line 변화 시
        if prev_block >= 0 and (w["block_num"] != prev_block or w["line_num"] != prev_line):
            if result_parts and result_parts[-1] != "\n":
                result_parts.append("\n")
        prev_block, prev_line = w["block_num"], w["line_num"]

        if text:
            if result_parts and result_parts[-1] != "\n":
                result_parts.append(" ")
            result_parts.append(text)

    return "".join(result_parts).strip()
