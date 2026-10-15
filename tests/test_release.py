import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from tools.build_release import build_release, RELEASE_FILES


class ReleaseTests(unittest.TestCase):
    def populate(self, root):
        for name in RELEASE_FILES:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('public sample', encoding='utf-8')

    def test_release_excludes_private_files_and_preserves_launchers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.populate(root)
            for name in ['_chat.txt', 'My Private Chat.txt', 'examples/private.txt',
                         'chat_stats.pdf', '.venv/secret', '.git/config', '__pycache__/cache']:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('PRIVATE', encoding='utf-8')
            output = build_release(root)
            with ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()), {
                    f'ChatStatsForWhatsApp/{name}' for name in RELEASE_FILES
                })
                self.assertTrue(all(b'PRIVATE' not in archive.read(name) for name in archive.namelist()))
                mode = archive.getinfo('ChatStatsForWhatsApp/run.sh').external_attr >> 16
                self.assertTrue(mode & 0o111)

    def test_release_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.populate(root)
            private = root / '_chat.txt'
            private.write_text('PRIVATE', encoding='utf-8')
            sample = root / 'examples/sample_chat.txt'
            sample.unlink()
            try:
                sample.symlink_to(private)
            except OSError as exc:
                self.skipTest(f'Symlink creation is unavailable: {exc}')
            with self.assertRaises(ValueError):
                build_release(root)


if __name__ == '__main__':
    unittest.main()
