"""스캔본 이미지 전처리: 그레이스케일, 기울기 보정, 노이즈 제거, 이진화."""

import cv2
import numpy as np


def to_grayscale(img: np.ndarray) -> np.ndarray:
    """BGR/RGB → 그레이스케일. 이미 단일 채널이면 그대로."""
    if len(img.shape) == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)


def deskew(gray: np.ndarray) -> np.ndarray:
    """텍스트 기울기 감지 후 보정. 기울기가 작으면(<0.5도) 그대로 반환."""
    coords = np.column_stack(np.where(gray < 128))
    if len(coords) < 100:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.5:
        return gray
    h, w = gray.shape
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        gray, matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def denoise(gray: np.ndarray) -> np.ndarray:
    """bilateral 필터로 글자 경계는 유지하면서 노이즈 제거."""
    return cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)


def binarize(gray: np.ndarray) -> np.ndarray:
    """적응형 이진화. 조명 불균형·그림자가 있는 스캔본에 효과적."""
    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=10,
    )


def preprocess_for_ocr(rgb_array: np.ndarray) -> np.ndarray:
    """전처리 파이프라인: 그레이스케일 → 기울기 보정 → 노이즈 제거 → 이진화."""
    gray = to_grayscale(rgb_array)
    straightened = deskew(gray)
    cleaned = denoise(straightened)
    binary = binarize(cleaned)
    return binary
