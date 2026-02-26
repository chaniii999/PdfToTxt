"""한글 문서 특화 최소 전처리: Grayscale, Deskew, Otsu, 획 구분 강화, 10px 테두리."""

import cv2
import numpy as np

DESKEW_MIN_ANGLE = 0.5  # 0.5도 이상일 때만 deskew 실행
BORDER_PX = 10  # Tesseract 권장 흰 테두리


def _sharpen_strokes(gray: np.ndarray, strength: float = 0.4) -> np.ndarray:
    """한글 자모 경계 선명화. ㅇ/ㅁ, ㅈ/ㅅ 등 획 구분 개선."""
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


def to_grayscale(img: np.ndarray) -> np.ndarray:
    """RGB → Grayscale."""
    if len(img.shape) == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)


def otsu_binarize(gray: np.ndarray) -> np.ndarray:
    """Otsu threshold 이진화."""
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def add_ocr_border(img: np.ndarray, border_px: int = BORDER_PX, color: int = 255) -> np.ndarray:
    """Tesseract 권장 10px 흰 테두리."""
    if len(img.shape) == 3:
        value = (color, color, color)
    else:
        value = color
    return cv2.copyMakeBorder(
        img, border_px, border_px, border_px, border_px,
        cv2.BORDER_CONSTANT, value=value,
    )


def hough_deskew(gray: np.ndarray, max_angle: float = 15.0) -> tuple[np.ndarray, float]:
    """Hough 변환으로 텍스트 라인 각도 추정. (보정 이미지, 각도) 반환."""
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=50, maxLineGap=10)

    if lines is None or len(lines) == 0:
        return gray, 0.0

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        dx = x2 - x1
        dy = y2 - y1
        if abs(dx) < 5:
            continue
        angle = np.degrees(np.arctan2(dy, dx))
        if abs(angle) <= max_angle:
            angles.append(angle)

    if not angles:
        return gray, 0.0

    median_angle = float(np.median(angles))
    if abs(median_angle) < DESKEW_MIN_ANGLE:
        return gray, 0.0

    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(
        gray, matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated, round(median_angle, 2)


def preprocess_minimal(rgb: np.ndarray) -> np.ndarray:
    """전처리: Grayscale → Sharpen → Deskew → Otsu → Morphology → 10px 테두리."""
    gray = to_grayscale(rgb)
    sharpened = _sharpen_strokes(gray)
    deskewed, _ = hough_deskew(sharpened)
    binary = otsu_binarize(deskewed)
    connected = _morphology_connect_strokes(binary)
    return add_ocr_border(connected)
