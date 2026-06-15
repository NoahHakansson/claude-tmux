from claude_tmux.cli import extract_assistant_message, get_status_line, is_busy, is_ready


def test_get_status_line_busy():
    pane = """
Welcome to Claude Code

✻ Cooking for 3s
──────────────────────────────
❯
"""
    assert get_status_line(pane) == "✻ Cooking for 3s"
    assert is_busy(pane) is True


def test_get_status_line_done():
    pane = """
Welcome to Claude Code

✻ Cogitated for 7s
──────────────────────────────
❯
"""
    assert get_status_line(pane) == "✻ Cogitated for 7s"
    assert is_busy(pane) is False


def test_get_status_line_uses_latest_prompt_in_scrollback():
    pane = """
Welcome to Claude Code

✻ Cogitated for 7s
──────────────────────────────
❯ old prompt

⏺ old answer

✻ Cooking for 3s
──────────────────────────────
❯
"""
    assert get_status_line(pane) == "✻ Cooking for 3s"
    assert is_busy(pane) is True


def test_is_ready_requires_prompt_and_claude_marker():
    pane = """
Welcome to Claude Code

❯
"""
    assert is_ready(pane) is True
    assert is_ready("❯") is False


def test_extract_assistant_message_strips_ui_chrome():
    pane = """
Welcome to Claude Code

❯ Explain this repo

⏺ This repository wraps Claude Code.
  It keeps the interactive TUI path.

✻ Cogitated for 7s
──────────────────────────────
❯
"""
    assert extract_assistant_message(pane) == (
        "This repository wraps Claude Code.\n"
        "  It keeps the interactive TUI path."
    )


def test_extract_assistant_message_handles_multiline_prompt():
    pane = """
Welcome to Claude Code

❯ Review this patch:
  diff --git a/a.py b/a.py
  +print('hello')

⏺ The patch only prints hello.

✢ Sautéed for 2s
──────────────────────────────
❯
"""
    assert extract_assistant_message(pane) == "The patch only prints hello."


def test_extract_returns_empty_when_no_assistant_turn_seen():
    pane = """
Welcome to Claude Code

❯ prompt text

✻ Cooking for 1s
──────────────────────────────
❯
"""
    assert extract_assistant_message(pane) == ""
