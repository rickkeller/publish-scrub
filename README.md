# Publish Scrub

Local read-only check before a private tree is copied to a public repository.

It looks for token shapes, password assignments, chat ids, host paths, and private repository URLs in the working tree and in git history. A finding is a kind, a location, and a masked value. It does not edit files, upload the tree, or print a full secret.

A public export is not done until this check exits 0.

This is not a hosted app. Do not send a private tree to a web service. This is not a substitute for reading the export. A clean check can still miss a secret that does not match a pattern.
