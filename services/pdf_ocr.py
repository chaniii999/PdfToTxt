"""PDF 텍스트 추출: 디지털 PDF는 직접 추출, 스캔본은 OCR 폴백. 스트리밍 지원."""

import json
from typing import Generator

import fitz
import pytesseract
import cv2
import numpy as np
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"  # 환경에 맞게 수정

TESSERACT_CONFIG = "--psm 3 --oem 3"
MIN_TEXT_LENGTH = 30


def _preprocess_for_ocr(pil_img: Image.Image) -> Image.Image:
    """그레이스케일 → 노이즈 제거 → 이진화 후 PIL Image 반환."""
    arr = np.array(pil_img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    denoised = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)
    _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(binary)


def _ocr_page(page: fitz.Page, lang: str) -> str:
    """페이지를 이미지로 변환 후 전처리 → Tesseract OCR."""
    pix = page.get_pixmap(dpi=300, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    img = _preprocess_for_ocr(img)
    return pytesseract.image_to_string(img, lang=lang, config=TESSERACT_CONFIG)


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
