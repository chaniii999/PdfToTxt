"""Post-OCR 정규화 단위 테스트."""

import sys
import unittest
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.ocr.postprocess_normalize import (
    normalize_text,
    get_rules_doc,
    DiffEntry,
)


class TestNormalizeText(unittest.TestCase):
    """normalize_text 기본 테스트."""

    def test_empty_input(self) -> None:
        """빈 입력은 그대로 반환."""
        out, flags, log = normalize_text("")
        assert out == ""
        assert flags == []
        assert log == []

    def test_whitespace_only(self) -> None:
        """공백만 있으면 원문 그대로 반환."""
        inp = "   \n  "
        out, flags, log = normalize_text(inp)
        assert out == inp or not out.strip()
        assert log == []

    def test_llm_in_parens(self) -> None:
        """초거대 언어 모델(L\\nL\\ne\\nM\\nm\\n) -> 초거대 언어 모델(LLM)."""
        inp = "초거대 언어 모델(L\nL\ne\nM\nm\n)"
        expected = "초거대 언어 모델(LLM)"
        out, flags, log = normalize_text(inp)
        assert out == expected, f"got {out!r}"

    def test_self_reflective(self) -> None:
        """Sel f-Ref lective Reliability -> Self-Reflective Reliability."""
        inp = "Sel f-Ref lective Reliability"
        expected = "Self-Reflective Reliability"
        out, flags, log = normalize_text(inp)
        assert out == expected, f"got {out!r}"

    def test_kr_ssuro(self) -> None:
        """스\\n스로 -> 스스로."""
        inp = "스\n스로"
        expected = "스스로"
        out, flags, log = normalize_text(inp)
        assert out == expected, f"got {out!r}"

    def test_kr_gieok(self) -> None:
        """기\\n억 -> 기억."""
        inp = "기\n억"
        expected = "기억"
        out, flags, log = normalize_text(inp)
        assert out == expected, f"got {out!r}"

    def test_kr_chadan(self) -> None:
        """차\\n단 -> 차단."""
        inp = "차\n단"
        expected = "차단"
        out, flags, log = normalize_text(inp)
        assert out == expected, f"got {out!r}"

    def test_bullet_line_removal(self) -> None:
        """단독 · 라인 제거 후 문장 연결."""
        inp = "문장 앞부분.\n·\n문장 뒷부분."
        out, flags, log = normalize_text(inp)
        assert "·" not in out
        assert "문장 앞부분." in out
        assert "문장 뒷부분." in out
        assert "\n" in out, "문단 구분은 유지"

    def test_paren_inner_recovery(self) -> None:
        """괄호 내부 파손 복구 또는 플래그."""
        inp = "(Sel f-Ref lective Reliability)"
        out, flags, log = normalize_text(inp)
        assert "Self-Reflective" in out or "Self" in out

    def test_diff_log_structure(self) -> None:
        """diff 로그에 rule_id, before, after 포함."""
        inp = "스\n스로"
        out, flags, log = normalize_text(inp)
        assert len(log) >= 1
        for entry in log:
            assert isinstance(entry, DiffEntry)
            assert entry.rule_id
            assert entry.before is not None
            assert entry.after is not None


class TestRulesDoc(unittest.TestCase):
    """규칙 문서화 테스트."""

    def test_get_rules_doc_returns_list(self) -> None:
        """get_rules_doc은 규칙 목록 반환."""
        rules = get_rules_doc()
        assert isinstance(rules, list)
        assert len(rules) >= 5

    def test_rule_has_required_fields(self) -> None:
        """각 규칙에 rule_id, description, condition, example 존재."""
        rules = get_rules_doc()
        for r in rules:
            assert "rule_id" in r
            assert "description" in r
            assert "condition" in r
            assert "example" in r


if __name__ == "__main__":
    unittest.main()
