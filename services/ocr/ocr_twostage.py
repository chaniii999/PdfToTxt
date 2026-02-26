"""1차 kor → 2차 eng(영어 의심후보군만) 2단 OCR.

프로세스:
1. 1차: kor image_to_string → 띄어쓰기 유지 (base_text)
2. image_to_data로 eng 의심후보 bbox 추출 (완성형 한글 1개라도 있으면 제외)
3. 2차: 의심후보만 eng 재인식 → base_text에 순차 치환
"""

import os
import re
from typing import Any

import cv2
import numpy as np
from PIL import Image
import pytesseract

CROP_PADDING = int(os.environ.get("OCR_CROP_PADDING", "8"))
ENG_ASCII_MIN = float(os.environ.get("OCR_ENG_ASCII_MIN", "0.5"))

_SYLLABLE = re.compile(r"[\uac00-\ud7a3]")
_JAMO = re.compile(r"[\u3130-\u318f\u1100-\u11ff]")
_ENG_SYMBOLS = re.compile(r"[|\\/\[\]()+\-!<>]")
_DIGIT = re.compile(r"[0-9]")
_ASCII = re.compile(r"[a-zA-Z0-9]")
_LETTER = re.compile(r"[a-zA-Z]")


def _parse_image_to_data(data: str, level: int = 5) -> list[dict[str, Any]]:
    """image_to_data TSV 파싱. level 5(단어) 또는 4(라인)."""
    lines = data.strip().split("\n")
    if not lines:
        return []
    items = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        try:
            if int(parts[0]) != level:
                continue
            left, top = int(parts[6]), int(parts[7])
            w, h = int(parts[8]), int(parts[9])
            text = parts[11].strip()
            items.append({
                "block_num": int(parts[1]), "line_num": int(parts[2]), "word_num": int(parts[3]),
                "left": left, "top": top, "width": w, "height": h,
                "text": text,
            })
        except (ValueError, IndexError):
            continue
    return items


def _has_complete_syllable(text: str) -> bool:
    """완성형 한글(가-힣) 1개라도 포함 여부."""
    return bool(text and _SYLLABLE.search(text))


def _is_eng_suspicious(word: dict[str, Any]) -> bool:
    """
    영어 의심후보군: 1) 숫자 2) 특수기호 3) 미완성 한글(자모)만.
    절대 규칙: 1차에서 완성된 한글(가-힣)이 1개라도 있으면 eng 절대 적용 안 함.
    """
    text = word["text"]
    if not text:
        return False
    if _has_complete_syllable(text):
        return False
    if _DIGIT.search(text):
        return True
    if _ENG_SYMBOLS.search(text):
        return True
    if _JAMO.search(text):
        return True
    return False


def _ascii_ratio(s: str) -> float:
    if not s:
        return 0.0
    return sum(1 for c in s if _ASCII.match(c)) / len(s)


def _has_letter(s: str) -> bool:
    return bool(s and _LETTER.search(s))


def _contains_korean(text: str) -> bool:
    """완성형 한글(가-힣) 또는 자모 포함 여부. eng 결과 채택 시 거부용."""
    return bool(text and (_SYLLABLE.search(text) or _JAMO.search(text)))


def _replace_first_from(text: str, start: int, old: str, new: str) -> tuple[str, int]:
    """text에서 start 이후 첫 old를 new로 치환. (결과, 다음 시작위치) 반환."""
    idx = text.find(old, start)
    if idx < 0:
        return text, start
    result = text[:idx] + new + text[idx + len(old) :]
    return result, idx + len(new)


def _ocr_roi_eng(
    img: np.ndarray,
    box: tuple[int, int, int, int],
    config: str,
) -> str:
    """ROI 영역만 eng OCR. PSM 8(단어)."""
    left, top, w, h = box
    if w < 2 or h < 2:
        return ""
    try:
        crop = img[top : top + h, left : left + w]
        if len(crop.shape) == 3:
            crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        pil_crop = Image.fromarray(crop)
        cfg = re.sub(r"--psm\s+\d+", "", config).strip() + " --psm 8"
        return pytesseract.image_to_string(pil_crop, lang="eng", config=cfg).strip()
    except Exception:
        return ""


