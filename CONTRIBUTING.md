# Contributing

Thanks for considering a contribution.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e . pytest
python3 -m pytest
```

## Ground rules

- Keep the tool dependency-free unless there is a strong reason not to.
- Do not add code paths that call `claude -p` or Claude SDKs; this project is specifically for driving the interactive TUI.
- Prefer tests that exercise pane parsing without launching Claude Code.
- If changing extraction logic, include a small sanitized pane fixture in the tests.
- Be careful with `--yes`; document risks plainly.
