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


if __name__ == "__main__":
    unittest.main()
