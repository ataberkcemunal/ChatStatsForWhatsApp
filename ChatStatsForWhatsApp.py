import argparse
import base64
import html
import io
import itertools
import os
import re
import sys
import tempfile
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

import emoji
import markdown
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (the backend must be chosen first)
from matplotlib.ticker import MaxNLocator  # noqa: E402
import pandas as pd
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

import whatsapp_chat
from whatsapp_chat import turkish_lower


# Patterns to detect media placeholders in chat. Calls are tracked separately,
# so they intentionally do not live in this list.
MEDIA_PATTERNS = [
    "Çıkartma dahil edilmedi",
    "görüntü dahil edilmedi",
    "video dahil edilmedi",
    "ses dahil edilmedi",
    "belge dahil edilmedi",
    "Konum: https://maps.google.com",
    "GIF dahil edilmedi",
]
MEDIA_PATTERNS_LOWER = [turkish_lower(pattern) for pattern in MEDIA_PATTERNS]
MEDIA_TYPE_PATTERNS = {
    "Stickers": "çıkartma dahil edilmedi",
    "Images": "görüntü dahil edilmedi",
    "Videos": "video dahil edilmedi",
    "Audio": "ses dahil edilmedi",
    "Documents": "belge dahil edilmedi",
    "GIFs": "GIF dahil edilmedi",
    "Locations": "konum:",
}

# Regex for links, tags and system indicators (edited/deleted)
LINK_REGEX = r"https?://\S+"
TAG_REGEX = r"@\u2068(.*?)\u2069"
CLEANUP_REGEX = re.compile(
    r"\u200e?<.*?(?:mesaj düzenlendi|message was edited)>|\u200e?Bu mesajı sildiniz\.|\u200e?Bu mesaj silindi\.",
    re.IGNORECASE,
)
QUOTED_CHAT_HEADER_REGEX = re.compile(
    r"\[\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\]\s+[^:\n]{1,80}:"
)


def is_poll(text):
    """Check if a message is a poll based on marker or heuristic"""
    if not text:
        return False

    # Check for System Poll Marker (\u200e followed by ANKET:)
    has_marker = bool(re.search(r"\u200e\s*ANKET:", text, re.IGNORECASE))

    # Check for heuristic: Contains both "ANKET:" and "SEÇENEK:" (ignoring case)
    # This covers cases where marker is lost but structure is clear
    upper_text = str(text).upper()
    has_heuristic = "ANKET:" in upper_text and "SEÇENEK:" in upper_text

    return has_marker or has_heuristic


def clean_media_placeholders(text):
    """Removes U+200E, media placeholders, and poll system text to extract pure user content"""
    if not text:
        return ""

    # Identify if it's a poll using the helper
    is_system_poll = is_poll(text)

    # Remove markers
    res = text.replace("\u200e", "").replace("\u200f", "")

    # Remove pasted WhatsApp headers from quoted chat snippets.
    res = QUOTED_CHAT_HEADER_REGEX.sub(" ", res)

    # Remove standard media placeholders
    for pat in MEDIA_PATTERNS:
        res = re.sub(re.escape(pat), "", res, flags=re.IGNORECASE)

    # Remove Poll system text
    # ONLY if it was identified as a system poll (either by marker or heuristic)
    if is_system_poll:
        flags = re.IGNORECASE
        # 1. Remove "ANKET:" prefix (start of string or after space)
        res = re.sub(r"(?:^|\s)ANKET:\s*", " ", res, flags=flags)
        # 2. Remove "SEÇENEK:" globally
        res = re.sub(r"(?:^|\s)SEÇENEK:\s*", " ", res, flags=flags)
        # 3. Remove vote counts "(X oy)" globally
        res = re.sub(r"\s*\(\d+\s+oy\)", "", res, flags=flags)

    return re.sub(r"\s+", " ", res).strip()


def clean_message(text):
    # Remove all invisible and control characters, normalize whitespace, and lowercase
    return "".join(
        c for c in text if not unicodedata.category(c).startswith("C")
    ).strip()


def clean_message_lower(text):
    return turkish_lower(clean_message(text))


def has_media_placeholder(cleaned_text):
    return any(pattern in cleaned_text for pattern in MEDIA_PATTERNS_LOWER)


