# Contributing to WhatsApp Chat Statistics Analyzer

We love your input! We want to make contributing to this project as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## We Develop with GitHub
We use GitHub to host code, to track issues and feature requests, as well as accept pull requests.

## Run checks locally

Use Python 3.11–3.14. Direct dependencies are pinned in `requirements.txt` to the versions verified locally on Python 3.14; transitive dependencies are resolved by pip. Install system PDF libraries and run `./setup.sh` (or `setup.ps1` on Windows) first.

macOS:

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:/usr/local/lib .venv/bin/python -m unittest discover -s tests -v
```

Linux:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Windows PowerShell, with MSYS2 Pango installed:

```powershell
$env:WEASYPRINT_DLL_DIRECTORIES = 'C:\msys64\ucrt64\bin'
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

GitHub Actions runs the test suite and sample PDF generation on Ubuntu with Python 3.11–3.14. A Windows job checks the PowerShell scripts' syntax, then runs `setup.ps1`, the test suite and `run.ps1` on the sample chat with Python 3.14, Windows PowerShell 5.1 and MSYS2 Pango. Workflow execution results are available only after the changes are pushed.

## Shared files

`whatsapp_chat.py` (the export parser), `report_style.py` (the PDF look) and `tests/test_whatsapp_chat.py` may be copied into other projects next to this one. The copies here are the originals. A test fails while a copy in a sibling folder differs; it is skipped when there is none. Keep these modules standard-library only.

## Sample data

Use only fictional chat data in tests and examples. To regenerate the sample report on macOS/Linux:

```bash
./run.sh examples/sample_chat.txt --output sample_report.pdf --markdown-output SAMPLE_REPORT.md
```

Never commit real chat exports, personal reports, virtual environments, or credentials.

## We Use [Github Flow](https://guides.github.com/introduction/flow/index.html)
Pull requests are the best way to propose changes to the codebase. We actively welcome your pull requests:

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.
6. Issue that pull request!

## Any contributions you make will be under the MIT Software License
In short, when you submit code changes, your submissions are understood to be under the same [MIT License](http://choosealicense.com/licenses/mit/) that covers the project. Feel free to contact the maintainers if that's a concern.

## Report bugs using GitHub's [issue tracker](https://github.com/ataberkcemunal/ChatStatsForWhatsApp/issues)
We use GitHub issues to track public bugs. Report a bug by [opening a new issue](https://github.com/ataberkcemunal/ChatStatsForWhatsApp/issues/new); it's that easy!

## Write bug reports with detail, background, and sample code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

## License
By contributing, you agree that your contributions will be licensed under its MIT License.
