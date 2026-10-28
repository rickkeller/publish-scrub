# Publish Scrub

A local, read-only check to run **before you copy a private tree into a public repository**. It scans the working tree and the full git history for likely secrets and private details, then prints each finding with its value masked.

It looks for:

| Kind | What matches |
| --- | --- |
| `github-token` | `ghp_` and `github_pat_` |
| `aws-key` | `AKIA` access key ids |
| `slack-token` | `xox` Slack tokens |
| `openai-key` | `sk-` keys that contain a digit. A class name is not a key |
| `slack-webhook` | Slack incoming webhook URLs |
| `private-key` | PEM private-key headers, including OpenSSH |
| `db-url` | Database URLs that include a password |
| `bot-token` | Telegram bot token shapes (`<digits>:<long id>`) |
| `assignment` | A name containing `password`, `secret`, `api_key` or `token`, quoted or not. A prefix such as `AWS_SECRET_ACCESS_KEY` counts |
| `chat-id` | `chat_id` or `user_id` assigned a number of 8 or more digits |
| `host-path` | Absolute home-directory paths (the Linux and macOS home roots) |
| `private-url` | GitHub URLs to repositories whose names end in `-private` |

A placeholder is ignored only when the whole value is one (`example`, `changeme`, `placeholder`, `redacted`, `todo`, `your_…`). A real value that merely contains those letters is not ignored. `${{ secrets.… }}` is not a finding.

Exit 0 means no findings. Exit 1 means findings. Exit 2 means the check could not finish, including missing git or a history scan that hit the size cap. An unread file is printed and does not by itself fail the run. `--no-history` skips git history.

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
.venv/bin/publish-scrub --self-test
.venv/bin/publish-scrub /path/to/export-tree      # or: python3 -m publish_scrub /path/to/export-tree
echo "exit code: $?"
```

`--self-test` is the check that works after install. It does not need `tests/`, fixtures, or `pyproject.toml`.

Each finding prints as one line in the form `kind location:line masked-value`, for example:

```
github-token config/settings.py:12 ghp_**** len=24
private-url abc1234:old/README.md:3 gith**** len=28
```

A history location is `commit:path:line`. Deleting the file from the tree does not remove it. Rewrite that history, or export a fresh tree without it.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | No findings. |
| `1` | At least one finding. Don't publish this tree. |
| `2` | The check could not finish. Missing git, a truncated history, a bad path, or bad arguments. This is not a finding. |

## Configuration

There is one option: `--no-history`. These are fixed in the code:

- Skipped directories: `.git`, `.hg`, `.svn`, `node_modules`, `.venv`, `venv` and `__pycache__`. They are listed as unread.
- Binary files, zip files, and files that are not UTF-8 or UTF-16 are listed as unread. They do not fail the run.
- Symlinks are not followed.
- Files over 1 MB are unread. History over 20 MB exits 2. Neither is a secret finding.

## Troubleshooting

- **Missing git.** The message is on stderr and the exit code is 2. Run the scan on the git checkout you plan to publish, or pass `--no-history` if you mean to skip history.
- **History over 20 MB.** Exit code 2. Scan a fresh export with a short history, or pass `--no-history`.
- **`unread <file>:1 file exceeds the text limit`.** Check that file by hand, or leave it out of the export.
- **False positives.** Use an obvious placeholder in examples (for example `your_token_here`), or split literal patterns in test fixtures the way `tests/test_scan.py` does.
- **Don't paste findings into a chat or ticket.** The values are masked, but each line still points to where a secret is.

## Development

```sh
python3 -m unittest discover -s tests

That command needs this clone. It is not part of the installed package.
```

See [AGENTS.md](AGENTS.md).

## License

MIT. See [LICENSE](LICENSE).
