"""PDF 텍스트 추출: 디지털 직접 추출 우선, 스캔본은 최소 전처리 OCR."""

import asyncio
import json
from typing import AsyncGenerator

import fitz
import cv2
import numpy as np
from PIL import Image
import pytesseract

from services.ocr.scan_detect import compute_scan_score, PAGE_DIRECT
from services.ocr.postprocess import correct_ocr_text

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

LANG = "kor+eng"
PSM_BLOCK = "--psm 6 --oem 3"
PSM_AUTO = "--psm 3 --oem 3"


def _render_page(page: fitz.Page, dpi: int = 300) -> np.ndarray:
    """페이지를 RGB numpy array로 렌더링."""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)


def _simple_ocr(rgb: np.ndarray, lang: str) -> tuple[str, str]:
    """최소 전처리 OCR: 원본 → 실패 시 grayscale+Otsu. Tesseract 호출 최소화."""
    pil_rgb = Image.fromarray(rgb)

    text1 = _ocr_string(pil_rgb, lang, PSM_BLOCK)
    if len(text1.strip()) > 20:
        return text1, PSM_BLOCK

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    pil_bin = Image.fromarray(binary)

    text2 = _ocr_string(pil_bin, lang, PSM_BLOCK)
    if len(text2.strip()) > len(text1.strip()):
        return text2, PSM_BLOCK

    text3 = _ocr_string(pil_bin, lang, PSM_AUTO)
    if len(text3.strip()) > len(text1.strip()) and len(text3.strip()) > len(text2.strip()):
        return text3, PSM_AUTO

    return text1, PSM_BLOCK


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
            rgb = _render_page(page, dpi=300)
            text, psm_used = _simple_ocr(rgb, lang)
            text = correct_ocr_text(text)
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
    """페이지별 NDJSON 스트리밍. 각 yield 후 event loop에 제어 넘겨 즉시 전송."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    all_parts: list[str] = []
    all_methods: list[str] = []

    try:
        for idx in range(total):
            page = doc[idx]
            ndjson_line, text, method = _process_page_sync(page, idx, total, lang)

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
