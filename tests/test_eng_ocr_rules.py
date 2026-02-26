"""2차 eng OCR 인식 규칙 단위 테스트."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.ocr.eng_ocr_rules import (
    postprocess_eng_result,
    is_valid_eng_result,
    classify_eng_candidate,
)


class TestPostprocessEngResult(unittest.TestCase):
    """postprocess_eng_result 테스트."""

    def test_acronym_fix(self) -> None:
        """도메인 약어 맵 적용."""
        assert postprocess_eng_result("P0II") == "PII"
        assert postprocess_eng_result("Al") == "AI"
        assert postprocess_eng_result("P|I") == "PII"
        assert postprocess_eng_result("0!!") == "PII"
        assert postprocess_eng_result("LLeMm") == "LLM"
        assert postprocess_eng_result("Lem") == "LLM"

    def test_pipe_to_i(self) -> None:
        """| → I (영문 내부)."""
        assert postprocess_eng_result("P|I") == "PII"

    def test_empty(self) -> None:
        """빈 입력은 그대로 반환."""
        assert postprocess_eng_result("") == ""
        assert postprocess_eng_result("   ").strip() == ""


class TestIsValidEngResult(unittest.TestCase):
    """is_valid_eng_result 테스트."""

    def test_valid(self) -> None:
        """유효한 영문."""
        assert is_valid_eng_result("PII")
        assert is_valid_eng_result("AI")
        assert is_valid_eng_result("Self-Reflective")

    def test_reject_korean(self) -> None:
        """한글 포함 거부."""
        assert not is_valid_eng_result("가나다")
        assert not is_valid_eng_result("PII한글")

    def test_reject_digits_only(self) -> None:
        """숫자만 거부."""
        assert not is_valid_eng_result("123")

    def test_reject_short_mixed(self) -> None:
        """3자 이하 + 숫자/특수문자 과다 거부."""
        assert not is_valid_eng_result("1!")


class TestClassifyEngCandidate(unittest.TestCase):
    """classify_eng_candidate 테스트."""

    def test_accept_corrected(self) -> None:
        """보정 후 채택."""
        assert classify_eng_candidate("xxx", "P0II") == "PII"
        assert classify_eng_candidate("xxx", "Al") == "AI"

    def test_reject_korean(self) -> None:
        """한글 거부."""
        assert classify_eng_candidate("xxx", "한글") is None

    def test_reject_empty(self) -> None:
        """빈 입력 거부."""
        assert classify_eng_candidate("xxx", "") is None


if __name__ == "__main__":
    unittest.main()