def _to_orig_coords(
    left: int, top: int, w: int, h: int,
    scale: float, border: int,
    orig_w: int, orig_h: int,
) -> tuple[int, int, int, int]:
    """전처리 좌표 → 원본 좌표."""
    l = max(0, int((left - CROP_PADDING - border) / scale))
    t = max(0, int((top - CROP_PADDING - border) / scale))
    rw = max(4, int((w + 2 * CROP_PADDING) / scale))
    rh = max(4, int((h + 2 * CROP_PADDING) / scale))
    l = min(l, orig_w - 4)
    t = min(t, orig_h - 4)
    rw = min(rw, orig_w - l)
    rh = min(rh, orig_h - t)
    return (l, t, rw, rh)


def ocr_page_twostage(
    pil_img: Image.Image,
    tess_config: str,
    rgb_original: np.ndarray | None = None,
    scale: float = 1.0,
    border: int = 10,
) -> str:
    """
    1차 kor image_to_string → 띄어쓰기 유지.
    image_to_data로 eng 의심후보 bbox만 추출 → 2차 eng → base_text에 순차 치환.
    """
    try:
        base_text = pytesseract.image_to_string(pil_img, lang="kor", config=tess_config).strip()
    except Exception:
        return ""

    try:
        data = pytesseract.image_to_data(pil_img, lang="kor", config=tess_config)
    except Exception:
        return base_text

    words = _parse_image_to_data(data, level=5)
    if not words:
        words = _parse_image_to_data(data, level=4)
    if not words:
        return base_text

    words.sort(key=lambda w: (w["block_num"], w["line_num"], w["word_num"]))

    img_w, img_h = pil_img.size
    base_config = re.sub(r"--psm\s+\d+", "", tess_config).strip()

    use_original = (
        rgb_original is not None
        and scale > 0
        and rgb_original.shape[0] > 0
        and rgb_original.shape[1] > 0
    )
    if use_original:
        orig_h, orig_w = rgb_original.shape[:2]

    replacements: list[tuple[str, str]] = []
    for w in words:
        if not _is_eng_suspicious(w) or w["width"] < 4 or w["height"] < 4:
            continue
        kor_text = w["text"]
        if not kor_text:
            continue

        left_px = max(0, w["left"] - CROP_PADDING)
        top_px = max(0, w["top"] - CROP_PADDING)
        right_px = min(img_w, w["left"] + w["width"] + CROP_PADDING)
        bottom_px = min(img_h, w["top"] + w["height"] + CROP_PADDING)
        box_preproc = (left_px, top_px, right_px - left_px, bottom_px - top_px)

        if use_original:
            box_orig = _to_orig_coords(
                w["left"], w["top"], w["width"], w["height"],
                scale, border, orig_w, orig_h,
            )
            eng_text = _ocr_roi_eng(rgb_original, box_orig, base_config)
            if not eng_text or _ascii_ratio(eng_text) < ENG_ASCII_MIN or not _has_letter(eng_text):
                eng_fallback = _ocr_roi_eng(np.array(pil_img), box_preproc, base_config)
                if eng_fallback and _ascii_ratio(eng_fallback) >= ENG_ASCII_MIN and _has_letter(eng_fallback):
                    eng_text = eng_fallback
        else:
            eng_text = _ocr_roi_eng(np.array(pil_img), box_preproc, base_config)

        if (
            eng_text
            and _ascii_ratio(eng_text) >= ENG_ASCII_MIN
            and _has_letter(eng_text)
            and not _contains_korean(eng_text)
        ):
            replacements.append((kor_text, eng_text))

    result = base_text
    pos = 0
    for kor_text, eng_text in replacements:
        result, pos = _replace_first_from(result, pos, kor_text, eng_text)

    return result.strip()