def get_message_stats(text, kind=whatsapp_chat.MESSAGE):
    cleaned_text = clean_message_lower(text)
    written = "" if kind != whatsapp_chat.MESSAGE else clean_media_placeholders(text)
    emojis = [em["emoji"] for em in emoji.emoji_list(text)]

    # Only what the person wrote counts: media placeholders, poll syntax and
    # call status text are not letters someone typed.
    return {
        "letter_count": len(written.replace(" ", "")),
        "has_text": int(bool(written)),
        "words": _get_tokens(written, min_len=4, keep_apostrophes=True),
        "phrase_words": _get_tokens(written, min_len=2, keep_apostrophes=True),
        "links": len(re.findall(LINK_REGEX, text)),
        "emojis": emojis,
        "emoji_count": len(emojis),
        "media": 1 if has_media_placeholder(cleaned_text) else 0,
    }


def update_message_stats(entry):
    entry.update(get_message_stats(entry["message"], entry["kind"]))


def add_time_columns(df):
    if df.empty:
        return df

    df = df.copy()
    df["date"] = df["datetime"].dt.date
    df["weekday"] = df["datetime"].dt.day_name()
    df["month"] = df["datetime"].dt.to_period("M").astype(str)
    df["hour"] = df["datetime"].dt.hour
    return df


def _get_tokens(text, min_len=2, keep_apostrophes=False):
    """Helper to tokenize text while preserving tags as single units"""
    placeholders = {}

    def repl(m):
        # Extract name, remove all spaces and control characters
        raw_name = m.group(1)
        # Remove invisible/control characters and spaces
        clean_name = "".join(
            c for c in raw_name if not unicodedata.category(c).startswith("C")
        )
        clean_name = clean_name.replace(" ", "")

        token = f"ZXTG{len(placeholders)}TX"
        formatted_name = f"@{clean_name}"
        # Store with standard lower() since our token is ascii-safe
        placeholders[token.lower()] = formatted_name
        return token

    # Remove links and system indicators
    text = re.sub(LINK_REGEX, "", text)
    text = CLEANUP_REGEX.sub("", text)

    # Replace tags with placeholders BEFORE tokenization
    text = re.sub(TAG_REGEX, repl, text)

    # Normalize apostrophes (curly to straight) for consistent processing
    text = text.replace("’", "'").replace("‘", "'")

    # Tokenize (keeping alphanumeric and underscores)
    # Note: we use words and placeholders as tokens
    lower_text = turkish_lower(text)
    if keep_apostrophes:
        # Match words potentially containing apostrophes (e.g. "ankara'da")
        words = re.findall(r"\b\w+(?:'\w+)*\b", lower_text)
    else:
        # Match only word characters, splitting at apostrophes
        words = re.findall(r"\b\w+\b", lower_text)

    # Restore placeholders and filter by min_len
    tokens = []
    for w in words:
        # We use standard .lower() for the lookup because our placeholder is ASCII
        lookup_w = w.lower()
        if lookup_w in placeholders:
            tokens.append(placeholders[lookup_w])
        elif len(w) >= min_len and not w.isdigit():
            tokens.append(w)

    return tokens


# Parse chat file into DataFrame
def parse_chat(filepath):
    """Load an export into a DataFrame; the shared parser decides what counts."""
    chat = whatsapp_chat.read_chat(filepath)
    records = []
    for record in chat.records:
        deleted = record.kind == whatsapp_chat.DELETED
        # Edit markers and deletion notices are not part of what was written.
        text = CLEANUP_REGEX.sub("", record.text.replace("\n", " ")).strip()
        entry = {
            "datetime": record.timestamp,
            "user": record.sender,
            "message": text,
            "kind": record.kind,
            "poll": 0 if deleted else int(is_poll(text)),
            "deleted": int(deleted),
        }
        update_message_stats(entry)
        records.append(entry)
    df = add_time_columns(pd.DataFrame(records))
    # Save the type before date filtering can reduce the participant count.
    df.attrs["is_group_chat"] = chat.is_group_chat
    return df


def parse_start_date(value):
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError("Please use DD.MM.YYYY, 'DD.MM.YYYY HH:MM' or 'DD.MM.YYYY HH:MM:SS'")


def parse_end_date(value):
    """Inclusive upper bound; a date without a time covers that whole day."""
    end = parse_start_date(value)
    if ":" not in value:
        end = end.replace(hour=23, minute=59, second=59)
    return end


