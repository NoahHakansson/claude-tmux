#!/usr/bin/env python3
"""Drive Claude Code's interactive TUI through tmux."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass

# Claude Code's status line has looked like:
#   "✻ Cogitated for 7s"   (done — past-tense verb, frozen timer)
#   "✻ Cooking for 3s"     (busy — present-participle verb, counting timer)
#   "✢ Unfurling…"         (busy — just started, no timer yet)
# Match it by shape instead of by a hard-coded verb list; the verbs change.
_STATUS_LINE_RE = re.compile(r"^[✻✶✳✢⏺·◐◓◑◒▘▝▗▖]\s+(\w+)(?:\s+for\s+\S+)?\s*$")
_PROMPT_RE = re.compile(r"^\s*❯\s*\S*\s*$")


class ClaudeTmuxError(RuntimeError):
    """Raised for expected runtime failures with a clean user-facing message."""


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


def run(cmd: list[str], check: bool = True) -> CommandResult:
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise ClaudeTmuxError(f"Required executable not found: {cmd[0]}") from exc
    if check and completed.returncode != 0:
        command = " ".join(shlex.quote(part) for part in cmd)
        raise ClaudeTmuxError(
            f"Command failed ({completed.returncode}): {command}\n{completed.stderr.strip()}"
        )
    return CommandResult(completed.stdout, completed.stderr, completed.returncode)


def tmux(*args: str) -> str:
    return run(["tmux", *args]).stdout


def session_exists(name: str) -> bool:
    return run(["tmux", "has-session", "-t", name], check=False).returncode == 0


def kill_session(name: str) -> None:
    if session_exists(name):
        tmux("kill-session", "-t", name)


def create_session(name: str, workdir: str, model: str | None, yes: bool) -> None:
    """Start a tmux session running Claude Code in the given working directory."""
    if session_exists(name):
        raise ClaudeTmuxError(
            f"tmux session {name!r} already exists; use --kill or choose a different --session"
        )

    cmd_parts = ["claude"]
    if yes:
        cmd_parts.append("--dangerously-skip-permissions")
    if model:
        cmd_parts += ["--model", model]
    claude_cmd = " ".join(shlex.quote(part) for part in cmd_parts)

    tmux("new-session", "-d", "-s", name, "-x", "200", "-y", "50")
    tmux("send-keys", "-t", name, f"cd {shlex.quote(workdir)} && {claude_cmd}", "Enter")


def get_status_line(pane: str) -> str | None:
    """Return Claude Code's turn-status line if one is visible above the prompt."""
    lines = pane.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        line = lines[index]
        if not _PROMPT_RE.match(line):
            continue
        for candidate_index in (index - 2, index - 3, index - 4, index - 5):
            if candidate_index < 0:
                continue
            candidate = lines[candidate_index].strip()
            if _STATUS_LINE_RE.match(candidate):
                return candidate
        return None
    return None


def is_busy(pane: str) -> bool:
    """Return True when the visible Claude Code status line says work is ongoing."""
    status = get_status_line(pane)
    if not status:
        return False
    match = _STATUS_LINE_RE.match(status)
    return bool(match and match.group(1).endswith("ing"))


def is_ready(pane: str) -> bool:
    """Return True when Claude Code appears ready for input."""
    has_prompt = any(_PROMPT_RE.match(line) for line in pane.splitlines())
    looks_like_claude = "Claude" in pane or "claude" in pane
    return has_prompt and looks_like_claude and not is_busy(pane)


