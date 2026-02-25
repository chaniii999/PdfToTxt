"""OCR 품질 게이트: confidence 평가 + PSM/프리셋 변경 재시도(최대 3회)."""

from dataclasses import dataclass
import re

import numpy as np
import pytesseract
from PIL import Image

from services.ocr.preprocess import PRESET_A, PRESET_B

MIN_AVG_CONF = 55
MIN_KOREAN_RATIO = 0.10
MAX_ABNORMAL_RATIO = 0.35

KOREAN_RE = re.compile(r"[\uac00-\ud7a3]")
ABNORMAL_RE = re.compile(r"[|_~=\[\]{}<>]{2,}")

MAX_RETRY = 3
RETRY_PLAN: list[tuple[str, str]] = [
    ("--psm 6 --oem 3", PRESET_A),
    ("--psm 6 --oem 3", PRESET_B),
    ("--psm 4 --oem 3", PRESET_A),
]


@dataclass
class OcrAttempt:
    text: str
    avg_conf: float
    psm_used: str
    preset_used: str
    korean_ratio: float = 0.0
    abnormal_ratio: float = 0.0
    passed: bool = False


def _reconstruct_text(data: dict) -> str:
    """image_to_data 결과에서 block/par/line 구조를 살려 텍스트 복원."""
    lines: dict[tuple[int, int, int], list[str]] = {}
    for i in range(len(data["text"])):
        if int(data["conf"][i]) <= 0 or not data["text"][i].strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(data["text"][i])

    return "\n".join(
        " ".join(words)
        for _, words in sorted(lines.items())
    )


def evaluate_quality(text: str, conf_list: list[int]) -> tuple[float, float, float]:
    """(평균 conf, 한글 비율, 비정상 문자 비율) 산출."""
    valid = [c for c in conf_list if c > 0]
    avg_conf = float(np.mean(valid)) if valid else 0.0

    chars = text.replace(" ", "").replace("\n", "")
    total_len = max(len(chars), 1)
    korean_ratio = len(KOREAN_RE.findall(chars)) / total_len

    abnormal_matches = ABNORMAL_RE.findall(chars)
    abnormal_ratio = sum(len(m) for m in abnormal_matches) / total_len

    return round(avg_conf, 1), round(korean_ratio, 3), round(abnormal_ratio, 3)


def is_acceptable(avg_conf: float, korean_ratio: float, abnormal_ratio: float, lang: str) -> bool:
    """품질 기준 통과 여부."""
    if avg_conf < MIN_AVG_CONF:
        return False
    if abnormal_ratio > MAX_ABNORMAL_RATIO:
        return False
    if "kor" in lang and korean_ratio < MIN_KOREAN_RATIO and avg_conf < 70:
        return False
    return True


def ocr_with_retry(
    binary_img: np.ndarray,
    lang: str,
    preprocess_fn=None,
) -> OcrAttempt:
    """RETRY_PLAN에 따라 최대 3회 OCR 시도, 가장 높은 conf 결과 채택."""
    best: OcrAttempt | None = None

    for psm, preset in RETRY_PLAN[:MAX_RETRY]:
        try:
            if preprocess_fn and preset != PRESET_A:
                img = preprocess_fn(preset)
            else:
                img = binary_img

            pil_img = Image.fromarray(img) if not isinstance(img, Image.Image) else img
            data = pytesseract.image_to_data(
                pil_img, lang=lang, config=psm, output_type=pytesseract.Output.DICT,
            )

            text = _reconstruct_text(data)
            conf_list = [int(c) for c in data["conf"]]
            avg_conf, kr, abnormal = evaluate_quality(text, conf_list)

            attempt = OcrAttempt(
                text=text,
                avg_conf=avg_conf,
                psm_used=psm,
                preset_used=preset,
                korean_ratio=kr,
                abnormal_ratio=abnormal,
                passed=is_acceptable(avg_conf, kr, abnormal, lang),
            )

            if attempt.passed:
                return attempt
            if best is None or attempt.avg_conf > best.avg_conf:
                best = attempt

        except Exception:
            continue

    return best or OcrAttempt("", 0.0, RETRY_PLAN[0][0], RETRY_PLAN[0][1])
