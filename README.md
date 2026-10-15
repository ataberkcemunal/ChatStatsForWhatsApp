# WhatsApp Chat Stats 📊

[![Python](https://img.shields.io/badge/python-3.11–3.14-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

English · [Türkçe](README_TR.md)

Generate PDF and optional Markdown reports from WhatsApp chat exports in **Turkish**. Analyze messages, words, emojis, media, and activity over time. The source chat file is unchanged.

## Quick start

Open a terminal in the project folder. Run setup once, then use the launcher for subsequent reports:

```bash
./setup.sh
./run.sh examples/sample_chat.txt --output sample_report.pdf
```

This analyzes a fictional chat. For your own chat, place `_chat.txt` in the project folder and run `./run.sh`. The default report is `chat_stats.pdf`.

## Installation

Python **3.11–3.14** is required. Local verification used Python 3.14; GitHub Actions is configured for all four versions. Initial setup needs internet access to download packages. Direct dependencies are pinned in `requirements.txt`; pip resolves transitive dependencies.

Download or clone the project:

```bash
git clone https://github.com/ataberkcemunal/ChatStatsForWhatsApp.git
cd ChatStatsForWhatsApp
```

Quote folder paths containing spaces: `cd "/path/to/project folder"`.

### macOS

Install Python and [Homebrew](https://brew.sh). Check them with `python3 --version` and `brew --version`.

```bash
./setup.sh
```

Setup installs Pango through Homebrew if missing, creates `.venv`, and installs Python packages into it. An existing `.venv` is used first. Otherwise, setup checks for a supported `python3`, then `python3.14`, `python3.13`, `python3.12`, and `python3.11`.

Manual environment activation is unnecessary. The leading dot makes `.venv` a hidden folder. Pango's system libraries live under Homebrew; `run.sh` configures their search path.

### Linux

Install your distribution's Pango system packages, then run `./setup.sh`. Package names vary; see the [WeasyPrint installation instructions](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#linux).

### Windows (PowerShell)

Install Python 3.11–3.14 and check that `python` works. Install [MSYS2](https://www.msys2.org/), then install Pango in the **MSYS2 UCRT64** shell:

```bash
pacman -S mingw-w64-ucrt-x86_64-pango
```

Close the MSYS2 shell. Open PowerShell in the project folder:

```powershell
.\setup.ps1
.\run.ps1 examples/sample_chat.txt --output sample_report.pdf
```

The default library path is `C:\msys64\ucrt64\bin`. For a custom installation, set the appropriate path in each new PowerShell session:

```powershell
$env:WEASYPRINT_DLL_DIRECTORIES = 'D:\msys64\ucrt64\bin'
```

These steps follow the [WeasyPrint Windows documentation](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows). Windows execution has not been verified locally; CI checks PowerShell syntax only. If scripts are blocked, follow your computer's script execution policy.

In the examples below, replace `./run.sh` with `.\run.ps1` on Windows; the options are the same.

## Prepare your chat file

Export the WhatsApp chat **without media**. If it arrives as an archive, extract the `.txt` file and copy it into the project folder. The default name is `_chat.txt`, but you can specify another name.

Supported UTF-8 plain text format:

```text
[1.10.2026 10:30:00] Ayşe: Merhaba
[1.10.2026 10:31:05] Deniz: Selam
```

Multiline messages are supported. Other languages, date formats, or export formats may not be recognized. Media contents are not inspected; counts come from placeholders such as “görüntü dahil edilmedi”.

## Usage

Run these commands from the project folder:

| Purpose | Command |
|---|---|
| Analyze the default `_chat.txt` | `./run.sh` |
| Choose another file | `./run.sh chat.txt` |
| Use a filename containing spaces | `./run.sh "Family Chat.txt"` |
| Set a start date | `./run.sh --start-date 01.10.2026` |
| Set a start date and time | `./run.sh --start-date "01.10.2026 18:30:00"` |
| Explicitly select a group chat | `./run.sh --chat-type group` |
| Explicitly select a direct chat | `./run.sh --chat-type direct` |
| Save the PDF under another name | `./run.sh --output report.pdf` |
| Also export Markdown text | `./run.sh --markdown-output report.md` |
| Show help | `./run.sh --help` |

Options can be combined:

```bash
./run.sh "Family Chat.txt" --chat-type group --start-date 01.10.2026 --output family.pdf
```

Dates use `DD.MM.YYYY`, optionally followed by `HH:MM:SS`. The start time is inclusive; there is no end-date option. Relative paths are resolved from the project folder. For an external file, use `./run.sh "/full/path/chat.txt"`.

A successful run prints `PDF report generated: chat_stats.pdf`, or the custom output path. Open that PDF to view the report.

The default PDF is overwritten on each successful run. Use `--output` to preserve an earlier report. Input, PDF, and Markdown paths must differ; destination folders must already exist. The Markdown export contains chart descriptions; the charts themselves are in the PDF.

In VS Code, **Terminal → Run Build Task** also generates the report (`Cmd+Shift+B` on macOS).

## Group and direct chats

The default `--chat-type auto` detects a group from group system events or more than two participants. Detection runs before date filtering. For incomplete exports or groups with only two active participants, explicitly select `group` or `direct`.

- **Group chats:** The Call Statistics table is hidden.
- **Direct chats:** The table appears if call records exist. Status reflects the exporting account's records. “Answered” is total calls minus missed records; it does not establish who answered.

Hiding the table does not remove other senders' call records from every metric. Call records can still contribute to message totals; recognized call status phrases are cleaned from word and phrase analysis.

## Read the report

The report's headings are in Turkish.

| Section | Contents |
|---|---|
| Sohbet Zaman Çizelgesi | First and last included record timestamps |
| Kullanıcı İstatistikleri | Per-person messages, average characters, media, emojis, links, polls, and deleted messages |
| Arama İstatistikleri | Voice/video call records and status counts, only for direct chats with calls |
| Detaylı Medya İstatistikleri | Stickers, images, videos, audio, documents, GIFs, and locations |
| Words and combinations | Frequent words, bigrams, and trigrams across the chat and by person |
| Emoji statistics | Most-used emojis by person, if emojis exist |
| Zamansal İstatistikler | Day-of-week, hour, and month distributions; ten busiest days |
| Kullanıcı Etkinlik Zaman Çizelgesi | Active days, participation rate, and messages per active day |

- **Messages:** Records remaining after filtering; these can include media and deleted message records.
- **Ort. Harf:** Average characters per message after removing spaces; punctuation and symbols can be included.
- **Active day:** A day on which the participant has at least one included record.
- **Total chat days:** Distinct days containing at least one included record; silent calendar days between them do not count.
- **Participation rate:** The participant's active days divided by total chat days, rather than their share of messages.
- **Messages per active day:** The participant's total messages divided by their own active days.

With a date filter, metrics cover only the selected period.

### Automatic filters

Records sent by **“Siz”** or **“Meta AI”** are excluded from all analysis, including calls attributed to “Siz”. Invisible formatting characters are removed from sender names. Other participants' messages mentioning these names are preserved.

Recognized group and system notifications are excluded; edit markers are cleaned. Deleted messages are counted from their markers; original contents cannot be recovered. “Siz” is not mapped to a real person, and differently written sender names are not automatically merged.

## Sample data and report

[examples/sample_chat.txt](examples/sample_chat.txt) is a completely fictional book-club chat. [SAMPLE_REPORT.md](SAMPLE_REPORT.md) is generated from it. The sample is a group chat, so its report has no call table. Regenerate it with:

```bash
./run.sh examples/sample_chat.txt --output sample_report.pdf --markdown-output SAMPLE_REPORT.md
```

## Troubleshooting

| Problem | Action |
|---|---|
| `Python ortamı bulunamadı` | Run `./setup.sh`, or `.\setup.ps1` on Windows. |
| `Sohbet dosyası okunamadı` | Check the name, path, read permissions, and UTF-8 encoding; quote paths containing spaces. |
| `No messages found for the given criteria.` | Check the line format and whether records remain after date filtering. |
| Pango, `libgobject`, or WeasyPrint error | On macOS, use `brew install pango` and `./run.sh`; on Windows, check MSYS2 Pango and the DLL path. |
| `ModuleNotFoundError` | Reinstall packages with the setup launcher. |
| `Permission denied` for a `.sh` file | Use `sh setup.sh` or `sh run.sh`. |
| A group report shows the call table | Regenerate with `--chat-type group`. |
| PDF generation error | Inspect the terminal error and `debug_output.html` if created. |

The first chart may take time while the font cache is built. If no records are found or PDF generation fails, an earlier PDF can remain in the folder. Check the success message and modification time.

## Data and sharing

Analysis runs locally; the application does not send your chat to an analysis service. Package downloads during setup are separate. Reports include names, phrases, and activity information; review their contents before sharing.

`.gitignore` excludes the default `_chat.txt`, `chat_stats.pdf`, and `sample_report.pdf`. Other filenames are not automatically protected. `.gitignore` does not filter a ZIP you create manually from the folder.

For distribution, use the ZIP builder's explicit project file list:

```bash
.venv/bin/python tools/build_release.py
```

Windows:

```powershell
.venv\Scripts\python.exe tools/build_release.py
```

The output is `dist/ChatStatsForWhatsApp.zip`. It includes code, documentation, tests, and fictional sample data; it excludes private chats, reports, environments, and caches. This is a source package; recipients still run setup.

If `.venv` is deleted, recreate it with setup. `__pycache__` folders are regenerable Python caches.

## Tests and contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for test commands and development instructions. GitHub Actions is configured to run tests, generate the sample PDF, and build the ZIP on Ubuntu with Python 3.11–3.14. The Windows job checks PowerShell syntax. Remote results become available after changes are pushed to GitHub.

## License

[MIT](LICENSE). Created by [Ataberk Cem Ünal](https://github.com/ataberkcemunal).
