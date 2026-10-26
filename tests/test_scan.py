import subprocess
import tempfile
import unittest
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
            self.assertTrue(any(line.startswith("token history:") for line in found))
            self.assertTrue(any(line.startswith("host-path history:") for line in found))
            self.assertTrue(any(line.startswith("private-url history:") for line in found))
            self.assertTrue(any(line.startswith("chat-id history:") for line in found))
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


if __name__ == "__main__":
    unittest.main()
