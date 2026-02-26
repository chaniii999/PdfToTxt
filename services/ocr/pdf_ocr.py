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
from services.ocr.hybrid_ocr import ocr_page_hybrid

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_tesseract_cmd = os.environ.get("TESSERACT_CMD", "/usr/bin/tesseract")
pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd

HYBRID_OCR = os.environ.get("HYBRID_OCR", "0").lower() in ("1", "true", "yes")

# Tesseract 옵션 (단일 열 문서, PSM 6)
DPI = 300
LANG = "kor"
# 한글 우선: kor+eng에서 첫 언어에 가중치. 비사전어(영문 오인식) 페널티.
TESS_CONFIG = (
    "--oem 1 "
    "--psm 6 "
    "-c preserve_interword_spaces=1 "
    "-c tessedit_do_invert=0 "
    "-c language_model_penalty_non_dict_word=0.25 "
    "-c language_model_penalty_non_freq_dict_word=0.2"
)


def _render_page(page: fitz.Page, dpi: int = DPI) -> np.ndarray:
    """페이지를 RGB numpy array로 렌더링. DPI 300 고정."""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)


def _ocr_single(pil_img: Image.Image) -> str:
    """Tesseract 단일 호출. kor+eng 실패 시 kor 폴백."""
    try:
        return pytesseract.image_to_string(
            pil_img,
            lang=LANG,
            config=TESS_CONFIG,
        ).strip()
    except pytesseract.TesseractError as e:
        if LANG == "kor+eng":
            logging.warning("kor+eng 실패, kor 폴백: %s", str(e)[:100])
            try:
                return pytesseract.image_to_string(
                    pil_img,
                    lang="kor",
                    config=TESS_CONFIG,
                ).strip()
            except pytesseract.TesseractError:
                return ""
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

        if HYBRID_OCR:
            text = ocr_page_hybrid(preprocessed)
        else:
            pil_img = Image.fromarray(preprocessed)
            text = _ocr_single(pil_img)
        text = correct_ocr_text(text)

        elapsed = time.perf_counter() - t0
        logging.info(
            "OCR page=%d elapsed=%.2fs shape=%s dpi=%d hybrid=%s",
            idx + 1,
            elapsed,
            preprocessed.shape,
            DPI,
            HYBRID_OCR,
        )
        if elapsed > 3.0:
            logging.warning("OCR page=%d 병목: %.2fs > 3초", idx + 1, elapsed)

        ndjson = json.dumps({
            "page": idx + 1,
            "total": total,
            "method": "ocr_hybrid" if HYBRID_OCR else "ocr",
            "psm_used": "3" if HYBRID_OCR else "6",
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
        "psm": 3 if HYBRID_OCR else 6,
        "hybrid": HYBRID_OCR,
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
