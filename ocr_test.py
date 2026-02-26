#!/usr/bin/env python3
"""OCR 인식률 테스트: 인풋1(원본) vs 인풋2(OCR 결과)의 한글·영어·숫자·한자 인식률 출력.

원본이 영어인데 OCR이 한글로 나온 경우 → 영어 틀림. 숫자/한자 각각 별도 카테고리.
"""

import argparse
import re
from pathlib import Path

_KR = re.compile(r"[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]")
_EN = re.compile(r"[a-zA-Z]")
_DIGIT = re.compile(r"[0-9]")
# CJK 통합 한자 (U+4E00~9FFF), 확장 A (U+3400~4DBF)
_CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def _char_type(c: str) -> str:
    """글자 유형: korean, english, digit, chinese, other."""
    if not c:
        return "other"
    if _KR.fullmatch(c):
        return "korean"
    if _EN.fullmatch(c):
        return "english"
    if _DIGIT.fullmatch(c):
        return "digit"
    if _CJK.fullmatch(c):
        return "chinese"
    return "other"


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


def _accuracy_by_type(ops: list[tuple[str, str, str]]) -> dict[str, dict]:
    """
    편집 스크립트를 한글/영어/숫자/한자 구분하여 정확도 계산.
    삽입(i): OCR에만 있는 글자. 다음 원본 글자 유형에 귀속.
    """
    counts: dict[str, tuple[int, int, int]] = {
        "korean": (0, 0, 0),
        "english": (0, 0, 0),
        "digit": (0, 0, 0),
        "chinese": (0, 0, 0),
    }

    def _next_gt(idx: int) -> str:
        for j in range(idx + 1, len(ops)):
            nop, ng, _ = ops[j]
            if nop in ("m", "s", "d") and ng:
                return ng
        for j in range(idx - 1, -1, -1):
            nop, ng, _ = ops[j]
            if nop in ("m", "s", "d") and ng:
                return ng
        return ""

    for idx, (op, gt_c, ocr_c) in enumerate(ops):
        if op == "m":
            t = _char_type(gt_c)
            if t != "other":
                gt, ok, wr = counts[t]
                counts[t] = (gt + 1, ok + 1, wr)
        elif op in ("s", "d"):
            t = _char_type(gt_c)
            if t != "other":
                gt, ok, wr = counts[t]
                counts[t] = (gt + 1, ok, wr + 1)
        elif op == "i":
            next_gt = _next_gt(idx)
            next_t = _char_type(next_gt)
            ocr_t = _char_type(ocr_c)
            if ocr_t != "other":
                attr = next_t if next_t != "other" else ocr_t
                gt, ok, wr = counts[attr]
                counts[attr] = (gt + 1, ok, wr + 1)

    def _acc(gt_count: int, ok: int, wrong_count: int) -> dict:
        if gt_count == 0:
            return {"accuracy": None, "correct": 0, "wrong": 0, "gt_count": 0}
        return {
            "accuracy": round(ok / gt_count * 100, 1),
            "correct": ok,
            "wrong": wrong_count,
            "gt_count": gt_count,
        }

    return {k: _acc(*v) for k, v in counts.items()}


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
    인풋1(원본) vs 인풋2(OCR 결과)의 한글·영어·숫자·한자 인식률 계산.

    Returns:
        {"korean": {...}, "english": {...}, "digit": {...}, "chinese": {...}}
    """
    gt = _load_text(input1)
    ocr = _load_text(input2)

    ops = _get_edit_ops(gt, ocr)
    return _accuracy_by_type(ops)


_LABELS = {"korean": "한글", "english": "영어", "digit": "숫자", "chinese": "한자"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OCR 인식률 테스트: 인풋1(원본) vs 인풋2(OCR 결과)의 한글·영어·숫자·한자 인식률 출력"
    )
    parser.add_argument("input1", help="원본 텍스트 (파일 경로 또는 문자열)")
    parser.add_argument("input2", help="OCR 인식 결과 (파일 경로 또는 문자열)")
    args = parser.parse_args()

    rates = compute_recognition_rates(args.input1, args.input2)

    print("=== OCR 인식률 (맞은 글자/원본 글자 기준) ===\n")
    for key, label in _LABELS.items():
        r = rates[key]
        if r["gt_count"] > 0:
            print(f"{label}: {r['accuracy']}% (맞음 {r['correct']}자 / 틀림 {r['wrong']}자 / 원본 {r['gt_count']}자)")
        else:
            print(f"{label}: 원본에 {label} 없음 (N/A)")


if __name__ == "__main__":
    main()
