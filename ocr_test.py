#!/usr/bin/env python3
"""OCR 인식률 테스트: 인풋1(원본) vs 인풋2(OCR 결과)의 한글·영어 인식률 출력."""

import argparse
import re
from pathlib import Path


def _levenshtein(s1: str, s2: str) -> int:
    """편집 거리(Levenshtein distance) 계산."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(
                prev[j + 1] + 1,
                curr[j] + 1,
                prev[j] + (0 if c1 == c2 else 1),
            ))
        prev = curr
    return prev[-1]


def _extract_korean(text: str) -> str:
    """한글 문자만 추출 (음절, 자모 포함)."""
    return "".join(re.findall(r"[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]", text))


def _extract_english(text: str) -> str:
    """영어 문자만 추출 (a-zA-Z)."""
    return "".join(re.findall(r"[a-zA-Z]", text))


def _accuracy_percent(ground_truth: str, ocr_result: str) -> float:
    """원본 대비 OCR 결과의 문자 인식률(%)."""
    if len(ground_truth) == 0:
        return 100.0
    edits = _levenshtein(ground_truth, ocr_result)
    correct = max(0, len(ground_truth) - edits)
    return round(correct / len(ground_truth) * 100, 1)


def _load_text(path_or_str: str) -> str:
    """파일 경로면 읽고, 아니면 문자열 그대로 반환."""
    p = Path(path_or_str)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return path_or_str


def compute_recognition_rates(input1: str, input2: str) -> dict:
    """
    인풋1(원본) vs 인풋2(OCR 결과)의 한글·영어 인식률 계산.

    Returns:
        {"korean": {"accuracy": float, "gt_count": int, "ocr_count": int},
         "english": {"accuracy": float, "gt_count": int, "ocr_count": int}}
    """
    gt = _load_text(input1)
    ocr = _load_text(input2)

    gt_kr = _extract_korean(gt)
    ocr_kr = _extract_korean(ocr)
    gt_en = _extract_english(gt)
    ocr_en = _extract_english(ocr)

    kr_acc = _accuracy_percent(gt_kr, ocr_kr) if gt_kr else None
    en_acc = _accuracy_percent(gt_en, ocr_en) if gt_en else None

    return {
        "korean": {
            "accuracy": kr_acc,
            "gt_count": len(gt_kr),
            "ocr_count": len(ocr_kr),
        },
        "english": {
            "accuracy": en_acc,
            "gt_count": len(gt_en),
            "ocr_count": len(ocr_en),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OCR 인식률 테스트: 인풋1(원본) vs 인풋2(OCR 결과)의 한글·영어 인식률 출력"
    )
    parser.add_argument("input1", help="원본 텍스트 (파일 경로 또는 문자열)")
    parser.add_argument("input2", help="OCR 인식 결과 (파일 경로 또는 문자열)")
    args = parser.parse_args()

    rates = compute_recognition_rates(args.input1, args.input2)

    kr = rates["korean"]
    en = rates["english"]

    print("=== OCR 인식률 ===\n")
    if kr["gt_count"] > 0:
        print(f"한글: {kr['accuracy']}% (원본 {kr['gt_count']}자 → OCR {kr['ocr_count']}자)")
    else:
        print("한글: 원본에 한글 없음 (N/A)")

    if en["gt_count"] > 0:
        print(f"영어: {en['accuracy']}% (원본 {en['gt_count']}자 → OCR {en['ocr_count']}자)")
    else:
        print("영어: 원본에 영어 없음 (N/A)")


if __name__ == "__main__":
    main()
