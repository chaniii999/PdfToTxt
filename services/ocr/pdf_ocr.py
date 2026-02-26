"""PDF 텍스트 추출: 핵심 세팅만. 전략 재설계용 최소 파이프라인."""

import asyncio
import json
import os
from typing import AsyncGenerator

import fitz
import cv2
import numpy as np
from PIL import Image
import pytesseract

from services.ocr.preprocess_minimal import preprocess_minimal
from services.ocr.postprocess import correct_ocr_text

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# === 핵심 세팅 (manual-evaluation-log 기준) ===
_tesseract_cmd = os.environ.get("TESSERACT_CMD", "/usr/bin/tesseract")
pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd

DPI = 300
LANG = "kor"
TESS_CONFIG = (
    "--oem 1 --psm 6 "
    "-c preserve_interword_spaces=1 -c tessedit_do_invert=0 "
    "-c language_model_penalty_non_dict_word=0.25 "
    "-c language_model_penalty_non_freq_dict_word=0.2"
)


def _render_page(page: fitz.Page, dpi: int = DPI) -> np.ndarray:
    """페이지를 RGB numpy array로 렌더링."""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)


def _ocr_single(pil_img: Image.Image) -> str:
    """Tesseract 단일 호출."""
    try:
        return pytesseract.image_to_string(
            pil_img, lang=LANG, config=TESS_CONFIG,
        ).strip()
    except Exception:
        return ""


def _process_page_sync(page: fitz.Page, idx: int, total: int) -> tuple[str, str]:
    """단일 페이지 처리. (NDJSON 줄, 텍스트) 반환."""
    try:
        rgb = _render_page(page)
        preprocessed = preprocess_minimal(rgb)
        pil_img = Image.fromarray(preprocessed)
        text = _ocr_single(pil_img)
        text = correct_ocr_text(text)

        ndjson = json.dumps({
            "page": idx + 1,
            "total": total,
            "method": "ocr",
            "dpi": DPI,
            "text": text,
        }) + "\n"
        return ndjson, text
    except Exception as err:
        ndjson = json.dumps({
            "page": idx + 1,
            "total": total,
            "method": "error",
            "error": str(err)[:200],
            "text": "",
        }) + "\n"
        return ndjson, ""


async def extract_text_stream(
    pdf_bytes: bytes,
    force_ocr: bool | None = None,
) -> AsyncGenerator[str, None]:
    """페이지별 NDJSON 스트리밍."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    all_parts: list[str] = []
    all_methods: list[str] = []

    yield json.dumps({"page": 0, "total": total, "method": "started", "dpi": DPI, "psm": 6}) + "\n"
    await asyncio.sleep(0)

    try:
        for idx in range(total):
            page = doc[idx]
            ndjson_line, text = await asyncio.to_thread(
                _process_page_sync, page, idx, total
            )
            all_parts.append(text)
            all_methods.append(f"p{idx + 1}:ocr")
            yield ndjson_line
            await asyncio.sleep(0)
    finally:
        doc.close()

    yield json.dumps({
        "done": True,
        "text": "\n\n".join(all_parts) if all_parts else "",
        "methods": all_methods,
    }) + "\n"
