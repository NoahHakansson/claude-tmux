import pytest

import claude_tmux.cli as cli
from claude_tmux.cli import (
    extract_assistant_message,
    get_status_line,
    is_busy,
    is_ready,
    is_workspace_trust_prompt,
)


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


def test_get_status_line_handles_claude_2_tall_pane_layout():
    pane = """
Claude Code v2.1.178
❯ Do not use tools. Reply exactly: DEBUG_TRUSTED_OK

⏺ DEBUG_TRUSTED_OK

✻ Crunched for 2s




──────────────────────────────
❯\u00a0
──────────────────────────────
  Model: Opus 4.8 · Ctx: 21.4k
  -- INSERT -- auto mode on
"""
    assert get_status_line(pane) == "✻ Crunched for 2s"
    assert is_busy(pane) is False


def test_prompt_with_user_text_is_not_treated_as_ready_prompt():
    pane = """
Welcome to Claude Code

✻ Cogitated for 7s
──────────────────────────────
❯ one_word_prompt_waiting_to_submit
"""
    assert get_status_line(pane) is None


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


def test_get_status_line_ignores_old_done_status_when_latest_turn_busy():
    pane = """
Welcome to Claude Code

❯ first prompt

⏺ first answer

✻ Baked for 2s

❯ second prompt

· Unravelling…
──────────────────────────────
❯\u00a0
"""
    assert get_status_line(pane) == "· Unravelling…"
    assert is_busy(pane) is True


def test_is_ready_requires_prompt_and_claude_marker():
    pane = """
Welcome to Claude Code

❯
"""
    assert is_ready(pane) is True
    assert is_ready("❯") is False


def test_detects_workspace_trust_prompt():
    pane = """
Accessing workspace:

/Users/noah/projects/claude-tmux

Quick safety check: Is this a project you created or one you trust? (Like your own code, a well-known open source project, or work from your team).

❯ 1. Yes, I trust this folder
  2. No, exit
"""
    assert is_workspace_trust_prompt(pane) is True
    assert is_workspace_trust_prompt("Welcome to Claude Code\n❯") is False


def test_wait_for_claude_ready_accepts_workspace_trust_with_yes(monkeypatch):
    trust_pane = """
Accessing workspace:
Quick safety check: Is this a project you created or one you trust?
❯ 1. Yes, I trust this folder
  2. No, exit
"""
    ready_pane = """
Claude Code v2.1.178
❯\u00a0
"""
    panes = [trust_pane, ready_pane]
    calls = []

    def fake_tmux(*args):
        calls.append(args)
        if args[0] == "capture-pane":
            return panes.pop(0)
        return ""

    monkeypatch.setattr(cli, "tmux", fake_tmux)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    cli.wait_for_claude_ready("test-session", timeout=5, yes=True)

    assert ("send-keys", "-t", "test-session", "Enter") in calls


def test_wait_for_claude_ready_rejects_workspace_trust_without_yes(monkeypatch):
    trust_pane = """
Accessing workspace:
Quick safety check: Is this a project you created or one you trust?
❯ 1. Yes, I trust this folder
  2. No, exit
"""

    monkeypatch.setattr(cli, "tmux", lambda *args: trust_pane)

    with pytest.raises(cli.ClaudeTmuxError, match="Rerun with `--yes`"):
        cli.wait_for_claude_ready("test-session", timeout=5, yes=False)


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


def test_extract_assistant_message_strips_claude_2_bottom_statusline():
    pane = """
Claude Code v2.1.178
❯ Do not use tools. Reply exactly: CLAUDE_TMUX_SMOKE_OK

⏺ CLAUDE_TMUX_SMOKE_OK

✻ Crunched for 2s



                                                                                                                                                                                      ◉ xhigh · /effort
──────────────────────────────
❯\u00a0
──────────────────────────────
  Model: Opus 4.8 · Ctx: 21.4k
  -- INSERT -- auto mode on
"""
    assert extract_assistant_message(pane) == "CLAUDE_TMUX_SMOKE_OK"


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
