"""PDF 텍스트 추출: 디지털 직접 추출 우선, 스캔본은 최소 전처리 OCR."""

import asyncio
import json
import logging
from typing import AsyncGenerator

import fitz
import cv2
import numpy as np
from PIL import Image
import pytesseract

from services.ocr.preprocess import (
    PRESET_A,
    PRESET_B,
    PRESET_C,
    add_ocr_border,
    enhance_for_ocr,
    preprocess_for_ocr,
)
from services.ocr.scan_detect import compute_scan_score, PAGE_DIRECT
from services.ocr.orientation import deskew_rgb
from services.ocr.tessdata_check import verify_tessdata_best

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

LANG = "kor+eng"
PSM_BLOCK = "--psm 6 --oem 3"
PSM_COLUMN = "--psm 4 --oem 3"
PSM_AUTO = "--psm 3 --oem 3"

def _render_page(page: fitz.Page, dpi: int = 350) -> np.ndarray:
    """페이지를 RGB numpy array로 렌더링."""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)


def _korean_ratio(text: str) -> float:
    """한글 문자 비율 (0~1). 품질 보조 지표."""
    chars = text.replace(" ", "").replace("\n", "")
    if not chars:
        return 0.0
    korean = sum(1 for c in chars if "\uac00" <= c <= "\ud7a3")
    return korean / len(chars)


def _score_candidate(text: str) -> float:
    """선택 점수: 길이×(0.2+0.8×한글비율). 한글 오인식(Latin) 억제."""
    t = text.strip()
    if not t:
        return 0.0
    kr = _korean_ratio(t)
    return len(t) * (0.2 + 0.8 * kr)


def _simple_ocr(rgb: np.ndarray, lang: str) -> tuple[str, str]:
    """다중 전처리·PSM 후보 중 최고 점수 선택. 인식률 우선."""
    pil_rgb = Image.fromarray(rgb)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    pil_bin = Image.fromarray(binary)

    candidates: list[tuple[str, str]] = [
        (_ocr_string(pil_rgb, lang, PSM_BLOCK), "rgb+psm6"),
        (_ocr_string(pil_bin, lang, PSM_BLOCK), "otsu+psm6"),
        (_ocr_string(pil_bin, lang, PSM_COLUMN), "otsu+psm4"),
        (_ocr_string(pil_bin, lang, PSM_AUTO), "otsu+psm3"),
    ]
    best = max(candidates, key=lambda x: _score_candidate(x[0]))
    if _score_candidate(best[0]) > 450:
        return best[0], best[1]

    try:
        enhanced = enhance_for_ocr(rgb)
        t = _ocr_string(Image.fromarray(enhanced), lang, PSM_BLOCK)
        if _score_candidate(t) > _score_candidate(best[0]):
            best = (t, "enhance+psm6")
    except Exception:
        pass
    for preset in (PRESET_A, PRESET_B, PRESET_C):
        try:
            preprocessed = preprocess_for_ocr(rgb, preset)
            t = _ocr_string(Image.fromarray(preprocessed), lang, PSM_BLOCK)
            if _score_candidate(t) > _score_candidate(best[0]):
                best = (t, f"preset{preset}+psm6")
        except Exception:
            pass

    return best[0], best[1]


def _ocr_string(pil_img: Image.Image, lang: str, psm: str) -> str:
    """image_to_string 단일 호출. Tesseract가 자체 단어 그룹핑 유지."""
    try:
        return pytesseract.image_to_string(pil_img, lang=lang, config=psm).strip()
    except Exception:
        return ""


def _process_page_sync(page: fitz.Page, idx: int, total: int, lang: str) -> tuple[str, str, str]:
    """단일 페이지 처리 후 (NDJSON 줄, 텍스트, 메서드) 반환."""
    try:
        score = compute_scan_score(page)

        if score.decision == PAGE_DIRECT:
            text = page.get_text("text").strip()
            method = "direct"
            psm_used = "n/a"
        else:
            rgb = _render_page(page)
            rgb = deskew_rgb(rgb)
            rgb = add_ocr_border(rgb)
            text, psm_used = _simple_ocr(rgb, lang)
            method = "ocr"

        ndjson = json.dumps({
            "page": idx + 1,
            "total": total,
            "method": method,
            "psm_used": psm_used,
            "scan_score": {
                "words": score.word_count,
                "text_area": round(score.text_area_ratio, 4),
                "img_area": round(score.image_area_ratio, 4),
            },
        }) + "\n"
        return ndjson, text, method

    except Exception as err:
        ndjson = json.dumps({
            "page": idx + 1,
            "total": total,
            "method": "error",
            "error": str(err)[:200],
        }) + "\n"
        return ndjson, "", "error"


async def extract_text_stream(pdf_bytes: bytes, lang: str = LANG) -> AsyncGenerator[str, None]:
    """페이지별 NDJSON 스트리밍. 블로킹 OCR은 스레드에서 실행해 이벤트 루프 비차단."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    all_parts: list[str] = []
    all_methods: list[str] = []

    tess_ok, tess_msg = verify_tessdata_best()
    if not tess_ok:
        logging.warning("OCR tessdata: %s", tess_msg)
    yield json.dumps({
        "page": 0,
        "total": total,
        "method": "started",
        "tessdata_ok": tess_ok,
        "tessdata_msg": tess_msg,
    }) + "\n"
    await asyncio.sleep(0)

    try:
        for idx in range(total):
            page = doc[idx]
            ndjson_line, text, method = await asyncio.to_thread(
                _process_page_sync, page, idx, total, lang
            )

            if text:
                all_parts.append(text)
            all_methods.append(f"p{idx + 1}:{method}")

            yield ndjson_line
            await asyncio.sleep(0)

    finally:
        doc.close()

    yield json.dumps({
        "done": True,
        "text": "\n\n".join(all_parts) if all_parts else "",
        "methods": all_methods,
    }) + "\n"
