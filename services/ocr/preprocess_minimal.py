"""최소 전처리: Grayscale → CLAHE → Sharpen(획 구분) → Otsu → Morphology(끊긴 획) → 10px 테두리.

자모 혼동 완화: ㅇ/ㅁ(성↔섬, 많↔않), ㅔ/ㅖ(페↔폐), ㅡ+ㅣ/ㅣ+ㄱ(의↔익).
"""

import cv2
import numpy as np

BORDER_PX = 10
SHARPEN_STRENGTH = 0.55  # ㅇ/ㅁ, ㅔ/ㅖ 등 자모 경계 선명화 강화
CLIP_LIMIT = 2.5  # CLAHE. 얇은 획(ㅖ 가로선 등) 보존


def to_grayscale(img: np.ndarray) -> np.ndarray:
    if len(img.shape) == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)


def _clahe_contrast(gray: np.ndarray, clip_limit: float = CLIP_LIMIT, grid_size: int = 8) -> np.ndarray:
    """저대비 영역 대비 향상. 얇은 획(ㅖ 가로선 등)·자모 경계 가독성 개선."""
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(grid_size, grid_size))
    return clahe.apply(gray)


def _sharpen_strokes(gray: np.ndarray, strength: float = SHARPEN_STRENGTH) -> np.ndarray:
    """한글 자모 경계 선명화. ㅇ/ㅁ, ㅈ/ㅅ, ㅓ/ㅣ 등 획 구분 개선."""
    kernel = np.array([
        [0, -1, 0],
        [-1, 5, -1],
        [0, -1, 0],
    ], dtype=np.float32)
    sharpened = cv2.filter2D(gray.astype(np.float32), -1, kernel)
    return np.clip(gray.astype(np.float32) * (1 - strength) + sharpened * strength, 0, 255).astype(np.uint8)


def _morphology_connect_strokes(binary: np.ndarray) -> np.ndarray:
    """끊긴 한글 획 연결. morphology close (작은 kernel)."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)


def otsu_binarize(gray: np.ndarray) -> np.ndarray:
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def add_ocr_border(img: np.ndarray, border_px: int = BORDER_PX, color: int = 255) -> np.ndarray:
    if len(img.shape) == 3:
        value = (color, color, color)
    else:
        value = color
    return cv2.copyMakeBorder(
        img, border_px, border_px, border_px, border_px,
        cv2.BORDER_CONSTANT, value=value,
    )


def preprocess_minimal(rgb: np.ndarray) -> np.ndarray:
    """Grayscale → CLAHE → Sharpen → Otsu → Morphology → 10px 테두리."""
    gray = to_grayscale(rgb)
    contrasted = _clahe_contrast(gray)
    sharpened = _sharpen_strokes(contrasted)
    binary = otsu_binarize(sharpened)
    connected = _morphology_connect_strokes(binary)
    return add_ocr_border(connected)
