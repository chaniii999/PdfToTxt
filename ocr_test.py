#!/usr/bin/env python3
"""OCR 인식률 테스트: 인풋1(원본) vs 인풋2(OCR 결과)의 한글·영어 인식률 출력.

원본이 영어/숫자인데 OCR이 한글로 나온 경우 → 영어 정확도에서만 감점.
"""

import argparse
import re
from pathlib import Path

_KR = re.compile(r"[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]")
_EN = re.compile(r"[a-zA-Z0-9]")


def _is_korean(c: str) -> bool:
    return bool(c and _KR.fullmatch(c))


def _is_english_or_digit(c: str) -> bool:
    return bool(c and _EN.fullmatch(c))


def _get_edit_ops(gt: str, ocr: str) -> list[tuple[str, str, str]]:
    """편집 스크립트 반환. (op, gt_char, ocr_char). op: m=매치, s=치환, i=삽입, d=삭제."""
    n, m = len(gt), len(ocr)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if gt[i - 1] == ocr[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)

    ops: list[tuple[str, str, str]] = []
    i, j = n, m
    while i > 0 or j > 0:
        a = gt[i - 1] if i > 0 else ""
        b = ocr[j - 1] if j > 0 else ""
        if i > 0 and j > 0 and gt[i - 1] == ocr[j - 1] and dp[i][j] == dp[i - 1][j - 1]:
            ops.append(("m", a, b))
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            ops.append(("s", a, b))
            i -= 1
            j -= 1
        elif j > 0 and dp[i][j] == dp[i][j - 1] + 1:
            ops.append(("i", "", b))
            j -= 1
        else:
            ops.append(("d", a, ""))
            i -= 1
    ops.reverse()
    return ops


def _accuracy_by_type(ops: list[tuple[str, str, str]]) -> tuple[dict, dict]:
    """
    편집 스크립트를 한글/영어 구분하여 정확도 계산.
    원본이 영어/숫자인데 OCR이 한글로 나온 경우 → 영어 틀림(한글 틀림 아님).
    삽입(i): OCR에만 있는 글자. 다음 원본 글자 유형에 귀속(영어→한글 오인식 시 영어 틀림).
    """
    kr_gt, kr_ok, kr_wrong = 0, 0, 0
    en_gt, en_ok, en_wrong = 0, 0, 0

    for idx, (op, gt_c, ocr_c) in enumerate(ops):
        if op == "m":
            if _is_korean(gt_c):
                kr_gt += 1
                kr_ok += 1
            elif _is_english_or_digit(gt_c):
                en_gt += 1
                en_ok += 1
        elif op == "s":
            if _is_korean(gt_c):
                kr_gt += 1
                kr_wrong += 1
            elif _is_english_or_digit(gt_c):
                en_gt += 1
                en_wrong += 1
        elif op == "d":
            if _is_korean(gt_c):
                kr_gt += 1
                kr_wrong += 1
            elif _is_english_or_digit(gt_c):
                en_gt += 1
                en_wrong += 1
        elif op == "i":
            next_gt = ""
            for j in range(idx + 1, len(ops)):
                nop, ng, _ = ops[j]
                if nop in ("m", "s", "d") and ng:
                    next_gt = ng
                    break
            if not next_gt:
                for j in range(idx - 1, -1, -1):
                    nop, ng, _ = ops[j]
                    if nop in ("m", "s", "d") and ng:
                        next_gt = ng
                        break
            if _is_korean(ocr_c):
                if _is_english_or_digit(next_gt):
                    en_gt += 1
                    en_wrong += 1
                else:
                    kr_gt += 1
                    kr_wrong += 1
            elif _is_english_or_digit(ocr_c):
                if _is_korean(next_gt):
                    kr_gt += 1
                    kr_wrong += 1
                else:
                    en_gt += 1
                    en_wrong += 1

    def _acc(gt_count: int, ok: int, wrong_count: int) -> tuple[float | None, int, int]:
        if gt_count == 0:
            return None, 0, 0
        acc = round(ok / gt_count * 100, 1)
        return acc, ok, wrong_count

    kr_acc, kr_correct, kr_wrong = _acc(kr_gt, kr_ok, kr_wrong)
    en_acc, en_correct, en_wrong = _acc(en_gt, en_ok, en_wrong)

    return (
        {"accuracy": kr_acc, "correct": kr_correct, "wrong": kr_wrong, "gt_count": kr_gt},
        {"accuracy": en_acc, "correct": en_correct, "wrong": en_wrong, "gt_count": en_gt},
    )


def _load_text(path_or_str: str) -> str:
    """파일 경로면 읽고, 아니면 문자열 그대로 반환."""
    if "\n" in path_or_str or len(path_or_str) > 512:
        return path_or_str
    p = Path(path_or_str)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return path_or_str


def compute_recognition_rates(input1: str, input2: str) -> dict:
    """
    인풋1(원본) vs 인풋2(OCR 결과)의 한글·영어 인식률 계산.
    위치 기반 정렬: 원본이 영어인데 OCR이 한글로 나온 경우 → 영어 틀림.

    Returns:
        {"korean": {"accuracy": float, "correct": int, "wrong": int, "gt_count": int},
         "english": {...}}
    """
    gt = _load_text(input1)
    ocr = _load_text(input2)

    ops = _get_edit_ops(gt, ocr)
    kr_res, en_res = _accuracy_by_type(ops)

    return {"korean": kr_res, "english": en_res}


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

    print("=== OCR 인식률 (맞은 글자/원본 글자 기준, 추출 갯수 비율 아님) ===\n")
    if kr["gt_count"] > 0:
        print(f"한글: {kr['accuracy']}% (맞음 {kr['correct']}자 / 틀림 {kr['wrong']}자 / 원본 {kr['gt_count']}자)")
    else:
        print("한글: 원본에 한글 없음 (N/A)")

    if en["gt_count"] > 0:
        print(f"영어: {en['accuracy']}% (맞음 {en['correct']}자 / 틀림 {en['wrong']}자 / 원본 {en['gt_count']}자)")
    else:
        print("영어: 원본에 영어 없음 (N/A)")


if __name__ == "__main__":
    main()