DAY_NAMES = {
    "Monday": "Pazartesi",
    "Tuesday": "Salı",
    "Wednesday": "Çarşamba",
    "Thursday": "Perşembe",
    "Friday": "Cuma",
    "Saturday": "Cumartesi",
    "Sunday": "Pazar",
}
MONTH_NAMES = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
CHART_COLOR = "#0f766e"

REPORT_CSS = """
@page {
    size: A4;
    margin: 18mm 16mm 19mm;
    @bottom-right { content: counter(page) " / " counter(pages); font-size: 8pt; color: #64748b; }
}
body { font-family: "DejaVu Sans", Arial, sans-serif; font-size: 9.5pt; line-height: 1.45; color: #17253b; }
.eyebrow { color: #0f766e; font-size: 9pt; font-weight: bold; letter-spacing: 1.5px; }
h1 { font-size: 26pt; line-height: 1.15; margin: 6px 0 10px; color: #10253f; }
h2 { font-size: 15pt; color: #10253f; margin: 26px 0 8px; padding-bottom: 4px;
     border-bottom: 2px solid #0f766e; break-after: avoid; }
h3, h4 { font-size: 11pt; color: #334155; margin: 16px 0 6px; break-after: avoid; }
p { margin: 7px 0; }
.meta { color: #64748b; font-size: 8.5pt; }
.kpis { width: 100%; border-collapse: separate; border-spacing: 5px; margin: 12px 0 4px; table-layout: fixed; }
.kpis td { background: #eff3f8; padding: 11px 9px; border: 0; vertical-align: top; }
.kpis .value { display: block; font-size: 17pt; font-weight: bold; color: #0f766e; }
.kpis .value.small { font-size: 12pt; padding: 5px 0 4px; }
.kpis .label { display: block; font-size: 8pt; color: #475569; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 14px; font-size: 8.5pt; }
th, td { border-bottom: 1px solid #e2e8f0; padding: 4px 7px; text-align: left; }
th { background-color: #e6f2f1; color: #10253f; }
tr { break-inside: avoid; }
tr:nth-child(even) td { background-color: #f8fafc; }
img { display: block; margin: 6px auto 12px; }
"""


def md_text(value):
    """Escape a name or word for a Markdown table cell or heading."""
    text = html.escape(str(value), quote=False).replace("\\", "\\\\")
    for char in "|*_`[]#":
        text = text.replace(char, "\\" + char)
    return text


def format_number(n):
    return f"{n:,}".replace(",", ".")


def format_decimal(n):
    return f"{n:,.1f}".replace(",", "_").replace(".", ",").replace("_", ".")


def format_datetime(value):
    return value.strftime("%d.%m.%Y %H:%M")


def create_chart(x_data, y_data, title, xlabel, ylabel, chart_type="bar"):
    fig, ax = plt.subplots(figsize=(10, 4.8))
    if chart_type == "bar":
        ax.bar(x_data, y_data, color=CHART_COLOR)
    else:
        ax.plot(x_data, y_data, marker="o", linestyle="-", color=CHART_COLOR)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", labelrotation=45)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    img_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f'<img src="data:image/png;base64,{img_base64}" style="width:100%; max-width:800px;" />'


def _phrase_table(write_line, title, counter, limit):
    write_line(f"**{title}**")
    write_line("")
    write_line("| İfade | Sayı |")
    write_line("|-------|------|")
    for phrase, count in counter.most_common(limit):
        write_line(f"| {md_text(' '.join(phrase))} | {format_number(count)} |")
    write_line("")


