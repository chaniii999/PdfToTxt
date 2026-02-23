"""표(Table) OCR: 선 제거 후 셀 OCR + 텍스트박스 기반 폴백."""

import cv2
import numpy as np
import pytesseract
from PIL import Image

TABLE_PSM = "--psm 6 --oem 3"


def _remove_lines(binary: np.ndarray) -> np.ndarray:
    """표 선(수평/수직)을 마스크로 제거. 셀 내부 텍스트 인식률 향상."""
    h, w = binary.shape[:2]
    inverted = cv2.bitwise_not(binary)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 15, 20), 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(h // 15, 20)))
    h_lines = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, h_kernel)
    v_lines = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, v_kernel)
    line_mask = cv2.add(h_lines, v_lines)
    cleaned = cv2.add(binary, line_mask)
    return cleaned


def _sort_cells(cells: list[tuple[int, int, int, int]], row_tolerance: int = 15) -> list[list[tuple[int, int, int, int]]]:
    if not cells:
        return []
    cells_sorted = sorted(cells, key=lambda c: (c[1], c[0]))
    rows: list[list[tuple[int, int, int, int]]] = []
    current_row = [cells_sorted[0]]
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


def _detect_cells_by_lines(table_img: np.ndarray) -> list[list[tuple[int, int, int, int]]]:
    """선 기반 셀 경계 감지."""
    h, w = table_img.shape[:2]
    inverted = cv2.bitwise_not(table_img)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 15, 20), 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(h // 15, 20)))
    grid = cv2.add(cv2.morphologyEx(inverted, cv2.MORPH_OPEN, h_kernel), cv2.morphologyEx(inverted, cv2.MORPH_OPEN, v_kernel))
    grid = cv2.dilate(grid, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)
    contours, _ = cv2.findContours(grid, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    min_area = (w * h) * 0.001
    cells = []
    for cnt in contours:
        cx, cy, cw, ch = cv2.boundingRect(cnt)
        if min_area < cw * ch < w * h * 0.95 and cw > 15 and ch > 10:
            cells.append((cx, cy, cw, ch))
    return _sort_cells(cells)


def _reconstruct_table_by_textbox(binary: np.ndarray, lang: str) -> str:
    """텍스트 박스 좌표 기반 행·열 클러스터링 → 마크다운 테이블 재구성."""
    try:
        data = pytesseract.image_to_data(Image.fromarray(binary), lang=lang, config=TABLE_PSM, output_type=pytesseract.Output.DICT)
    except Exception:
        return ""
    entries = []
    for i in range(len(data["text"])):
        if int(data["conf"][i]) < 10 or not data["text"][i].strip():
            continue
        entries.append({"x": data["left"][i], "y": data["top"][i], "w": data["width"][i], "h": data["height"][i], "text": data["text"][i]})
    if not entries:
        return ""

    entries.sort(key=lambda e: e["y"])
    rows: list[list[dict]] = []
    current_row = [entries[0]]
    current_y = entries[0]["y"]
    for e in entries[1:]:
        if abs(e["y"] - current_y) <= 15:
            current_row.append(e)
        else:
            current_row.sort(key=lambda e: e["x"])
            rows.append(current_row)
            current_row = [e]
            current_y = e["y"]
    current_row.sort(key=lambda e: e["x"])
    rows.append(current_row)

    md_lines = []
    for idx, row in enumerate(rows):
        cells_text = [e["text"] for e in row]
        md_lines.append("| " + " | ".join(cells_text) + " |")
        if idx == 0:
            md_lines.append("|" + "|".join(["---"] * len(cells_text)) + "|")
    return "\n".join(md_lines)


def extract_table_text(binary_img: np.ndarray, lang: str = "kor+eng") -> str:
    """선 제거 후 셀 OCR → 실패 시 텍스트박스 기반 재구성 폴백."""
    cleaned = _remove_lines(binary_img)
    rows = _detect_cells_by_lines(binary_img)

    if rows:
        md_lines = []
        for row_idx, row in enumerate(rows):
            cells_text = []
            for (cx, cy, cw, ch) in row:
                pad = 2
                cell_img = cleaned[max(cy + pad, 0):min(cy + ch - pad, cleaned.shape[0]), max(cx + pad, 0):min(cx + cw - pad, cleaned.shape[1])]
                if cell_img.size == 0:
                    cells_text.append("")
                    continue
                try:
                    txt = pytesseract.image_to_string(cell_img, lang=lang, config=TABLE_PSM).strip().replace("\n", " ")
                except Exception:
                    txt = ""
                cells_text.append(txt)
            md_lines.append("| " + " | ".join(cells_text) + " |")
            if row_idx == 0:
                md_lines.append("|" + "|".join(["---"] * len(cells_text)) + "|")
        return "\n".join(md_lines)

    fallback = _reconstruct_table_by_textbox(cleaned, lang)
    if fallback:
        return fallback
    try:
        return pytesseract.image_to_string(Image.fromarray(cleaned), lang=lang, config=TABLE_PSM)
    except Exception:
        return ""
