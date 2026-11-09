import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from publish_scrub.__main__ import main, scan


def _secret_file() -> str:
    token = "ghp_" + ("a" * 20)
    home = "/" + "home" + "/app/demo-tree"
    private = "https://github.com/acme/demo" + "-" + "private"
    chat = "chat_id=" + ("7" * 10)
    password = "pass" + "word=" + '"' + ("s" * 12) + '"'
    return "\n".join((token, home, private, chat, password)) + "\n"


class ScanTest(unittest.TestCase):
    def test_a_dirty_fixture_fails_and_does_not_print_the_secret(self):
        secret = _secret_file()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.txt").write_text(secret, encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "add", "notes.txt"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-m", "add"], cwd=root, check=True, capture_output=True)
            (root / "notes.txt").write_text("clean\n", encoding="utf-8")
            subprocess.run(["git", "add", "notes.txt"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-m", "remove"], cwd=root, check=True, capture_output=True)
            found = scan(root)
            self.assertTrue(any(line.startswith("github-token ") and ":notes.txt:" in line for line in found))
            self.assertTrue(any(line.startswith("host-path ") and ":notes.txt:" in line for line in found))
            self.assertTrue(any(line.startswith("private-url ") and ":notes.txt:" in line for line in found))
            self.assertTrue(any(line.startswith("chat-id ") and ":notes.txt:" in line for line in found))
            joined = "\n".join(found)
            self.assertNotIn("ghp_" + ("a" * 20), joined)
            self.assertNotIn("/" + "home" + "/app/demo-tree", joined)
            self.assertEqual(main([tmp]), 1)

    def test_a_clean_tree_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("A clean note.\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-m", "add"], cwd=root, check=True, capture_output=True)
            self.assertEqual(scan(root), [])
            self.assertEqual(main([tmp]), 0)

    def test_missing_git_is_not_a_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("A clean note.\n", encoding="utf-8")
            err = io.StringIO()
            with redirect_stderr(err):
                code = main([tmp])
            self.assertEqual(code, 2)
            self.assertIn("git history was not scanned", err.getvalue())
            self.assertNotIn("git history was not scanned", "\n".join(scan(root)))

    def test_non_utf8_history_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "odd.txt").write_bytes(b"caf\xe9\n")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "add", "odd.txt"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-m", "add"], cwd=root, check=True, capture_output=True)
            self.assertEqual(main([tmp]), 0)

    def test_prefixed_secret_is_found_and_placeholder_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = "AWS_SECRET_ACCESS_KEY=" + ("k" * 16)
            fake = "password=" + "todo"
            actions = "password: ${{ secrets.EXAMPLE_TOKEN }}"
            (root / ".env").write_text(real + "\n" + fake + "\n" + actions + "\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            found = scan(root)
            joined = "\n".join(found)
            self.assertTrue(any(line.startswith("assignment ") for line in found))
            self.assertNotIn("k" * 16, joined)
            self.assertNotIn("EXAMPLE_TOKEN", joined)
            self.assertEqual(sum(1 for line in found if line.startswith("assignment ")), 1)

    def test_large_file_is_unread_and_does_not_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "big.lock").write_bytes(b"x" * (1_000_001))
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "add", "big.lock"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-m", "add"], cwd=root, check=True, capture_output=True)
            out = io.StringIO()
            with redirect_stdout(out):
                code = main([tmp])
            self.assertEqual(code, 0)
            self.assertIn("unread big.lock:1", out.getvalue())

    def test_self_test_does_not_need_the_source_tree(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--self-test"])
        self.assertEqual(code, 0)
        self.assertIn("self-test passed", out.getvalue())

    def test_home_path_after_equals_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            line = "HOME=" + "/" + "home" + "/app/demo"
            (root / "env.txt").write_text(line + "\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "add", "env.txt"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-m", "add"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            found = scan(root)
            self.assertTrue(any(line.startswith("host-path ") and "env.txt" in line for line in found))
            self.assertNotIn("/" + "home" + "/app/demo", "\n".join(found))

    def test_unreadable_directory_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hidden = root / "hidden"
            hidden.mkdir()
            (hidden / "note.txt").write_text("clean\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            hidden.chmod(0)
            try:
                err = io.StringIO()
                with redirect_stderr(err):
                    code = main([tmp])
                self.assertEqual(code, 2)
                self.assertIn("working tree was not fully scanned", err.getvalue())
            finally:
                hidden.chmod(0o700)

    def test_quoted_history_path_keeps_the_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = "my notes.txt"
            token = "ghp_" + ("b" * 20)
            (root / name).write_text(token + "\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "add", name], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-m", "add"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            found = scan(root)
            hits = [line for line in found if line.startswith("github-token ") and "my notes.txt" in line]
            self.assertTrue(hits)
            self.assertNotIn('"', hits[0])
            self.assertNotIn(token, "\n".join(found))

    def test_history_over_the_cap_exits_before_returning_findings(self):
        from publish_scrub import __main__ as scrub

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.txt").write_text("A clean note.\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "add", "notes.txt"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-m", "add"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            old = scrub.HISTORY_LIMIT
            scrub.HISTORY_LIMIT = 20
            try:
                _found, failures, _unread = scrub.scan_history(root)
            finally:
                scrub.HISTORY_LIMIT = old
            self.assertIn("git history scan was truncated", failures)

    def test_truncated_history_keeps_the_tree_finding_and_drops_history(self):
        from publish_scrub import __main__ as scrub

        history_token = "ghp_" + ("c" * 20)
        tree_token = "ghp_" + ("d" * 20)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.txt").write_text(history_token + "\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "add", "notes.txt"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-m", "add"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            (root / "notes.txt").write_text(tree_token + "\n", encoding="utf-8")
            old = scrub.HISTORY_LIMIT
            scrub.HISTORY_LIMIT = 20
            try:
                out = io.StringIO()
                err = io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    code = main([tmp])
            finally:
                scrub.HISTORY_LIMIT = old
            text = out.getvalue()
            self.assertEqual(code, 2)
            self.assertIn("git history scan was truncated", err.getvalue())
            self.assertIn("github-token ", text)
            self.assertNotIn(history_token, text)
            self.assertNotIn(tree_token, text)

    def test_digit_only_home_segment_is_not_a_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            line = "/" + "home" + "/12345/notes"
            (root / "env.txt").write_text(line + "\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            found = scan(root)
            self.assertFalse(any(line.startswith("host-path ") for line in found))

    def test_a_file_path_is_not_a_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "note.txt"
            note.write_text("clean\n", encoding="utf-8")
            err = io.StringIO()
            with redirect_stderr(err):
                code = main([str(note)])
            self.assertEqual(code, 2)
            self.assertIn("not a directory", err.getvalue())

    def test_unreadable_file_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            locked = root / "locked.txt"
            locked.write_text("clean\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            locked.chmod(0)
            try:
                err = io.StringIO()
                with redirect_stderr(err):
                    code = main([tmp])
                self.assertEqual(code, 2)
                self.assertIn("working tree was not fully scanned", err.getvalue())
            finally:
                locked.chmod(0o600)

    def test_zip_and_binary_are_unread_and_do_not_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pack.zip").write_bytes(b"not-a-real-zip")
            (root / "bin.dat").write_bytes(b"\0\x01\x02")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            out = io.StringIO()
            with redirect_stdout(out):
                code = main([tmp])
            text = out.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("unread pack.zip:1 zip was not opened", text)
            self.assertIn("unread bin.dat:1 file was not decoded", text)

    def test_openai_key_without_a_digit_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skipped = "sk-" + ("a" * 12)
            kept = "sk-" + ("a" * 8) + "1"
            (root / "keys.txt").write_text(skipped + "\n" + kept + "\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            found = scan(root)
            joined = "\n".join(found)
            self.assertEqual(sum(1 for line in found if line.startswith("openai-key ")), 1)
            self.assertNotIn(skipped, joined)
            self.assertNotIn(kept, joined)

    def test_each_pattern_is_masked(self):
        samples = {
            "aws-key": "AKIA" + ("A" * 8),
            "slack-token": "xoxb-" + ("a" * 8),
            "slack-webhook": "https://hooks.slack.com/services/" + ("T" * 8),
            "private-key": "-----BEGIN " + "PRIVATE KEY-----",
            "db-url": "postgres://" + "user" + "@db",
            "bot-token": "12345678:" + ("a" * 30),
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "samples.txt").write_text("\n".join(samples.values()) + "\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            out = io.StringIO()
            with redirect_stdout(out):
                code = main([tmp])
            text = out.getvalue()
            self.assertEqual(code, 1)
            for kind, value in samples.items():
                self.assertTrue(any(line.startswith(kind + " ") for line in text.splitlines()), kind)
                self.assertNotIn(value, text)



if __name__ == "__main__":
    unittest.main()
