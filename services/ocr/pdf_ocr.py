"""PDF 텍스트 추출: 한글 문서 특화 최소 파이프라인. 1~2초/페이지 목표."""

import asyncio
import json
import logging
import os
import time
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

_tesseract_cmd = os.environ.get("TESSERACT_CMD", "/usr/bin/tesseract")
pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd

# Tesseract 옵션 통일 (한글 문서 특화)
DPI = 300
LANG = "kor"
TESS_CONFIG = (
    "--oem 1 "
    "--psm 6 "
    "-c preserve_interword_spaces=1 "
    "-c tessedit_do_invert=0"
)


def _render_page(page: fitz.Page, dpi: int = DPI) -> np.ndarray:
    """페이지를 RGB numpy array로 렌더링. DPI 300 고정."""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)


def _ocr_single(pil_img: Image.Image) -> str:
    """Tesseract 단일 호출. 메모리 상에서 바로 전달."""
    try:
        return pytesseract.image_to_string(
            pil_img,
            lang=LANG,
            config=TESS_CONFIG,
        ).strip()
    except pytesseract.TesseractError as e:
        logging.warning("Tesseract 오류: %s", str(e)[:200])
        return ""
    except Exception as e:
        logging.warning("OCR 예외: %s", type(e).__name__, exc_info=True)
        return ""


def _process_page_sync(
    page: fitz.Page,
    idx: int,
    total: int,
) -> tuple[str, str, str]:
    """단일 페이지 처리. (NDJSON 줄, 텍스트, 메서드) 반환."""
    t0 = time.perf_counter()
    try:
        rgb = _render_page(page)
        logging.info("OCR page=%d 변환 직후 image.shape=%s dpi=%d", idx + 1, rgb.shape, DPI)

        preprocessed = preprocess_minimal(rgb)
        pil_img = Image.fromarray(preprocessed)

        text = _ocr_single(pil_img)
        text = correct_ocr_text(text)

        elapsed = time.perf_counter() - t0
        logging.info(
            "OCR page=%d elapsed=%.2fs shape=%s dpi=%d psm=6",
            idx + 1,
            elapsed,
            preprocessed.shape,
            DPI,
        )
        if elapsed > 3.0:
            logging.warning("OCR page=%d 병목: %.2fs > 3초", idx + 1, elapsed)

        ndjson = json.dumps({
            "page": idx + 1,
            "total": total,
            "method": "ocr",
            "psm_used": "6",
            "dpi": DPI,
            "elapsed_sec": round(elapsed, 2),
            "image_shape": list(preprocessed.shape),
            "text": text,
        }) + "\n"
        return ndjson, text, "ocr"

    except Exception as err:
        elapsed = time.perf_counter() - t0
        logging.exception("OCR page=%d 오류: %s", idx + 1, str(err)[:200])
        ndjson = json.dumps({
            "page": idx + 1,
            "total": total,
            "method": "error",
            "error": str(err)[:200],
            "text": "",
        }) + "\n"
        return ndjson, "", "error"


async def extract_text_stream(
    pdf_bytes: bytes,
    lang: str | None = None,
    force_ocr: bool | None = None,
) -> AsyncGenerator[str, None]:
    """페이지별 NDJSON 스트리밍. 항상 OCR."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    all_parts: list[str] = []
    all_methods: list[str] = []

    yield json.dumps({
        "page": 0,
        "total": total,
        "method": "started",
        "dpi": DPI,
        "psm": 6,
    }) + "\n"
    await asyncio.sleep(0)

    try:
        for idx in range(total):
            page = doc[idx]
            ndjson_line, text, method = await asyncio.to_thread(
                _process_page_sync, page, idx, total
            )

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
