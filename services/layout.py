"""레이아웃 분석: 페이지 이미지에서 표/텍스트 영역 감지 및 분류."""

from dataclasses import dataclass

import cv2
import numpy as np

REGION_TEXT = "text"
REGION_TABLE = "table"


@dataclass
class Region:
    x: int
    y: int
    w: int
    h: int
    kind: str  # "text" | "table"


def _detect_lines(binary: np.ndarray, horizontal: bool) -> np.ndarray:
    """모폴로지로 수평 또는 수직 선분 검출."""
    h, w = binary.shape
    inverted = cv2.bitwise_not(binary)
    if horizontal:
        kernel_len = max(w // 20, 30)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_len, 1))
    else:
        kernel_len = max(h // 20, 30)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kernel_len))
    return cv2.morphologyEx(inverted, cv2.MORPH_OPEN, kernel, iterations=1)


def _find_table_regions(binary: np.ndarray, min_area_ratio: float = 0.005) -> list[tuple[int, int, int, int]]:
    """수평+수직 선 교차점으로 표 영역 후보 추출."""
    h_lines = _detect_lines(binary, horizontal=True)
    v_lines = _detect_lines(binary, horizontal=False)
    combined = cv2.add(h_lines, v_lines)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    combined = cv2.dilate(combined, kernel, iterations=2)

    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_area = binary.shape[0] * binary.shape[1]
    tables = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w * h > img_area * min_area_ratio and w > 60 and h > 60:
            tables.append((x, y, w, h))
    return tables


def detect_regions(binary: np.ndarray) -> list[Region]:
    """페이지에서 표 영역과 텍스트 영역을 구분해 위→아래 순서로 반환."""
    img_h, img_w = binary.shape
    table_boxes = _find_table_regions(binary)

    regions: list[Region] = []
    covered_rows = set()

    for (x, y, w, h) in table_boxes:
        regions.append(Region(x=x, y=y, w=w, h=h, kind=REGION_TABLE))
        for row in range(y, y + h):
            covered_rows.add(row)

    text_start = None
    for row in range(img_h):
        in_table = row in covered_rows
        if not in_table and text_start is None:
            text_start = row
        elif in_table and text_start is not None:
            row_h = row - text_start
            if row_h > 20:
                regions.append(Region(x=0, y=text_start, w=img_w, h=row_h, kind=REGION_TEXT))
            text_start = None

    if text_start is not None:
        row_h = img_h - text_start
        if row_h > 20:
            regions.append(Region(x=0, y=text_start, w=img_w, h=row_h, kind=REGION_TEXT))

    regions.sort(key=lambda r: r.y)
    return regions
