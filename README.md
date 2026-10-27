# Publish Scrub

A local, read-only check to run **before you copy a private tree into a public repository**. It scans the working tree and the full git history for likely secrets and private details, then prints each finding with its value masked.

It looks for:

| Kind | What matches |
| --- | --- |
| `token` | Common token prefixes: GitHub (`ghp_`, `github_pat_`), AWS access keys (`AKIA`), Slack (`xox…-`) and `sk-` keys |
| `bot-token` | Telegram bot token shapes (`<digits>:<long id>`) |
| `assignment` | `password`, `secret`, `api_key` or `token` assigned a quoted value of 8 or more characters |
| `chat-id` | `chat_id` or `user_id` assigned a number of 8 or more digits |
| `host-path` | Absolute home-directory paths (the Linux and macOS home roots) |
| `private-url` | GitHub URLs to repositories whose names end in `-private` |

Values that contain a placeholder word (`example`, `changeme`, `placeholder`, `redacted`, `your_`, `todo`, `****`) are ignored.

It does not edit files, upload anything or print a full secret. **It isn't a substitute for reading the export yourself**: a clean result can still miss a secret that doesn't match a pattern. A public export isn't done until this check exits 0.

This is not a hosted app. Don't send a private tree to a web service.

## Requirements

- Python 3.11 or newer. There are no third-party dependencies.
- `git` on your `PATH`, so it can scan history.

## Install

```sh
git clone https://github.com/rickkeller/publish-scrub
cd publish-scrub
python3 -m venv .venv && .venv/bin/pip install .
```

You can also skip installing and run `python3 -m publish_scrub` from the checkout.

## Quickstart

```sh
.venv/bin/publish-scrub /path/to/export-tree      # or: python3 -m publish_scrub /path/to/export-tree
echo "exit code: $?"
```

Each finding prints as one line in the form `kind location:line masked-value`, for example:

```
token config/settings.py:12 ghp_**** len=24
private-url history:33 gith**** len=28
```

`history` as the location means the match is in an old commit, from `git log -p --all`. Deleting the file from the tree won't remove it. You need to rewrite the history, or export a fresh tree without it.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | No findings. |
| `1` | At least one finding. Don't publish this tree. |
| `2` | The path isn't a directory, or the arguments are wrong. |

## Configuration

There are no options, config files or environment variables. These are fixed in the code:

- Skipped directories: `.git`, `.hg`, `.svn`, `node_modules`, `.venv`, `venv` and `__pycache__`.
- Binary files and files that aren't UTF-8 are skipped.
- Symlinks are not followed.
- Files over 1 MB are reported as `unread`, and history over 20 MB is reported as `truncated`. Both count as findings.

## Troubleshooting

- **`history .:1 git history was not scanned`.** The directory isn't a git repository, or `git log` failed. The result is exit 1 on purpose, because the history wasn't checked. Run the scan on the git checkout you plan to publish.
- **`git history scan was truncated`.** History is over 20 MB. Scan a fresh export with a short history instead.
- **`unread <file>:1 file exceeds the text limit`.** Check that file by hand, or leave it out of the export.
- **False positives.** Use an obvious placeholder in examples (for example `your_token_here`), or split literal patterns in test fixtures the way `tests/test_scan.py` does.
- **Don't paste findings into a chat or ticket.** The values are masked, but each line still points to where a secret is.

## Development

```sh
python3 -m unittest discover -s tests
```

See [AGENTS.md](AGENTS.md).

## License

MIT. See [LICENSE](LICENSE).
