"""PDF 텍스트 추출: 디지털 PDF는 직접 추출, 스캔본은 레이아웃 분석 OCR. 스트리밍 지원."""

import json
from typing import Generator

import fitz
import pytesseract
import numpy as np
from PIL import Image

from services.preprocess import preprocess_for_ocr
from services.layout import detect_regions, REGION_TABLE, REGION_TEXT
from services.table_ocr import extract_table_text

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"  # 환경에 맞게 수정

TEXT_PSM = "--psm 6 --oem 3"
MIN_TEXT_LENGTH = 30


def _ocr_page(page: fitz.Page, lang: str) -> str:
    """레이아웃 분석 → 영역별(텍스트/표) 최적 OCR → 결합."""
    pix = page.get_pixmap(dpi=300, alpha=False)
    rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    binary = preprocess_for_ocr(rgb)

    regions = detect_regions(binary)
    if not regions:
        return pytesseract.image_to_string(
            Image.fromarray(binary), lang=lang, config=TEXT_PSM,
        )

    parts = []
    for region in regions:
        crop = binary[region.y:region.y + region.h, region.x:region.x + region.w]
        if crop.size == 0:
            continue
        if region.kind == REGION_TABLE:
            text = extract_table_text(crop, lang=lang)
        else:
            text = pytesseract.image_to_string(
                Image.fromarray(crop), lang=lang, config=TEXT_PSM,
            )
        if text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


def extract_text_stream(pdf_bytes: bytes, lang: str = "kor+eng") -> Generator[str, None, None]:
    """페이지별 진행 상태를 NDJSON으로 yield. 마지막에 전체 결과 yield."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    parts = []
    methods = []
    try:
        for idx, page in enumerate(doc):
            text = page.get_text("text")
            method = "direct"
            if len(text.strip()) < MIN_TEXT_LENGTH:
                text = _ocr_page(page, lang)
                method = "ocr"
            if text.strip():
                parts.append(text.strip())
            methods.append(f"p{idx + 1}:{method}")
            yield json.dumps({
                "page": idx + 1,
                "total": total,
                "method": method,
            }) + "\n"
    finally:
        doc.close()
    yield json.dumps({
        "done": True,
        "text": "\n\n".join(parts) if parts else "",
        "methods": methods,
    }) + "\n"
