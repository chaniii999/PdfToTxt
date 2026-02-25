"""스캔본 이미지 전처리: 프리셋 A/B/C, 외곽 제거, 조건부 denoise."""

import cv2
import numpy as np

PRESET_A = "A"
PRESET_B = "B"
PRESET_C = "C"


def crop_border(gray: np.ndarray, margin_pct: float = 0.015) -> np.ndarray:
    """외곽 마진(기본 1.5%) 제거. 스캔 그림자·펀치홀·바인딩 영역 제거."""
    h, w = gray.shape
    my = int(h * margin_pct)
    mx = int(w * margin_pct)
    return gray[my:h - my, mx:w - mx]


def crop_document_region(gray: np.ndarray) -> np.ndarray:
    """가장 큰 사각형 컨투어를 찾아 문서 영역만 crop. 실패 시 마진 crop."""
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return crop_border(gray)
    largest = max(contours, key=cv2.contourArea)
    area_ratio = cv2.contourArea(largest) / (gray.shape[0] * gray.shape[1])
    if area_ratio < 0.3:
        return crop_border(gray)
    x, y, w, h = cv2.boundingRect(largest)
    return gray[y:y + h, x:x + w]


def denoise_adaptive(gray: np.ndarray) -> np.ndarray:
    """노이즈 타입에 따라 적절한 필터 선택."""
    noise_level = float(np.std(gray[gray > 20]))
    if noise_level > 60:
        return cv2.medianBlur(gray, 3)
    return cv2.bilateralFilter(gray, d=5, sigmaColor=40, sigmaSpace=40)


def _preset_a(gray: np.ndarray) -> np.ndarray:
    """프리셋 A(일반): denoise → adaptive gaussian 이진화."""
    cleaned = denoise_adaptive(gray)
    return cv2.adaptiveThreshold(cleaned, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)


def _preset_b(gray: np.ndarray) -> np.ndarray:
    """프리셋 B(그림자/얼룩 심함): CLAHE → denoise → adaptive 이진화."""
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    cleaned = denoise_adaptive(enhanced)
    return cv2.adaptiveThreshold(cleaned, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 8)


def _preset_c(gray: np.ndarray) -> np.ndarray:
    """프리셋 C(저대비/글자 연함): CLAHE → Otsu → morphology close."""
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)


PRESET_MAP = {PRESET_A: _preset_a, PRESET_B: _preset_b, PRESET_C: _preset_c}


def to_grayscale(img: np.ndarray) -> np.ndarray:
    if len(img.shape) == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)


def binarize(gray: np.ndarray, preset: str = PRESET_A) -> np.ndarray:
    """이미 crop된 grayscale 이미지에 프리셋별 이진화만 수행."""
    fn = PRESET_MAP.get(preset, _preset_a)
    return fn(gray)


def preprocess_for_ocr(rgb_array: np.ndarray, preset: str = PRESET_A) -> np.ndarray:
    """전체 파이프라인(최초 입력용): 그레이스케일 → 외곽 제거 → 프리셋별 이진화."""
    gray = to_grayscale(rgb_array)
    cropped = crop_document_region(gray)
    return binarize(cropped, preset)