# Compute and print statistics
def compute_stats(
    df, *, chat_type="auto", output_file="chat_stats.pdf", markdown_output=None
):
    is_group_chat = (
        df.attrs.get("is_group_chat", df["user"].nunique() > 2)
        if chat_type == "auto"
        else chat_type == "group"
    )
    # Collect all markdown content
    markdown_content = []

    def write_subheader(title):
        markdown_content.append(f"\n## {title}\n")

    def write_line(content):
        markdown_content.append(content + "\n")

    def user_messages(user):
        return df[df["user"] == user]

    def count_contains(series, pattern, regex=False):
        return series.str.contains(pattern, case=False, na=False, regex=regex).sum()

    # Summary shown at the top of both reports
    first, last = df["datetime"].min(), df["datetime"].max()
    total_chat_days = df["date"].nunique()
    summary = [
        ("Mesaj", format_number(len(df))),
        ("Katılımcı", format_number(df["user"].nunique())),
        ("Sohbet günü", format_number(total_chat_days)),
        ("Dönem", f"{first:%d.%m.%Y} – {last:%d.%m.%Y}"),
    ]
    summary_markdown = "".join(f"**{label}:** {value}  \n" for label, value in summary)
    summary_markdown += f"**İlk mesaj:** {format_datetime(first)} · **Son mesaj:** {format_datetime(last)}\n"
    kpis = "".join(
        f'<td><span class="value{" small" if label == "Dönem" else ""}">{value}</span>'
        f'<span class="label">{label}</span></td>'
        for label, value in summary
    )
    header_html = (
        '<div class="eyebrow">WHATSAPP SOHBET ANALİZİ</div>'
        "<h1>Sohbet İstatistikleri</h1>"
        f'<p class="meta">{format_datetime(first)} – {format_datetime(last)}'
        f' · {"Grup sohbeti" if is_group_chat else "Birebir sohbet"}</p>'
        f'<table class="kpis"><tr>{kpis}</tr></table>'
    )

    # User Statistics
    write_subheader("👥 Kullanıcı İstatistikleri")

    # Create comprehensive user stats table
    user_stats = []
    for user in df["user"].unique():
        user_df = user_messages(user)
        written = user_df["has_text"].sum()
        user_stats.append(
            {
                "User": user,
                "Messages": len(user_df),
                # Average over messages with written text; media-only messages have none.
                "AvgLetters": user_df["letter_count"].sum() / written if written else 0,
                "Media": user_df["media"].sum(),
                "Emojis": user_df["emoji_count"].sum(),
                "Links": user_df["links"].sum(),
                "Polls": user_df["poll"].sum(),
                "Deleted": user_df["deleted"].sum(),
            }
        )

    # Sort by message count
    user_stats.sort(key=lambda x: x["Messages"], reverse=True)
    sorted_users = [s["User"] for s in user_stats]

    write_line(
        "| Kullanıcı | Ort. Harf | Medya | Emojiler | Linkler | Anketler | Silinen | **Mesajlar** |"
    )
    write_line(
        "|-----------|-----------|-------|----------|---------|----------|---------|----------|"
    )
    for stat in user_stats:
        write_line(
            f"| {md_text(stat['User'])} | {format_decimal(stat['AvgLetters'])} | {format_number(stat['Media'])} | {format_number(stat['Emojis'])} | {format_number(stat['Links'])} | {format_number(stat['Polls'])} | {format_number(stat['Deleted'])} | **{format_number(stat['Messages'])}** |"
        )
    write_line("")

    call_stats = []
    for user in [] if is_group_chat else sorted_users:
        user_df = user_messages(user)

        # Only call records count; a message that mentions "sesli arama" is not a call.
        call_df = user_df[user_df["kind"] == whatsapp_chat.CALL]
        msgs = call_df["message"].str.replace("\u200e", "", regex=False)

        # Voice Calls (Initiated)
        voice_calls = count_contains(msgs, "Sesli arama")

        # Video Calls (Initiated)
        video_calls = count_contains(msgs, "Görüntülü arama")

        # Call status is recorded from the export owner's perspective.
        missed_calls = count_contains(msgs, "Cevapsız|Cevaplanmadı", regex=True)

        total_calls = voice_calls + video_calls
        answered_calls = total_calls - missed_calls

        if total_calls > 0:
            call_stats.append(
                {
                    "User": user,
                    "Voice": voice_calls,
                    "Video": video_calls,
                    "Answered": answered_calls,
                    "Missed": missed_calls,
                    "Total": total_calls,
                }
            )

    if call_stats:
        write_subheader("📞 Arama İstatistikleri")
        call_stats.sort(key=lambda x: x["Total"], reverse=True)
        write_line(
            "| Kullanıcı | Sesli Arama | Görüntülü Arama | Cevaplanan | Cevapsız | **Toplam** |"
        )
        write_line(
            "|-----------|-------------|-----------------|------------|----------|--------|"
        )
        for stat in call_stats:
            write_line(
                f"| {md_text(stat['User'])} | {format_number(stat['Voice'])} | {format_number(stat['Video'])} | {format_number(stat['Answered'])} | {format_number(stat['Missed'])} | **{format_number(stat['Total'])}** |"
            )
        write_line("")

    # Create media stats table
    media_stats = []
    for user in sorted_users:
        user_df = user_messages(user)

        # Count different media types using standard case-insensitive matching
        # (Avoids Turkish-specific I/ı issues for these fixed system placeholders)
        msgs_clean = user_df["message"].str.replace("\u200e", "", regex=False)
        media_counts = {
            label: count_contains(msgs_clean, pattern)
            for label, pattern in MEDIA_TYPE_PATTERNS.items()
        }

        media_stats.append(
            {"User": user, **media_counts, "Total Media": sum(media_counts.values())}
        )

    # Sort by total media
    if any(s["Total Media"] > 0 for s in media_stats):
        write_subheader("📱 Detaylı Medya İstatistikleri")
        media_stats.sort(key=lambda x: x["Total Media"], reverse=True)

        write_line(
            "| Kullanıcı | Çıkartmalar | Resimler | Videolar | Sesler | Belgeler | GIFler | Konumlar | **Toplam** |"
        )
        write_line(
            "|-----------|-------------|----------|----------|--------|----------|--------|----------|--------|"
        )
        for stat in media_stats:
            counts = " | ".join(
                format_number(stat[label]) for label in MEDIA_TYPE_PATTERNS
            )
            write_line(
                f"| {md_text(stat['User'])} | {counts} | **{format_number(stat['Total Media'])}** |"
            )
        write_line("")

    # Words and phrases were tokenized once per message in parse_chat.
    word_counts = {user: Counter() for user in sorted_users}
    bigram_counts = {user: Counter() for user in sorted_users}
    trigram_counts = {user: Counter() for user in sorted_users}
    for user, words, phrase_words in zip(df["user"], df["words"], df["phrase_words"]):
        word_counts[user].update(words)
        bigram_counts[user].update(itertools.pairwise(phrase_words))
        trigram_counts[user].update(zip(phrase_words, phrase_words[1:], phrase_words[2:]))

    # Most Used Words
    write_subheader("📝 En Çok Kullanılan Kelimeler (>3 harf)")
    write_line("| Kelime | Sayı |")
    write_line("|--------|------|")
    for word, count in sum(word_counts.values(), Counter()).most_common(50):
        write_line(f"| {md_text(word)} | {format_number(count)} |")
    write_line("")

    # Most Used Word Combinations
    write_subheader("🔗 En Çok Kullanılan Kelime Kombinasyonları")
    _phrase_table(write_line, "İkili Kombinasyonlar", sum(bigram_counts.values(), Counter()), 20)
    _phrase_table(write_line, "Üçlü Kombinasyonlar", sum(trigram_counts.values(), Counter()), 20)

    # Most Used Words by User
    write_subheader("🗣️ Kullanıcılara Göre En Çok Kullanılan Kelimeler")
    for user in sorted_users:
        write_line(f"\n#### {md_text(user)}\n")
        write_line("| Kelime | Sayı |")
        write_line("|--------|------|")
        for word, count in word_counts[user].most_common(20):
            write_line(f"| {md_text(word)} | {format_number(count)} |")
        write_line("")

    # Most Used Word Combinations by User
    write_subheader("🔗 Kullanıcı Bazlı En Çok Kullanılan Kelime Kombinasyonları")
    for user in sorted_users:
        write_line(f"\n#### {md_text(user)}\n")
        _phrase_table(write_line, "İkili Kombinasyonlar", bigram_counts[user], 10)
        _phrase_table(write_line, "Üçlü Kombinasyonlar", trigram_counts[user], 10)

    # Most Used Emojis by User
    emoji_data = {}
    for user in sorted_users:
        user_emojis = Counter()
        for em_list in user_messages(user)["emojis"]:
            user_emojis.update(em_list)
        if user_emojis:
            emoji_data[user] = user_emojis

    if emoji_data:
        write_subheader("😊 Kullanıcılara Göre En Çok Kullanılan Emojiler")
        for user, user_emojis in emoji_data.items():
            write_line(f"\n#### {md_text(user)}\n")
            write_line("| Emoji | Sayı |")
            write_line("|-------|------|")
            for em, cnt in user_emojis.most_common(5):
                write_line(f"| {em} | {format_number(cnt)} |")
            write_line("")

    # Temporal Statistics
    write_subheader("⏰ Zamansal İstatistikler")

    write_line("#### 📅 Haftanın Günlerine Göre Mesajlar")
    days = (
        df["weekday"]
        .map(DAY_NAMES)
        .value_counts()
        .reindex(list(DAY_NAMES.values()), fill_value=0)
    )
    write_line(
        create_chart(
            days.index,
            days.values,
            "Haftanın Günlerine Göre Mesaj Dağılımı",
            "Günler",
            "Mesaj Sayısı",
            "bar",
        )
    )
    write_line("")

    # Messages by Hour
    write_line("#### 🕐 Saatlere Göre Mesajlar")
    hour_stats = df["hour"].value_counts().reindex(range(24), fill_value=0).sort_index()
    write_line(
        create_chart(
            [f"{h:02d}" for h in range(24)],
            hour_stats.values,
            "Saatlere Göre Mesaj Dağılımı",
            "Saat",
            "Mesaj Sayısı",
            "line",
        )
    )
    write_line("")

    # Messages by Month
    write_line("#### 📆 Aylara Göre Mesajlar")
    month_stats = df["month"].value_counts().sort_index()
    month_labels = [
        f"{MONTH_NAMES[int(month[5:7]) - 1]} {month[:4]}" for month in month_stats.index
    ]
    write_line(
        create_chart(
            month_labels,
            month_stats.values,
            "Aylara Göre Mesaj Dağılımı",
            "Ay",
            "Mesaj Sayısı",
            "bar",
        )
    )
    write_line("")

    # Most Active Days
    write_line("#### 🔥 En Aktif 10 Gün")
    write_line("")
    day_stats = df["date"].value_counts()
    # Busiest first; on equal counts, the earlier day first.
    busiest = sorted(day_stats.items(), key=lambda item: (-item[1], item[0]))[:10]
    write_line("| Tarih | Gün | Mesajlar |")
    write_line("|-------|-----|----------|")
    for d, v in busiest:
        weekday = list(DAY_NAMES.values())[d.weekday()]
        write_line(f"| {d:%d.%m.%Y} | {weekday} | {format_number(v)} |")
    write_line("")

    # Users First and Last Message
    write_line("#### 📊 Kullanıcı Etkinlik Zaman Çizelgesi")
    write_line("")
    write_line(f"**Toplam Sohbet Günü: {format_number(total_chat_days)}**")
    write_line("")

    user_timeline = []
    for user in sorted_users:
        user_df = user_messages(user)
        active_days = user_df["date"].nunique()
        user_timeline.append(
            {
                "User": user,
                "Messages": len(user_df),
                "Days Active": active_days,
            }
        )

    user_timeline.sort(key=lambda x: x["Days Active"], reverse=True)
    write_line("| Kullanıcı | Aktif Günler | Katılım Oranı | Aktif Gün Başına Mesaj |")
    write_line("|-----------|--------------|---------------|------------------------|")
    for timeline in user_timeline:
        participation_rate = (timeline["Days Active"] / total_chat_days) * 100
        messages_per_day = timeline["Messages"] / timeline["Days Active"]
        write_line(
            f"| {md_text(timeline['User'])} | {format_number(timeline['Days Active'])} / {format_number(total_chat_days)} | %{format_decimal(participation_rate)} | {format_decimal(messages_per_day)} |"
        )
    write_line("")

    body_markdown = "".join(markdown_content)
    # The Markdown export carries the summary as text; the PDF shows it as cards.
    markdown_text = "# WhatsApp Sohbet İstatistikleri\n\n" + summary_markdown + body_markdown
    html_content = header_html + markdown.markdown(body_markdown, extensions=["tables"])

    full_html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="utf-8">
    <title>WhatsApp Sohbet İstatistikleri</title>
    <style>{REPORT_CSS}</style>
