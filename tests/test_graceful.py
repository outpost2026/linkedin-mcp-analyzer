"""Tests for graceful degradation — no-op responses + safe wrapping."""

from __future__ import annotations

from linkedin_mcp_custom.util.graceful import NOOP_RESPONSES, noop_for, safe_tool_response


class TestNoopFor:
    def test_known_methods_return_noop(self) -> None:
        for method in NOOP_RESPONSES:
            resp = noop_for(method)
            assert resp is not None
            assert isinstance(resp, dict)

    def test_prompts_list_returns_empty_list(self) -> None:
        assert noop_for("prompts/list") == {"prompts": []}

    def test_resources_list_returns_empty_list(self) -> None:
        assert noop_for("resources/list") == {"resources": []}

    def test_unknown_method_returns_none(self) -> None:
        assert noop_for("something/weird") is None


class TestSafeToolResponse:
    def test_dict_gets_defaults(self) -> None:
        result = safe_tool_response("test_tool", {"job_id": "123"})
        assert result["tool"] == "test_tool"
        assert result["status"] == "ok"
        assert result["job_id"] == "123"

    def test_non_dict_wrapped(self) -> None:
        result = safe_tool_response("calc", 42)
        assert result["status"] == "ok"
        assert result["tool"] == "calc"
        assert result["data"] == 42

    def test_existing_status_not_overwritten_falsy(self) -> None:
        result = safe_tool_response("t", {"status": "error", "message": "fail"})
        assert result["status"] == "error"
