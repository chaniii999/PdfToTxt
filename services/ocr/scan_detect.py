"""스캔 판별: 텍스트 밀도·이미지 비율·단어 수로 페이지가 스캔본인지 판단."""

from dataclasses import dataclass

import fitz

PAGE_DIRECT = "direct"
PAGE_OCR = "ocr"

MIN_WORDS = 10
MIN_TEXT_AREA_RATIO = 0.05
MIN_WORD_LENGTH_AVG = 1.5


@dataclass
class ScanScore:
    word_count: int
    text_area_ratio: float
    image_area_ratio: float
    decision: str  # "direct" | "ocr"


def compute_scan_score(page: fitz.Page) -> ScanScore:
    """페이지의 텍스트/이미지 특성 분석 후 직접 추출 vs OCR 결정."""
    page_area = page.rect.width * page.rect.height
    if page_area == 0:
        return ScanScore(0, 0.0, 0.0, PAGE_OCR)

    words = page.get_text("words")
    word_count = len(words)

    text_area = 0.0
    for w in words:
        text_area += (w[2] - w[0]) * (w[3] - w[1])
    text_area_ratio = text_area / page_area if page_area else 0.0

    image_area = 0.0
    for img in page.get_images(full=True):
        try:
            xref = img[0]
            rects = page.get_image_rects(xref)
            for r in rects:
                image_area += r.width * r.height
        except Exception:
            pass
    image_area_ratio = image_area / page_area if page_area else 0.0

    text_content = page.get_text("text").strip()
    avg_word_len = len(text_content) / max(word_count, 1)

    is_reliable_text = (
        word_count >= MIN_WORDS
        and text_area_ratio >= MIN_TEXT_AREA_RATIO
        and avg_word_len >= MIN_WORD_LENGTH_AVG
    )

    if is_reliable_text and image_area_ratio < 0.8:
        decision = PAGE_DIRECT
    else:
        decision = PAGE_OCR

    return ScanScore(
        word_count=word_count,
        text_area_ratio=round(text_area_ratio, 4),
        image_area_ratio=round(image_area_ratio, 4),
        decision=decision,
    )