def wait_for_claude_ready(name: str, timeout: int = 30) -> None:
    """Block until the Claude Code TUI appears ready to accept input."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_ready(tmux("capture-pane", "-t", name, "-p")):
            return
        time.sleep(0.3)
    raise ClaudeTmuxError(f"Claude Code did not become ready in {name!r} within {timeout}s")


def send_prompt(name: str, prompt: str) -> None:
    """Send a prompt to Claude Code through tmux literal input, then submit it."""
    tmux("send-keys", "-t", name, "-l", prompt)
    time.sleep(0.1)
    tmux("send-keys", "-t", name, "Enter")


def wait_for_idle(name: str, timeout: int) -> str:
    """
    Wait until Claude Code finishes responding, then return the captured pane.

    Absence of a status line is not enough: immediately after prompt submission,
    the input box can contain text before Claude has started processing. The
    wrapper waits for a past-tense status line, then requires it to be stable.
    """
    deadline = time.time() + timeout
    last_status = None

    while time.time() < deadline:
        pane = tmux("capture-pane", "-t", name, "-p")
        status = get_status_line(pane)

        if status is None:
            last_status = None
        else:
            match = _STATUS_LINE_RE.match(status)
            verb = match.group(1) if match else ""
            if verb.endswith("ing"):
                last_status = status
            elif status == last_status:
                return pane
            else:
                last_status = status

        time.sleep(0.4)

    raise ClaudeTmuxError(f"Claude Code did not finish within {timeout}s")


def extract_assistant_message(pane: str) -> str:
    """Extract the assistant's latest response from a raw Claude Code pane."""
    lines = pane.splitlines()

    end_index = None
    for index in range(len(lines) - 1, -1, -1):
        if _PROMPT_RE.match(lines[index]):
            end_index = index
            break
    if end_index is None:
        return pane

    last_prompt_index = -1
    for index in range(end_index - 1, -1, -1):
        if lines[index].lstrip().startswith("❯ "):
            last_prompt_index = index
            break

    start_index = None
    for index in range(last_prompt_index + 1, end_index):
        if lines[index].lstrip().startswith("⏺"):
            start_index = index
            break
    if start_index is None:
        return ""

    body = lines[start_index:end_index]
    body[0] = re.sub(r"^\s*⏺\s?", "", body[0])
    body = [line for line in body if not re.match(r"^\s*[─━═-]+\s*$", line)]
    body = [line for line in body if not _STATUS_LINE_RE.match(line.strip())]

    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()

    return "\n".join(body).strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Drive Claude Code in interactive TUI mode via tmux.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  claude-tmux "Explain this repository"
  claude-tmux --session dev "Refactor auth.go to use JWT"
  claude-tmux --session dev "Now add tests"
  claude-tmux --session dev --kill
  cat prompt.md | claude-tmux - --yes
""".strip(),
    )
    parser.add_argument("prompt", nargs="?", help="Prompt to send. Use '-' to read from stdin.")
    parser.add_argument("--session", default=None, help="tmux session name (default: ephemeral)")
    parser.add_argument("--workdir", default=os.getcwd(), help="Working directory for Claude Code")
    parser.add_argument("--model", default=None, help="Claude model alias to pass through")
    parser.add_argument("--timeout", type=int, default=600, help="Max wait for response in seconds")
    parser.add_argument("--kill", action="store_true", help="Tear down the session and exit")
    parser.add_argument("--raw", action="store_true", help="Print the raw captured pane instead of extracted text")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Pass --dangerously-skip-permissions to Claude Code; use only in trusted directories",
    )
    parser.add_argument("--keep", action="store_true", help="Keep an ephemeral session after exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.prompt == "-":
        args.prompt = sys.stdin.read().rstrip("\n")
    elif args.prompt is None and not args.kill:
        parser.error("prompt required, or pass '-' to read from stdin")
    if args.kill and args.session is None:
        parser.error("--kill requires --session NAME")
    if not os.path.isdir(args.workdir):
        parser.error(f"--workdir does not exist or is not a directory: {args.workdir}")

    session = args.session or f"claude-{os.getpid()}-{int(time.time())}"
    ephemeral = args.session is None

    try:
        if args.kill:
            kill_session(session)
            print(f"killed session {session!r}")
            return 0

        if not session_exists(session):
            create_session(session, args.workdir, args.model, args.yes)
            wait_for_claude_ready(session)

        send_prompt(session, args.prompt)
        pane = wait_for_idle(session, args.timeout)
        print(pane if args.raw else extract_assistant_message(pane))
        return 0
    except ClaudeTmuxError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if ephemeral and not args.keep and not args.kill:
            try:
                kill_session(session)
            except ClaudeTmuxError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
