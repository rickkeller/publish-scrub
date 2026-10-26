# Publish Scrub

This repository is a local read-only check. Run it before a private tree is copied to a public repository.

Run `python3 -m publish_scrub <directory>` from this checkout. Exit 0 means no finding. Exit 1 means do not publish that tree. Exit 2 means the path was not a directory.

It does not edit files, upload the tree, or print a full secret. It is not a hosted app. Do not send a private tree to a web service. A clean result can still miss a secret that does not match a pattern.
