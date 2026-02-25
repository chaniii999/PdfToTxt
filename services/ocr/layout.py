"""레이아웃 분석: 선 기반(Track 1) + 텍스트 박스 기반(Track 2) 표/텍스트 영역 감지."""

from dataclasses import dataclass

import cv2
import numpy as np
import pytesseract
from PIL import Image

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
    h, w = binary.shape
    inverted = cv2.bitwise_not(binary)
    if horizontal:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 20, 30), 1))
    else:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(h // 20, 30)))
    return cv2.morphologyEx(inverted, cv2.MORPH_OPEN, kernel, iterations=1)


def _find_table_regions_by_lines(binary: np.ndarray, min_area_ratio: float = 0.005) -> list[tuple[int, int, int, int]]:
    """Track 1: 수평+수직 선 교차로 표 영역 추출."""
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


def _find_table_regions_by_textbox(binary: np.ndarray, lang: str = "kor+eng") -> list[tuple[int, int, int, int]]:
    """Track 2: image_to_data로 단어 박스 추출 후 격자 패턴 감지."""
    try:
        pil_img = Image.fromarray(binary)
        data = pytesseract.image_to_data(pil_img, lang=lang, config="--psm 6 --oem 3", output_type=pytesseract.Output.DICT)
    except Exception:
        return []

    boxes = []
    for i in range(len(data["text"])):
        if int(data["conf"][i]) < 10 or not data["text"][i].strip():
            continue
        boxes.append((data["left"][i], data["top"][i], data["width"][i], data["height"][i]))
    if len(boxes) < 6:
        return []

    y_coords = sorted(set(b[1] for b in boxes))
    rows_grouped = _group_by_proximity(y_coords, tolerance=15)
    if len(rows_grouped) < 3:
        return []

    col_counts = []
    for row_y_list in rows_grouped:
        y_min, y_max = min(row_y_list), max(row_y_list) + 20
        row_boxes = [b for b in boxes if y_min <= b[1] <= y_max]
        col_counts.append(len(row_boxes))

    if len(col_counts) < 3:
        return []
    median_cols = sorted(col_counts)[len(col_counts) // 2]
    consistent = sum(1 for c in col_counts if abs(c - median_cols) <= 1)
    if consistent / len(col_counts) < 0.6 or median_cols < 2:
        return []

    all_x = [b[0] for b in boxes]
    all_y = [b[1] for b in boxes]
    all_r = [b[0] + b[2] for b in boxes]
    all_b = [b[1] + b[3] for b in boxes]
    return [(min(all_x), min(all_y), max(all_r) - min(all_x), max(all_b) - min(all_y))]


def _group_by_proximity(values: list[int], tolerance: int = 15) -> list[list[int]]:
    if not values:
        return []
    groups: list[list[int]] = [[values[0]]]
    for v in values[1:]:
        if abs(v - groups[-1][-1]) <= tolerance:
            groups[-1].append(v)
        else:
            groups.append([v])
    return groups


def detect_regions(binary: np.ndarray, lang: str = "kor+eng") -> list[Region]:
    """Track 1(선 기반) → Track 2(텍스트 박스 기반) 순으로 표 감지 후 영역 반환."""
    img_h, img_w = binary.shape
    table_boxes = _find_table_regions_by_lines(binary)
    if not table_boxes:
        table_boxes = _find_table_regions_by_textbox(binary, lang=lang)

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
