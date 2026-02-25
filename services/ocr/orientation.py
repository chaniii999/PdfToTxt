"""회전(0/90/180/270) 감지 및 Hough 기반 미세 deskew."""

import cv2
import numpy as np
import pytesseract


def detect_orientation(gray: np.ndarray) -> int:
    """Tesseract OSD로 페이지 회전각(0/90/180/270) 감지. 실패 시 0."""
    if gray.size == 0 or min(gray.shape[:2]) < 100:
        return 0
    try:
        from PIL import Image
        pil_img = Image.fromarray(gray)
        osd = pytesseract.image_to_osd(pil_img, output_type=pytesseract.Output.DICT)
        angle = int(osd.get("rotate", 0))
        if angle in (0, 90, 180, 270):
            return angle
        return 0
    except Exception:
        return 0


def correct_orientation(gray: np.ndarray) -> tuple[np.ndarray, int]:
    """회전각 감지 후 보정. (보정된 이미지, 적용된 회전각) 반환."""
    angle = detect_orientation(gray)
    if angle == 0:
        return gray, 0
    h, w = gray.shape[:2]
    if angle == 90:
        return cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE), angle
    if angle == 180:
        return cv2.rotate(gray, cv2.ROTATE_180), angle
    if angle == 270:
        return cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE), angle
    return gray, 0


def hough_deskew(gray: np.ndarray, max_angle: float = 15.0) -> tuple[np.ndarray, float]:
    """Hough 변환으로 텍스트 라인 각도 추정 후 deskew. (보정 이미지, 각도) 반환."""
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
    if abs(median_angle) < 0.3:
        return gray, 0.0

    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated, round(median_angle, 2)


def deskew_rgb(rgb: np.ndarray, max_angle: float = 15.0) -> np.ndarray:
    """RGB 이미지에 Hough deskew 적용. I, L, 1 오인식 완화."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    deskewed_gray, angle = hough_deskew(gray, max_angle)
    if abs(angle) < 0.3:
        return rgb
    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        rgb, matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
