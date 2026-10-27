# WhatsApp Chat Stats 📊

[![Python](https://img.shields.io/badge/python-3.11–3.14-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

English · [Türkçe](README_TR.md)

Turns a **Turkish** WhatsApp chat export into a PDF report: who writes how much, which words, emojis and media they use, and when the chat is most active. A Markdown copy of the report is optional. Everything runs on your computer, and the chat file is never modified.

## Quick start

```bash
./setup.sh                                    # once
./run.sh examples/sample_chat.txt --output sample_report.pdf
```

This builds a report from a fictional sample chat. For your own chat, copy it into this folder as `_chat.txt` and run `./run.sh`. The report is written to `chat_stats.pdf`.

On Windows use `.\setup.ps1` and `.\run.ps1`; every option below works the same way.

## Installation

You need Python **3.11–3.14** and the Pango library, which WeasyPrint uses to draw the PDF. Setup needs an internet connection once to download packages.

```bash
git clone https://github.com/ataberkcemunal/ChatStatsForWhatsApp.git
cd ChatStatsForWhatsApp
```

### macOS

Install [Homebrew](https://brew.sh), then run `./setup.sh`. The script:

1. installs Pango with Homebrew if it is missing,
2. creates a `.venv` folder with a supported Python (`python3`, then `python3.14` … `python3.11`),
3. installs the packages pinned in `requirements.txt`.

You never need to activate `.venv` yourself; `run.sh` uses it and points WeasyPrint at Homebrew's libraries.

### Linux

Install your distribution's Pango packages ([WeasyPrint's list](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#linux)), then run `./setup.sh`.

### Windows (PowerShell)

1. Install Python 3.11–3.14 and [MSYS2](https://www.msys2.org/).
2. In the **MSYS2 UCRT64** shell run `pacman -S mingw-w64-ucrt-x86_64-pango`.
3. In PowerShell, in the project folder, run `.\setup.ps1`.

`run.ps1` looks for Pango in `C:\msys64\ucrt64\bin`. If MSYS2 is elsewhere, set the path first:

```powershell
$env:WEASYPRINT_DLL_DIRECTORIES = 'D:\msys64\ucrt64\bin'
```

CI runs setup, the tests and the sample PDF on Windows with Windows PowerShell 5.1 and MSYS2 Pango in `C:\msys64`.

## Exporting the chat

In WhatsApp, export the chat **without media**. If you get a ZIP, extract the `.txt` file. The file must be UTF-8 text in this format:

```text
[1.10.2026 10:30:00] Ayşe: Merhaba
[1.10.2026 10:31:05] Deniz: Selam
```

A comma after the date and times without seconds (`[1.10.2026, 10:30]`) are also accepted. Messages that span several lines are supported. Other languages and date formats are not recognised. Media files are not read; media is counted from placeholders such as “görüntü dahil edilmedi”.

## Usage

```bash
./run.sh [chat_file] [options]
```

| Option | Meaning | Default |
|---|---|---|
| `chat_file` | Chat export to analyse | `_chat.txt` |
| `--start-date`, `-s` | Only include records from this moment on (inclusive). `DD.MM.YYYY`, `"DD.MM.YYYY HH:MM"` or `"DD.MM.YYYY HH:MM:SS"` | whole chat |
| `--end-date`, `-e` | Only include records up to this moment (inclusive). A date without a time covers that whole day | whole chat |
| `--chat-type` | `auto`, `group` or `direct` | `auto` |
| `--output`, `-o` | PDF path | `chat_stats.pdf` |
| `--markdown-output` | Also write the report as Markdown (charts stay in the PDF) | off |
| `--help` | Show all options | |

Examples:

```bash
./run.sh "Family Chat.txt"
./run.sh --start-date "20.10.2026 14:50:00" --output october.pdf
./run.sh --start-date 01.10.2026 --end-date 31.10.2026 --output october-only.pdf
./run.sh "/full/path/_chat.txt" --chat-type group --markdown-output report.md
```

- `run.sh` switches to the project folder first, so relative paths are relative to the project folder. Use a full path for files elsewhere.
- Quote paths that contain spaces.
- The PDF, Markdown and chat paths must all be different, and the output folder must already exist.
- An existing report with the same name is overwritten. Use `--output` to keep an older one.

When the run succeeds it prints `PDF report generated: <path>` and exits with code 0. If there are no messages to report, a date is invalid or the PDF cannot be created, the error goes to stderr and the exit code is 1. In VS Code, **Terminal → Run Build Task** (`Cmd+Shift+B`) runs `run.sh` with the defaults.

## What is in the report

The PDF has the same look as the Profanity Stats report; section titles are in Turkish.

| Section | Contents |
|---|---|
| Summary cards | Messages, participants, chat days and messages per day |
| Kişiler | Per person: messages (with a bar), share, average letters, media, emojis, links, polls, deleted messages, plus a total row; then active days, participation and messages per active day |
| Aramalar | Voice and video calls by status (direct chats only, when there are calls) |
| Medya | Stickers, images, videos, audio, documents, GIFs and locations per person, with totals |
| Zaman | Weekday and hour charts side by side, a month chart when the chat spans several months, and the ten busiest days |
| Kelimeler ve ifadeler | The 45 most frequent words (4+ letters) in three columns, and the 15 most frequent two- and three-word phrases |
| Kişi bazında kelimeler | For each person, a highlighted band (messages, share, active days) and their top 10 words, two-word and three-word phrases side by side |
| Emojiler | Each person's ten most used emojis |

How the numbers are defined:

- **Messages** – every record left after filtering, including media and deleted-message records.
- **Ort. harf** – average characters per written message, spaces excluded (punctuation and symbols count). Media placeholders, poll syntax, calls and deleted messages are not written text, so they are left out of both the letters and the message count.
- **Active day** – a day on which the person has at least one record.
- **Chat days** – days with at least one record in the chat; silent days do not count.
- **Participation** – the person's active days ÷ chat days (not their share of messages).
- **Messages per active day** – the person's messages ÷ their own active days.

Numbers use Turkish formatting: `1.234` for thousands, `12,5` for decimals and `%45,3` for percentages.

With `--start-date` or `--end-date`, every figure covers only the selected period.

### Group or direct chat

`--chat-type auto` treats a chat as a group when it finds group system events or more than two participants. This is decided on the whole file, before the date filter. If an export is incomplete, or a group has only two active members, choose `group` or `direct` yourself.

- **Group:** the call table is hidden.
- **Direct:** the call table appears if there are call records. Statuses come from the exporting phone; “answered” means total calls minus missed calls, not who picked up.

Call records still count towards message totals in both cases; call status phrases are removed from the word analysis. Only actual call records are counted as calls, so a message such as “sesli arama yapalım mı?” is not.

### What is filtered out

- Records sent by **“Siz”** or **“Meta AI”**, including calls attributed to “Siz”. Mentions of these names inside other people's messages are kept.
- Recognised group and system notifications, empty records, and timestamped lines without a sender. “Edited” markers are removed from the text.
- Invisible formatting characters in sender names.

Deleted messages are counted, but their content cannot be recovered. “Siz” is not linked to a real person, and the same person written in two different ways is not merged.

Reading the export is done by `whatsapp_chat.py`, which Profanity Stats for WhatsApp shares, so both reports count the same messages.

## Sample report

[examples/sample_chat.txt](examples/sample_chat.txt) is a fictional book-club group chat, and [SAMPLE_REPORT.md](SAMPLE_REPORT.md) is the report generated from it. To regenerate both outputs:

```bash
./run.sh examples/sample_chat.txt --output sample_report.pdf --markdown-output SAMPLE_REPORT.md
```

## Troubleshooting

| Message or problem | What to do |
|---|---|
| `Python environment missing` | Run `./setup.sh` (Windows: `.\setup.ps1`). |
| `Could not read chat file` | Check the file name, path, permissions and that it is UTF-8. Quote paths with spaces. |
| `No messages found for the given criteria.` | Check the line format and the `--start-date` / `--end-date` values. |
| Pango, `libgobject` or WeasyPrint error | macOS: `brew install pango`, then use `./run.sh`. Windows: check MSYS2 Pango and `WEASYPRINT_DLL_DIRECTORIES`. |
| `ModuleNotFoundError` | Run the setup script again. |
| `Permission denied` on a `.sh` file | Use `sh setup.sh` / `sh run.sh`. |
| Call table appears in a group report | Run again with `--chat-type group`. |
| `Error generating PDF` | Read the error; the HTML is saved as `debug_output.html` for inspection. Existing reports with the same names are left untouched. |

The first run can be slow while Matplotlib builds its font cache. The PDF and the Markdown file are only replaced together, after both are ready. If a run fails, the reports already in the folder stay as they were, so check the success message and the file's modification time.

## Privacy and sharing

The analysis is local; your chat is not sent anywhere. Setup only downloads packages. Reports contain names, phrases and activity patterns, so review them before sharing.

`.gitignore` covers `_chat.txt`, `chat_stats.pdf`, `sample_report.pdf` and `debug_output.html`. Files with other names are not protected, and `.gitignore` does not apply to a ZIP you make by hand. To share the project, use **Code → Download ZIP** on GitHub: it contains only the files in the repository, never your chats or reports. Recipients still need to run setup.

## Tests and contributing

Test commands and development notes are in [CONTRIBUTING.md](CONTRIBUTING.md). GitHub Actions runs the tests and renders the sample PDF on Ubuntu with Python 3.11–3.14. On Windows it checks the PowerShell scripts, runs setup and the tests, and renders the sample PDF with Python 3.14.

## License

[MIT](LICENSE) · Created by [Ataberk Cem Ünal](https://github.com/ataberkcemunal)
