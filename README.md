# claude-tmux

Drive [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview)'s interactive TUI through `tmux` from scripts and automation.

`claude-tmux` is for people who want to use Claude Code's normal interactive terminal UI, but still need a scriptable way to:

- send one-shot prompts,
- keep a named multi-turn session alive,
- read back the assistant's response without TUI chrome, and
- avoid the common failure mode where programmatic pseudo-terminal input is treated as paste text and Enter never submits.

It does **not** use `claude -p`, the Claude Code SDK, or GitHub Actions. It launches the regular `claude` command inside a real `tmux` session and drives that session with `tmux send-keys`.

## Requirements

- macOS or Linux
- Python 3.10+
- [`tmux`](https://github.com/tmux/tmux/wiki)
- Claude Code CLI installed and authenticated (`claude` must work in your shell)

Check prerequisites:

```bash
python3 --version
tmux -V
claude --version
```

## Install

### From GitHub

```bash
python3 -m pip install git+https://github.com/NoahHakansson/claude-tmux.git
```

### From a checkout

```bash
git clone https://github.com/NoahHakansson/claude-tmux.git
cd claude-tmux
python3 -m pip install .
```

### No install: run from source

```bash
git clone https://github.com/NoahHakansson/claude-tmux.git
cd claude-tmux
PYTHONPATH=src python3 bin/claude-tmux "Explain this repository"
```

## Usage

### One-shot prompt

```bash
claude-tmux "Explain what this repository does"
```

By default, a one-shot run creates an ephemeral tmux session and kills it when the response has been captured.

### Prompt from stdin

Use `-` as the prompt argument:

```bash
cat review-prompt.md | claude-tmux -
```

### Multi-turn named session

Named sessions keep Claude Code's conversation context alive between calls:

```bash
claude-tmux --session dev "Inspect this repo and summarize the architecture"
claude-tmux --session dev "Now propose a minimal refactor plan"
claude-tmux --session dev --kill
```

### Run in a specific directory

```bash
claude-tmux --workdir /path/to/project "Run the tests and explain any failures"
```

### Pass a Claude model alias

```bash
claude-tmux --model sonnet "Review this diff"
```

### Skip Claude Code permission prompts and accept workspace trust

```bash
claude-tmux --yes "Implement the failing test fix"
```

`--yes` passes `--dangerously-skip-permissions` through to Claude Code and, if Claude Code shows its workspace trust dialog, confirms `Yes, I trust this folder` automatically. Use it only in directories you trust and where you are comfortable letting Claude Code run tools without interactive approvals.

### Keep an ephemeral session for debugging

```bash
claude-tmux --keep "Do something slow"
tmux list-sessions
tmux capture-pane -t <session-name> -p -S -300
```

## How it works

The core trick is simple:

1. create a `tmux` session with a large pane,
2. start `claude` inside it,
3. send prompt text with `tmux send-keys -l`,
4. submit with a separate `tmux send-keys Enter`,
5. wait until Claude Code's status line changes from a present-participle verb such as `Cooking` to a past-tense verb such as `Cogitated`, and
6. capture the pane and extract only the latest assistant response.

The status-line detection intentionally matches by shape and verb suffix instead of a hard-coded list of Claude Code's whimsical status verbs.

## Options

```text
usage: claude-tmux [-h] [--session SESSION] [--workdir WORKDIR]
                   [--model MODEL] [--timeout TIMEOUT] [--kill] [--raw]
                   [--yes] [--keep]
                   [prompt]
```

| Option | Description |
| --- | --- |
| `prompt` | Prompt to send. Use `-` to read from stdin. |
| `--session NAME` | Reuse a named tmux session. Without this, the session is ephemeral. |
| `--workdir DIR` | Directory where Claude Code should run. Defaults to the current directory. |
| `--model NAME` | Model alias passed to Claude Code. |
| `--timeout SECS` | Maximum seconds to wait for a response. Defaults to 600. |
| `--kill` | Kill the named session and exit. |
| `--raw` | Print the raw tmux pane, including UI chrome. Useful for debugging extraction. |
| `--yes` | Pass `--dangerously-skip-permissions` to Claude Code. |
| `--keep` | Keep an otherwise-ephemeral session after the command exits. |

## Troubleshooting

### `Claude Code did not become ready...`

Make sure `claude` works manually in a terminal and that the account is authenticated:

```bash
claude
```

Also verify that `tmux` can create sessions:

```bash
tmux new-session -d -s claude-tmux-test 'echo ok; sleep 2'
tmux capture-pane -t claude-tmux-test -p
tmux kill-session -t claude-tmux-test
```

### The command timed out, but Claude may have finished

Do not immediately re-run a long prompt. Inspect the tmux session first:

```bash
tmux list-sessions
tmux capture-pane -t <session-name> -p -S -300
```

If the answer is visible, use `--raw` or capture the pane manually, then kill the session when done.

### The extracted response is empty or weird

Run the same command with `--raw` and open an issue with the captured pane after removing private prompt text. Claude Code's TUI output changes over time; extraction logic may need adjustment.

## Security notes

- `claude-tmux` does not store credentials or read Claude Code tokens.
- Prompts and responses are visible inside the tmux pane while a session exists.
- Named sessions keep conversation history in the running Claude Code process until killed.
- `--yes` disables Claude Code's interactive permission prompts. Treat it as a high-trust mode.
- Do not use this tool in directories containing secrets unless you are comfortable with Claude Code having access to those files.

## Development

```bash
git clone https://github.com/NoahHakansson/claude-tmux.git
cd claude-tmux
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e . pytest
python3 -m pytest
```

The test suite covers parser/status extraction logic and does not launch Claude Code.

## License

MIT. See [LICENSE](LICENSE).
