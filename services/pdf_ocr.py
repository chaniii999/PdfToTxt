"""PDF 텍스트 추출: 디지털 직접 추출 우선, 스캔본은 최소 전처리 OCR."""

import asyncio
import json
from typing import AsyncGenerator

import fitz
import cv2
import numpy as np
from PIL import Image
import pytesseract

from services.scan_detect import compute_scan_score, PAGE_DIRECT

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

LANG = "kor+eng"
PSM_BLOCK = "--psm 6 --oem 3"
PSM_AUTO = "--psm 3 --oem 3"


def _render_page(page: fitz.Page, dpi: int = 300) -> np.ndarray:
    """페이지를 RGB numpy array로 렌더링."""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)


def _simple_ocr(rgb: np.ndarray, lang: str) -> tuple[str, float, str]:
    """최소 전처리 OCR: 원본 → 실패 시 grayscale+Otsu 순으로 시도."""
    pil_img = Image.fromarray(rgb)

    text, conf, psm = _try_ocr(pil_img, lang, PSM_BLOCK)
    if conf >= 50 and len(text.strip()) > 5:
        return text, conf, psm

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    pil_binary = Image.fromarray(binary)

    text2, conf2, psm2 = _try_ocr(pil_binary, lang, PSM_BLOCK)
    if conf2 > conf:
        return text2, conf2, psm2

    text3, conf3, psm3 = _try_ocr(pil_binary, lang, PSM_AUTO)
    if conf3 > conf and conf3 > conf2:
        return text3, conf3, psm3

    return text, conf, psm


def _try_ocr(pil_img: Image.Image, lang: str, psm: str) -> tuple[str, float, str]:
    """image_to_data로 텍스트 + confidence를 한번에 추출."""
    try:
        data = pytesseract.image_to_data(
            pil_img, lang=lang, config=psm,
            output_type=pytesseract.Output.DICT,
        )
    except Exception:
        return "", 0.0, psm

    lines: dict[tuple[int, int, int], list[str]] = {}
    conf_values: list[int] = []

    for i in range(len(data["text"])):
        c = int(data["conf"][i])
        txt = data["text"][i]
        if c <= 0 or not txt.strip():
            continue
        conf_values.append(c)
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(txt)

    text = "\n".join(" ".join(words) for _, words in sorted(lines.items()))
    avg_conf = float(np.mean(conf_values)) if conf_values else 0.0

    return text, round(avg_conf, 1), psm


def _process_page_sync(page: fitz.Page, idx: int, total: int, lang: str) -> tuple[str, str, str]:
    """단일 페이지 처리 후 (NDJSON 줄, 텍스트, 메서드) 반환."""
    try:
        score = compute_scan_score(page)

        if score.decision == PAGE_DIRECT:
            text = page.get_text("text").strip()
            method = "direct"
            avg_conf = 100.0
            psm_used = "n/a"
        else:
            rgb = _render_page(page, dpi=300)
            text, avg_conf, psm_used = _simple_ocr(rgb, lang)
            method = "ocr"

        ndjson = json.dumps({
            "page": idx + 1,
            "total": total,
            "method": method,
            "avg_conf": avg_conf,
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
