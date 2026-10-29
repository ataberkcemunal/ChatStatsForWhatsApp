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

A comma after the date and times without seconds (`[1.10.2026, 10:30]`) are also accepted. Messages that span several lines are supported. A pasted line from an older chat (a header more than a day older than the messages before it) stays part of the message it was pasted into. Other languages and date formats are not recognised. Media files are not read; media is counted from placeholders such as “görüntü dahil edilmedi”.

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
| `--conversation-gap` | Hours of silence after which the next record starts a new conversation (e.g. `0.5`) | `1` |
| `--min-messages N` | Only include people with at least N records in the period (after the date filter); the others are named under the people table | `1` (everyone) |
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

Section titles in the PDF are in Turkish.

| Section | Contents |
|---|---|
| Summary cards | Messages, participants, chat days, messages per day, longest streak and longest silence, with their dates below |
| Kişiler | Per person: messages (with a bar), share, active days, participation, messages per active day and deleted messages, plus a total row; then **Paylaşımlar**: images, videos, audio, stickers, GIFs, documents, locations, polls and links per person with a total (with a bar), the most shared kind first and kinds nobody shared left out; then **Aramalar** (when there are calls) by caller: total, voice, video and length, plus answered and missed in direct chats or the average number of people who joined in groups; then conversations started and last words; in groups, whom each person replies to most and who replies to them most; then **Etiketleme** (when anyone tags with @): tags made and received (each with a bar) and the people each person tags most |
| Yazış tarzı | **Sorular**: questions per person (share, count and messages that are only question marks), highest share first; **Gülme**: laughing messages (share and count) and each person's styles (haha, hehe / hihi, hoho, Random for ksksks, sjsj and keyboard mashes, za, xd, lol, :D / :d, emoji), the highest share and the style used most first; **Emoji**: messages with an emoji (share and count) and each person's eight most used emojis in rank columns, with the chat's own in the total row. All counted once per message ("😂😂😂" is one) |
| Kelimeler ve ifadeler | The 45 most frequent words (4+ letters) in three columns, and the 30 most frequent phrases in two |
| Kişi bazında kelimeler | For each person, a highlighted band (messages, share, active days) and their top 15 words and phrases side by side |
| Kendine özgü kelimeler ve ifadeler | For each person, up to ten words and ten phrases they use distinctly more than the others, with how many of their and the others' messages contain them |
| Linkler | One row per person (the person who shares the most links first): links (with a bar) and their five most linked sites in rank columns, the site's count below its name; the total row has the chat's five. Then **İçerik türü**: links by what the address shows they hold (video, short video, post, music, map) |
| Zaman | Weekday and hour charts side by side; when the chat spans several months, a month chart and each person's monthly share (the five most active people, the rest as "Diğer") |

How the numbers are defined:

