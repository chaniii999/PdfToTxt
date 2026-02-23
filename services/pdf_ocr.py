"""PDF 텍스트 추출: 스캔 점수 분기 → 회전·deskew → 프리셋 OCR → 품질 게이트 → 레이아웃."""

import json
from typing import Generator

import fitz
import numpy as np
from PIL import Image
import pytesseract

from services.scan_detect import compute_scan_score, PAGE_DIRECT
from services.orientation import correct_orientation, hough_deskew
from services.preprocess import to_grayscale, crop_document_region, preprocess_for_ocr, PRESET_A
from services.layout import detect_regions, REGION_TABLE
from services.table_ocr import extract_table_text
from services.quality_gate import ocr_with_retry, OcrAttempt

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

TEXT_PSM = "--psm 6 --oem 3"


def _ocr_page(page: fitz.Page, lang: str) -> dict:
    """스캔본 특화 파이프라인: 렌더→crop→회전→deskew→전처리→품질게이트→레이아웃."""
    pix = page.get_pixmap(dpi=300, alpha=False)
    rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)

    gray = to_grayscale(rgb)
    cropped = crop_document_region(gray)
    oriented, rotated_deg = correct_orientation(cropped)
    deskewed, deskew_angle = hough_deskew(oriented)

    binary_a = preprocess_for_ocr(deskewed, preset=PRESET_A)
    regions = detect_regions(binary_a, lang=lang)

    parts: list[str] = []
    page_conf_list: list[float] = []

    if not regions:
        attempt = ocr_with_retry(
            binary_a, lang=lang,
            preprocess_fn=lambda p: preprocess_for_ocr(deskewed, preset=p),
        )
        parts.append(attempt.text.strip())
        page_conf_list.append(attempt.avg_conf)
        return _build_meta(parts, page_conf_list, attempt, rotated_deg, deskew_angle)

    best_attempt: OcrAttempt | None = None
    for region in regions:
        crop = binary_a[region.y:region.y + region.h, region.x:region.x + region.w]
        if crop.size == 0:
            continue
        if region.kind == REGION_TABLE:
            text = extract_table_text(crop, lang=lang)
            page_conf_list.append(0)
        else:
            attempt = ocr_with_retry(
                crop, lang=lang,
                preprocess_fn=lambda p, g=deskewed, r=region: preprocess_for_ocr(
                    g[r.y:r.y + r.h, r.x:r.x + r.w], preset=p,
                ),
            )
            text = attempt.text
            page_conf_list.append(attempt.avg_conf)
            if best_attempt is None or attempt.avg_conf > best_attempt.avg_conf:
                best_attempt = attempt
        if text.strip():
            parts.append(text.strip())

    meta_attempt = best_attempt or OcrAttempt("", 0.0, TEXT_PSM, PRESET_A)
    return _build_meta(parts, page_conf_list, meta_attempt, rotated_deg, deskew_angle)


def _build_meta(parts: list[str], confs: list[float], attempt: OcrAttempt, rotated_deg: int, deskew_angle: float) -> dict:
    avg_conf = round(sum(confs) / max(len(confs), 1), 1)
    return {
        "text": "\n\n".join(p for p in parts if p),
        "avg_conf": avg_conf,
        "psm_used": attempt.psm_used,
        "preset_used": attempt.preset_used,
        "rotated_deg": rotated_deg,
        "deskew_angle": deskew_angle,
    }


def extract_text_stream(pdf_bytes: bytes, lang: str = "kor+eng") -> Generator[str, None, None]:
    """페이지별 스캔 점수 분기 → 직접 추출 or OCR → NDJSON 스트리밍."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    all_parts: list[str] = []
    all_methods: list[str] = []

    try:
        for idx, page in enumerate(doc):
            try:
                score = compute_scan_score(page)

                if score.decision == PAGE_DIRECT:
                    text = page.get_text("text").strip()
                    method = "direct"
                    meta = {
                        "avg_conf": 100, "psm_used": "n/a",
                        "preset_used": "n/a", "rotated_deg": 0, "deskew_angle": 0,
                    }
                else:
                    result = _ocr_page(page, lang)
                    text = result["text"]
                    method = "ocr"
                    meta = {k: result[k] for k in ("avg_conf", "psm_used", "preset_used", "rotated_deg", "deskew_angle")}

                if text:
                    all_parts.append(text)
                method_label = f"p{idx + 1}:{method}"
                all_methods.append(method_label)

                yield json.dumps({
                    "page": idx + 1,
                    "total": total,
                    "method": method,
                    "scan_score": {
                        "words": score.word_count,
                        "text_area": score.text_area_ratio,
                        "img_area": score.image_area_ratio,
                    },
                    **meta,
                }) + "\n"

            except Exception as page_err:
                all_methods.append(f"p{idx + 1}:error")
                yield json.dumps({
                    "page": idx + 1,
                    "total": total,
                    "method": "error",
                    "error": str(page_err)[:200],
                }) + "\n"

    finally:
        doc.close()

    yield json.dumps({
        "done": True,
        "text": "\n\n".join(all_parts) if all_parts else "",
        "methods": all_methods,
    }) + "\n"
