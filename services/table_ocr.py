"""표(Table) 영역 셀 감지 및 구조화된 텍스트 추출."""

import cv2
import numpy as np
import pytesseract

TABLE_PSM = "--psm 6 --oem 3"


def _sort_cells(cells: list[tuple[int, int, int, int]], row_tolerance: int = 15) -> list[list[tuple[int, int, int, int]]]:
    """셀을 행·열 순으로 정렬. y좌표가 비슷하면(tolerance) 같은 행."""
    if not cells:
        return []
    cells_sorted = sorted(cells, key=lambda c: (c[1], c[0]))
    rows: list[list[tuple[int, int, int, int]]] = []
    current_row: list[tuple[int, int, int, int]] = [cells_sorted[0]]
    current_y = cells_sorted[0][1]

    for cell in cells_sorted[1:]:
        if abs(cell[1] - current_y) <= row_tolerance:
            current_row.append(cell)
        else:
            current_row.sort(key=lambda c: c[0])
            rows.append(current_row)
            current_row = [cell]
            current_y = cell[1]
    current_row.sort(key=lambda c: c[0])
    rows.append(current_row)
    return rows


def detect_cells(table_img: np.ndarray) -> list[list[tuple[int, int, int, int]]]:
    """표 이미지에서 셀 경계 감지 후 행·열 구조로 반환."""
    h, w = table_img.shape[:2]
    inverted = cv2.bitwise_not(table_img) if len(table_img.shape) == 2 else cv2.bitwise_not(cv2.cvtColor(table_img, cv2.COLOR_RGB2GRAY))

    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 15, 20), 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(h // 15, 20)))
    h_lines = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, h_kernel)
    v_lines = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, v_kernel)

    grid = cv2.add(h_lines, v_lines)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    grid = cv2.dilate(grid, kernel, iterations=1)

    contours, _ = cv2.findContours(grid, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    cells = []
    min_cell_area = (w * h) * 0.001
    for cnt in contours:
        cx, cy, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        if min_cell_area < area < (w * h * 0.95) and cw > 15 and ch > 10:
            cells.append((cx, cy, cw, ch))

    return _sort_cells(cells)


def extract_table_text(binary_img: np.ndarray, lang: str = "kor+eng") -> str:
    """표 이미지에서 셀별 OCR 후 마크다운 테이블로 반환."""
    rows = detect_cells(binary_img)
    if not rows:
        return pytesseract.image_to_string(binary_img, lang=lang, config=TABLE_PSM)

    md_lines = []
    for row_idx, row in enumerate(rows):
        cells_text = []
        for (cx, cy, cw, ch) in row:
            pad = 2
            y1 = max(cy + pad, 0)
            y2 = min(cy + ch - pad, binary_img.shape[0])
            x1 = max(cx + pad, 0)
            x2 = min(cx + cw - pad, binary_img.shape[1])
            cell_img = binary_img[y1:y2, x1:x2]
            if cell_img.size == 0:
                cells_text.append("")
                continue
            txt = pytesseract.image_to_string(
                cell_img, lang=lang, config=TABLE_PSM,
            ).strip().replace("\n", " ")
            cells_text.append(txt)
        md_lines.append("| " + " | ".join(cells_text) + " |")
        if row_idx == 0:
            md_lines.append("|" + "|".join(["---"] * len(cells_text)) + "|")
    return "\n".join(md_lines)