- **Messages** – every record left after filtering, including media and deleted-message records; calls are not messages.
- **Location** – a location sent with WhatsApp's location feature; its map link is not counted as a link, and typing "konum:" is not a location.
- **Active day** – a day on which the person has at least one record.
- **Chat days** – days with at least one record in the chat; silent days do not count.
- **Longest streak** – the most calendar days in a row with at least one record. **Longest silence** – the most calendar days in a row with none, between the first and last record.
- **Participation** – the person's active days ÷ chat days (not their share of messages).
- **Messages per active day** – the person's messages ÷ their own active days.
- **Conversation** – records with no silence of an hour or more between them (set with `--conversation-gap`). The first record after such a silence starts a new conversation; the last record before it is the **last word**.
- **Phrases** – patterns of 2 to 6 words within one sentence, found in at least 3 messages. A phrase that mostly appears inside a longer one is shown only as the longer one ("doğum günün kutlu olsun", not "kutlu olsun" as well). Phrases made only of words such as "ben de" or "o zaman", or only of tags, are left out; laughter breaks a phrase. Words and phrases count the messages they appear in, so a repeat in one message counts once.
- **Distinctive words and phrases** – up to ten each that a person uses clearly more often than the rest of the chat (weighted log-odds, z > 1.96). Short chats may have none.
- **Sites** – well-known sites are shown by name (instagram.com is Instagram, sahibinden.com is Sahibinden), others by their address (gib.gov.tr). Subdomains and endings count with their site (open.spotify.com and spotify.com are Spotify), a site's own short links with it (youtu.be is YouTube, t.co and twitter.com are X). Shorteners such as bit.ly hide where they lead, so they count as Kısa link; chat.whatsapp.com links are WhatsApp grup daveti. Google links are named by service (Google Haritalar, including goo.gl location links, Google Drive, Google Dokümanlar, Google Formlar, otherwise Google). Each link counts, so two links in one message are two.
- **Calls** – counted by the person who started them, never as messages. Calls the exporter made from another device (such as a computer) are written as “Siz” in the export; they are given the exporter's name, found from the “Bu mesajı sildiniz” lines only the exporter's own deleted messages have, or stay as “Siz” when that is unknown.
- **Tags** – an @ tag in a message; the same person tagged twice in one message counts once, and tagging yourself or Meta AI does not count. WhatsApp's tag for the whole group is shown as Herkes.
- **Questions and laughter** – written messages with a question (a question mark, the particle mi/mı/mu/mü, also attached as in gelcekmisin, a question word such as nasıl, neden, niye, niçin, kaç, hangi, nerede, kim, or a message that is only "ne"; "ne???" still counts as one question; neredeyse, neden olmak, "hangisi/kim/ne olursa olsun" and the ? in a link do not count) or with laughter (haha, hehe, hohoho, jajaja, ksksks, sksksk, sjsj, hshs, kdkd, zaaa, asdf, xd, :D, 😀 😃 😄 😁 😆 😅 🤣 😂 😹 (smiles such as :), :P, 🙂 😊 🙃 do not count), or a keyboard mash such as asjdkasjd: a word of six or more letters typed mostly on the home row with four home-row consonants in a row), each counted once per message; the share is of the person's written messages. The table also counts messages that are only question marks ("?", "???"); these are reactions and are not counted as questions.
- **Who replies to whom** – the export does not record which message a reply answers, so the sender of the previous record in the same conversation is used.

Numbers use Turkish formatting: `1.234` for thousands, `12,5` for decimals and `%45,3` for percentages.

With `--start-date` or `--end-date`, every figure covers only the selected period.

### Group or direct chat

`--chat-type auto` treats a chat as a group when it finds group system events or more than two participants. This is decided on the whole file, before the date filter. If an export is incomplete, or a group has only two active members, choose `group` or `direct` yourself.

The call table differs: a direct chat shows answered and missed calls; a group shows how many people joined on average instead, since in a group “missed” only means the exporting phone did not join. Only actual call records are counted as calls, so a message such as “sesli arama yapalım mı?” is not; call status phrases are not part of the word analysis.

### What is filtered out

- Records sent by **“Siz”** or **“Meta AI”**, except calls written as “Siz” (see Calls). Mentions of these names inside other people's messages are kept.
- Recognised group and system notifications, empty records, and timestamped lines without a sender. “Edited” markers are removed from the text.
- Invisible formatting characters in names. A name written with a no-break space, a double space or differently encoded letters is the same name.

Deleted messages are counted, but their content cannot be recovered. The same person saved under two different names is not merged.

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
| Call table shows answered and missed calls in a group | Run again with `--chat-type group`. |
| `Error generating PDF` | Read the error; the HTML is saved as `debug_output.html` for inspection. Existing reports with the same names are left untouched. |

The first run can be slow while Matplotlib builds its font cache. The PDF and the Markdown file are only replaced together, after both are ready. If a run fails, the reports already in the folder stay as they were, so check the success message and the file's modification time.

## Privacy and sharing

The analysis is local; your chat is not sent anywhere. Setup only downloads packages. Reports contain names, phrases and activity patterns, so review them before sharing.

`.gitignore` covers `_chat.txt`, `chat_stats.pdf`, `sample_report.pdf` and `debug_output.html`. Files with other names are not protected, and `.gitignore` does not apply to a ZIP you make by hand. To share the project, use **Code → Download ZIP** on GitHub: it contains only the files in the repository, never your chats or reports. Recipients still need to run setup.

## Tests and contributing

Test commands and development notes are in [CONTRIBUTING.md](CONTRIBUTING.md). GitHub Actions runs the tests and renders the sample PDF on Ubuntu with Python 3.11–3.14. On Windows it checks the PowerShell scripts, runs setup and the tests, and renders the sample PDF with Python 3.14.

## License

[MIT](LICENSE) · Created by [Ataberk Cem Ünal](https://github.com/ataberkcemunal)
