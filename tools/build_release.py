"""Build a source ZIP from an explicit list; never include local chat exports."""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED


ROOT = Path(__file__).resolve().parents[1]
RELEASE_FILES = (
    'ChatStatsForWhatsApp.py', 'whatsapp_chat.py', 'requirements.txt', 'setup.sh', 'run.sh',
    'setup.ps1', 'run.ps1', '.gitignore', 'README.md', 'README_TR.md',
    'CONTRIBUTING.md', 'LICENSE', 'SAMPLE_REPORT.md',
    'examples/sample_chat.txt', 'tests/test_parser_exclusions.py', 'tests/test_whatsapp_chat.py',
    'tests/test_release.py', 'tools/build_release.py', '.github/workflows/tests.yml',
    '.vscode/settings.json', '.vscode/tasks.json',
)


def build_release(root=ROOT, output=None):
    root = Path(root).resolve()
    output = Path(output) if output else root / 'dist' / 'ChatStatsForWhatsApp.zip'
    output = output.resolve()
    sources = []
    for name in RELEASE_FILES:
        source = root / name
        if any(parent.is_symlink() for parent in (source, *source.parents) if parent.is_relative_to(root)):
            raise ValueError(f'Symlinks are not allowed in the release: {name}')
        if not source.is_file() or not source.resolve().is_relative_to(root):
            raise ValueError(f'Required release file missing or outside project: {name}')
        sources.append((name, source))
    if output in {source.resolve() for _, source in sources} or output.suffix.lower() != '.zip':
        raise ValueError('Output must be a .zip file separate from source files.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for name, source in sources:
            info = ZipInfo(f'ChatStatsForWhatsApp/{name}')
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='ZIP path; default: dist/ChatStatsForWhatsApp.zip')
    args = parser.parse_args()
    print(build_release(output=args.output))
