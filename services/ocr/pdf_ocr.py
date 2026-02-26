"""PDF 텍스트 추출: 핵심 세팅만. 전략 재설계용 최소 파이프라인."""

import asyncio
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import AsyncGenerator

import fitz
import cv2
import numpy as np
from PIL import Image
import pytesseract

from services.ocr.preprocess_minimal import (
    BORDER_PX,
    preprocess_minimal,
    UPSCALE_FACTOR,
)
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

# user_words, user_patterns (의/익/폐/페 문맥 보정)
_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "tesseract"
_USER_WORDS = _CONFIG_DIR / "user_words.txt"
_USER_PATTERNS = _CONFIG_DIR / "user_patterns.txt"
_user_config = ""
if _USER_WORDS.exists():
    _user_config += f" -c user_words_file={_USER_WORDS}"
if _USER_PATTERNS.exists():
    _user_config += f" -c user_patterns_file={_USER_PATTERNS}"

TESS_CONFIG = (
    "--oem 1 --psm 6 "
    "-c preserve_interword_spaces=1 -c tessedit_do_invert=0 "
    "-c language_model_penalty_non_dict_word=0.25 "
    "-c language_model_penalty_non_freq_dict_word=0.2"
    f"{_user_config}"
).strip()

OCR_2PASS = os.environ.get("OCR_2PASS", "0").lower() in ("1", "true", "yes")

# 멀티프로세싱: i5-6600(4코어) 기준 3 workers. Tesseract는 subprocess라 코어당 1개.
_CPU_COUNT = os.cpu_count() or 4
OCR_MAX_WORKERS = int(os.environ.get("OCR_MAX_WORKERS", "0")) or max(1, min(3, _CPU_COUNT))
OCR_USE_MULTIPROCESS = os.environ.get("OCR_USE_MULTIPROCESS", "1").lower() in ("1", "true", "yes")

# 디지털 PDF 판별: 텍스트 레이어 단어 수 임계값
_DIRECT_WORD_MIN = 10


def _is_digital_page(page: fitz.Page) -> bool:
    """텍스트 레이어가 충분하면 디지털 PDF로 판별."""
    words = page.get_text("words")
    return len(words) >= _DIRECT_WORD_MIN


def _render_page(page: fitz.Page, dpi: int = DPI) -> np.ndarray:
    """페이지를 RGB numpy array로 렌더링."""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)


def _ocr_single(pil_img: Image.Image, rgb_original: np.ndarray | None = None) -> str:
    """1차 kor → 2차 eng(영어 의심후보군만). 실패 시 OCR_2PASS 또는 kor 단일 폴백."""
    from services.ocr.ocr_twostage import ocr_page_twostage
    try:
        return ocr_page_twostage(
            pil_img,
            TESS_CONFIG,
            rgb_original=rgb_original,
            scale=UPSCALE_FACTOR,
            border=BORDER_PX,
        )
    except Exception:
        pass
    if OCR_2PASS:
        from services.ocr.ocr_twopass import ocr_page_twopass
        try:
            return ocr_page_twopass(pil_img, TESS_CONFIG, LANG)
        except Exception:
            pass
    try:
        return pytesseract.image_to_string(
            pil_img, lang=LANG, config=TESS_CONFIG,
        ).strip()
    except Exception:
        return ""


def _process_page_sync(
    page: fitz.Page, idx: int, total: int, force_ocr: bool = False
) -> tuple[str, str, str]:
    """단일 페이지 처리. (NDJSON 줄, 텍스트, method) 반환. method: direct | ocr | error."""
    try:
        if force_ocr:
            use_ocr = True
        else:
            use_ocr = not _is_digital_page(page)

        if use_ocr:
            rgb = _render_page(page)
            preprocessed = preprocess_minimal(rgb)
            pil_img = Image.fromarray(preprocessed)
            text = _ocr_single(pil_img, rgb_original=rgb)
            text = correct_ocr_text(text)
            method = "ocr"
        else:
            text = page.get_text().strip()
            method = "direct"

        ndjson = json.dumps({
            "page": idx + 1,
            "total": total,
            "method": method,
            "dpi": DPI if use_ocr else None,
            "text": text,
        }) + "\n"
        return ndjson, text, method
    except Exception as err:
        ndjson = json.dumps({
            "page": idx + 1,
            "total": total,
            "method": "error",
            "error": str(err)[:200],
            "text": "",
        }) + "\n"
        return ndjson, "", "error"


def _process_page_worker(args: tuple) -> tuple[str, str, str]:
    """
    ProcessPoolExecutor용 워커. PDF 바이트·인덱스만 전달 (pickle 가능).
    프로세스당 독립 Tesseract subprocess 실행.
    """
    pdf_bytes, idx, total, force_ocr = args
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[idx]
        return _process_page_sync(page, idx, total, force_ocr)
    finally:
        doc.close()


def _run_pages_parallel(
    pdf_bytes: bytes, total: int, force_ocr: bool, max_workers: int
) -> list[tuple[str, str, str]]:
    """ProcessPoolExecutor로 페이지 병렬 처리. 결과는 페이지 순서 유지."""
    tasks = [(pdf_bytes, idx, total, force_ocr) for idx in range(total)]
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(_process_page_worker, tasks, chunksize=1))


async def extract_text_stream(
    pdf_bytes: bytes,
    force_ocr: bool | None = None,
) -> AsyncGenerator[str, None]:
    """페이지별 NDJSON 스트리밍. force_ocr=True면 모든 페이지 OCR 강제."""
    force = force_ocr or False
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    all_parts: list[str] = []
    all_methods: list[str] = []

    workers = min(OCR_MAX_WORKERS, total) if (OCR_USE_MULTIPROCESS and total >= 2) else 1
    yield json.dumps({
        "page": 0, "total": total, "method": "started", "dpi": DPI, "psm": 6,
        "workers": workers if OCR_USE_MULTIPROCESS else None,
    }) + "\n"
    await asyncio.sleep(0)

    try:
        use_parallel = (
            OCR_USE_MULTIPROCESS
            and total >= 2
            and OCR_MAX_WORKERS >= 2
        )
        if use_parallel:
            workers = min(OCR_MAX_WORKERS, total)
            results = await asyncio.to_thread(
                _run_pages_parallel, pdf_bytes, total, force, workers
            )
            for ndjson_line, text, method in results:
                all_parts.append(text)
                all_methods.append(f"p{len(all_parts)}:{method}")
                yield ndjson_line
                await asyncio.sleep(0)
        else:
            for idx in range(total):
                page = doc[idx]
                ndjson_line, text, method = await asyncio.to_thread(
                    _process_page_sync, page, idx, total, force
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
        "methods": [m for m in all_methods if m],
    }) + "\n"
