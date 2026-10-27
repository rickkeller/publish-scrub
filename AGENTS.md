# Publish Scrub

This repository is a local read-only check. Run it before a private tree is copied to a public repository.

Run `python3 -m publish_scrub <directory>` from this checkout. Exit 0 means no finding. Exit 1 means do not publish that tree. Exit 2 means the path was not a directory.

It does not edit files, upload the tree, or print a full secret. It is not a hosted app. Do not send a private tree to a web service. A clean result can still miss a secret that does not match a pattern.

## Layout

```
publish_scrub/__main__.py   the whole tool: patterns, mask(), scan_tree(), scan_history(), main()
tests/test_scan.py          unittest tests (they build throwaway git repos in temp dirs)
pyproject.toml              package metadata; `publish-scrub` console script
```

## Run and test

```sh
python3 -m unittest discover -s tests
python3 -m publish_scrub .        # the repo must scan clean (exit 0) before you push
```

## Conventions

- Standard library only.
- The tool stays read-only. Never add code that edits, deletes, uploads or "fixes" files.
- Never print a full matched value. Every finding goes through `mask()`.
- Build sensitive-looking literals from pieces (for example `"ghp_" + "a" * 20`), in both the patterns and the tests, so this repo scans itself clean.
- A new pattern needs a test, an entry in the README's pattern table and a check that this repo still exits 0.

## Secrets: never commit them

- Never commit real tokens, passwords, chat ids, home-directory paths or private repo URLs, not even as test data. Use generated or placeholder values.
- Never commit scan output from a private tree.