</head>
<body>
{html_content}
</body>
</html>
"""

    # Generate PDF. Both reports go to temporary files first, so a failure
    # never leaves a new Markdown file next to an old PDF.
    temporary_files = []
    try:
        font_config = FontConfiguration()
        pdf_temp = _temporary_sibling(output_file, temporary_files)
        HTML(string=full_html).write_pdf(str(pdf_temp), font_config=font_config)
        if markdown_output:
            # Keep the text export small; charts are available in the PDF.
            text_report = re.sub(
                r"<img\b[^>]*>", "*Grafik PDF raporunda yer alır.*", markdown_text
            )
            markdown_temp = _temporary_sibling(markdown_output, temporary_files)
            markdown_temp.write_text(text_report.rstrip() + "\n", encoding="utf-8")
            os.replace(markdown_temp, markdown_output)
        os.replace(pdf_temp, output_file)
        print(f"PDF report generated: {output_file}")
    except (OSError, ValueError) as e:
        print(f"Error generating PDF: {e}", file=sys.stderr)
        # Fallback: save HTML for debugging
        with open("debug_output.html", "w", encoding="utf-8") as f:
            f.write(full_html)
        print("Debug HTML saved to debug_output.html", file=sys.stderr)
        return False
    finally:
        for path in temporary_files:
            path.unlink(missing_ok=True)
    return True


def _temporary_sibling(path, temporary_files):
    """Create an empty temporary file next to path, so os.replace stays atomic."""
    path = Path(path)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(descriptor)
    temporary_files.append(Path(name))
    return Path(name)


def main():
    parser = argparse.ArgumentParser(description="WhatsApp chat statistics")
    parser.add_argument(
        "chat_file",
        nargs="?",
        default="_chat.txt",
        help="Path to exported chat text file (default: _chat.txt)",
    )
    parser.add_argument(
        "--start-date",
        "-s",
        help="Filter messages from this date/time onwards (Format: DD.MM.YYYY, DD.MM.YYYY HH:MM or DD.MM.YYYY HH:MM:SS)",
        default=None,
    )
    parser.add_argument(
        "--end-date",
        "-e",
        help="Filter messages up to this date/time, inclusive (Format: DD.MM.YYYY for the whole day, DD.MM.YYYY HH:MM or DD.MM.YYYY HH:MM:SS)",
        default=None,
    )
    parser.add_argument(
        "--chat-type",
        choices=["auto", "group", "direct"],
        default="auto",
        help="Chat type: auto-detect (default), group, or direct",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="chat_stats.pdf",
        help="Output PDF path (default: chat_stats.pdf)",
    )
    parser.add_argument(
        "--markdown-output",
        help="Optional text report path (.md); charts remain in the PDF",
    )
    args = parser.parse_args()
    input_path = Path(args.chat_file).resolve()
    output_path = Path(args.output).resolve()
    markdown_path = (
        Path(args.markdown_output).resolve() if args.markdown_output else None
    )
    if input_path == output_path or (
        markdown_path is not None and markdown_path in {input_path, output_path}
    ):
        parser.error("The chat, PDF and Markdown paths must all be different.")

    option = "--start-date"
    try:
        start_dt = parse_start_date(args.start_date) if args.start_date else None
        option = "--end-date"
        end_dt = parse_end_date(args.end_date) if args.end_date else None
    except ValueError as exc:
        print(f"Error: Invalid date format for {option}. {exc}", file=sys.stderr)
        return 1
    if start_dt and end_dt and start_dt > end_dt:
        print("Error: --start-date must not be after --end-date.", file=sys.stderr)
        return 1

    try:
        df = parse_chat(args.chat_file)
    except (OSError, UnicodeError) as exc:
        print(f"Could not read chat file: {args.chat_file}. {exc}", file=sys.stderr)
        return 1

    if df.empty:
        print("No messages found for the given criteria.", file=sys.stderr)
        return 1

    if start_dt:
        df = df[df["datetime"] >= start_dt]
    if end_dt:
        df = df[df["datetime"] <= end_dt]
    if start_dt or end_dt:
        period = " - ".join(
            [args.start_date or "beginning", args.end_date or "end"]
        )
        print(f"Filtered messages for {period}. Remaining records: {len(df)}")

    if df.empty:
        print("No messages found for the given criteria.", file=sys.stderr)
        return 1

    return (
        0
        if compute_stats(
            df,
            chat_type=args.chat_type,
            output_file=args.output,
            markdown_output=args.markdown_output,
        )
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
