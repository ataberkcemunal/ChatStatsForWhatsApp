import argparse
import base64
import io
import logging
import itertools
import math
import os
import re
import sys
import tempfile
import unicodedata
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import emoji
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (the backend must be chosen first)
from matplotlib.ticker import MaxNLocator  # noqa: E402
import pandas as pd
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

import report_style
import whatsapp_chat
from whatsapp_chat import turkish_lower

# Charts use the same typeface as the report text where available.
plt.rcParams["font.family"] = ["Helvetica Neue", "Arial", "DejaVu Sans"]
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)


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


# Written laughter: haha, ahaha, hehe, hihi, hohoho, ohhohoh, ksksks, sjsjsj, jsjs, za, zaaa, zazaza,
# asdf..., xd, lol, plus :D, :DD, :) and the laughing emojis.
LAUGH_REGEX = re.compile(
    r"(?<!\w)(?:a?(?:h+a+){2,}h*|o?(?:h+o+){2,}h*|(?:h+e+){2,}h*|(?:h+i+){2,}h*|(?:ks){2,}k?|(?:sj){2,}s?|(?:js){2,}j?"
    r"|(?:z+a+)+|asd\w*|x+d+|lo+l+|lmao+)(?!\w)|:d+(?!\w)|:\)|[\U0001F602\U0001F923\U0001F639]"
)


# Questions without a question mark. Vowels are not harmony-checked, so ASCII typing (misin for mısın)
# also counts. The particle counts as a separate word in any form (mi, mısın, miydi) and attached only
# with a personal or tense ending (gelcekmisin), since a bare attached -mi is usually an accusative
# (evimi, adamı).
_V = "[iıuü]"
_QUESTION_SUFFIX = rf"(?:y{_V}[mz]|s{_V}n(?:{_V}z)?|yd{_V}(?:[mnk]|n{_V}z)?|ym{_V}[şs](?:{_V}m|s{_V}n|{_V}z)?)"
QUESTION_REGEX = re.compile(
    rf"(?<!\w)m{_V}{_QUESTION_SUFFIX}?(?!\w)|(?<=\w)m{_V}{_QUESTION_SUFFIX}(?!\w)"
    r"|(?<!\w)(?:nas[ıi]l(?!sa(?!\w))\w*|neden|niye|ni[çc]in|ka[çc](?:ta|tan|[ıi]|[ıi]nc[ıi])?|hangi\w*"
    r"|nere\w*|nerde\w*|nerden\w*|kim(?:in|e|den|le|ler|sin|di|mi[şs])?)(?!\w)"
)
# "ne" counts only as a whole message (ne, neee), since inside a sentence it is often not a question.
ONLY_NE_REGEX = re.compile(r"n+e+[\s!.]*")
# Phrases built on question words that are not questions: neredeyse (almost), neden olmak
# (to cause), hangisi/kim/ne olursa olsun (whichever/whoever/whatever).
NOT_QUESTION_REGEX = re.compile(
    r"(?<!\w)(?:nere?deyse|neden\s+ol\w*|(?:hangi\w*|kim\w*|ne)(?:\s+\w+)?\s+olursa\s+olsun)(?!\w)"
)
# Links written without http (x.com/?a=1): their ? is not a question mark.
BARE_LINK_REGEX = re.compile(r"(?<!\w)(?:www\.)?[\w-]+(?:\.[\w-]+)+/\S*")


def style_flags(written):
    """Whether someone asked a question or laughed, once per message (links left out)."""
    text = BARE_LINK_REGEX.sub("", re.sub(LINK_REGEX, "", written))
    lower = turkish_lower(text)
    asked = NOT_QUESTION_REGEX.sub(" ", lower)
    question = "?" in text or QUESTION_REGEX.search(asked) or ONLY_NE_REGEX.fullmatch(lower.strip())
    return {
        "question": int(bool(question)),
        "laugh": int(bool(LAUGH_REGEX.search(lower))),
    }


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
        **style_flags(written),
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
DAY_SHORT = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
MONTH_NAMES = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
MEDIA_LABELS = {
    "Stickers": "Çıkartma",
    "Images": "Görsel",
    "Videos": "Video",
    "Audio": "Ses",
    "Documents": "Belge",
    "GIFs": "GIF",
    "Locations": "Konum",
}


def create_chart(labels, values, *, kind="bar", size=(5.4, 2.9)):
    """Draw a small chart as an SVG data URI in the reports' accent colour."""
    fig, ax = plt.subplots(figsize=size)
    if kind == "bar":
        ax.bar(labels, values, color=report_style.ACCENT, width=0.7 if len(labels) > 3 else 0.4)
    else:
        ax.plot(labels, values, marker="o", markersize=3, linewidth=1.6, color=report_style.ACCENT)
        ax.fill_between(range(len(labels)), values, color=report_style.ACCENT, alpha=0.08)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(True, axis="y", color="#e2e8f0", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#94a3b8")
    ax.tick_params(colors="#475569", labelsize=8, length=0)
    if len(labels) > 8:
        ax.tick_params(axis="x", labelrotation=90 if kind == "line" else 45)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="svg", transparent=True)
    plt.close(fig)
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


# Colours for people in the share chart; the most active person gets the accent.
PERSON_COLOURS = [report_style.ACCENT, "#f59e0b", "#6366f1", "#e11d48", "#0ea5e9"]
OTHERS_COLOUR = "#cbd5e1"


def monthly_shares(df, users, limit=len(PERSON_COLOURS)):
    """Each month's message share per person in percent; people after ``limit`` become "Diğer"."""
    table = pd.crosstab(df["month"], df["user"]).reindex(columns=users, fill_value=0)
    shares = table.div(table.sum(axis=1), axis=0) * 100
    if len(users) > limit:
        others = shares[users[limit:]].sum(axis=1)
        shares = shares[users[:limit]].assign(Diğer=others)
    return shares


def share_chart(labels, shares, size=(10.8, 3.2)):
    """Stacked 100% bars of monthly shares as an SVG data URI, with a legend on top."""
    fig, ax = plt.subplots(figsize=size)
    bottom = [0.0] * len(labels)
    for index, name in enumerate(shares.columns):
        colour = PERSON_COLOURS[index] if index < len(PERSON_COLOURS) else OTHERS_COLOUR
        values = shares[name].tolist()
        ax.bar(labels, values, bottom=bottom, color=colour, label=name,
               width=0.7 if len(labels) > 3 else 0.4)
        bottom = [b + v for b, v in zip(bottom, values)]
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(lambda value, _: f"%{value:.0f}")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#94a3b8")
    ax.tick_params(colors="#475569", labelsize=8, length=0)
    if len(labels) > 8:
        ax.tick_params(axis="x", labelrotation=45)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=len(shares.columns),
              frameon=False, fontsize=8, labelcolor="#475569")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="svg", transparent=True)
    plt.close(fig)
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


# How many entries each list shows; the same for every person.
TOP_WORDS = 45  # three columns of 15
TOP_PHRASES = 15
TOP_PER_PERSON = 15
TOP_DISTINCTIVE = 10
TOP_EMOJIS = 10


def _top(counter, limit):
    return [[" ".join(item) if isinstance(item, tuple) else item, report_style.number(count)]
            for item, count in counter.most_common(limit)]


def distinctive_words(word_counts, user, limit=TOP_DISTINCTIVE):
    """Words this person uses clearly more often than everyone else.

    Weighted log-odds with the whole chat as an informative Dirichlet prior
    (Monroe, Colaresi & Quinn, 2008): each word gets a z-score, and only words
    above 1.96 (about 95% confidence) are kept, highest first.
    """
    mine = word_counts[user]
    others = sum((counts for name, counts in word_counts.items() if name != user), Counter())
    prior = mine + others
    n_mine, n_others, n_prior = mine.total(), others.total(), prior.total()
    if not n_mine or not n_others:
        return []
    scores = []
    for word, count in mine.items():
        alpha, other = prior[word], others[word]
        rest_mine, rest_others = n_mine + n_prior - count - alpha, n_others + n_prior - other - alpha
        if rest_mine <= 0 or rest_others <= 0:
            continue  # the only word anyone used: nothing to compare against
        delta = math.log((count + alpha) / rest_mine) - math.log((other + alpha) / rest_others)
        z = delta / math.sqrt(1 / (count + alpha) + 1 / (other + alpha))
        if z > 1.96:
            scores.append((-z, -count, word))
    return [word for _, _, word in sorted(scores)[:limit]]


def day_streaks(dates):
    """Return the longest run of days with records and the longest run without.

    Each is ``(days, first_day, last_day)``; the silence is ``None`` when no
    calendar day between the first and the last record is empty.
    """
    days = sorted(set(dates))
    streak = silence = None
    run_start = days[0]
    for previous, day in zip(days, [*days[1:], None]):
        if day is not None and (day - previous).days == 1:
            continue
        run = ((previous - run_start).days + 1, run_start, previous)
        if streak is None or run[0] > streak[0]:
            streak = run
        if day is not None:
            gap = ((day - previous).days - 1, previous + timedelta(days=1), day - timedelta(days=1))
            if silence is None or gap[0] > silence[0]:
                silence = gap
            run_start = day
    return streak, silence


# Hours of silence that end one conversation; the next record opens a new one.
CONVERSATION_GAP_HOURS = 1.0


def conversation_stats(df, gap_hours=CONVERSATION_GAP_HOURS):
    """Count who opens and closes conversations, and who replies to whom.

    A reply is a record whose sender differs from the previous record's sender
    within the same conversation.
    """
    ordered = df.sort_values("datetime", kind="stable")
    silence = ordered["datetime"].diff()
    starts = silence.isna() | (silence >= pd.Timedelta(hours=gap_hours))
    ends = starts.shift(-1, fill_value=True)
    replies = ~starts & (ordered["user"] != ordered["user"].shift())
    pairs = Counter(zip(ordered["user"].shift()[replies], ordered.loc[replies, "user"]))
    return {
        "pairs": pairs,
        "conversations": int(starts.sum()),
        "starts": ordered.loc[starts, "user"].value_counts(),
        "ends": ordered.loc[ends, "user"].value_counts(),
    }


# Compute and print statistics
def compute_stats(
    df, *, chat_type="auto", output_file="chat_stats.pdf", markdown_output=None, source_name=None,
    conversation_gap=CONVERSATION_GAP_HOURS, min_messages=1, excluded_senders=(),
):
    number, decimal, percent = report_style.number, report_style.decimal, report_style.percent
    is_group_chat = (
        df.attrs.get("is_group_chat", df["user"].nunique() > 2)
        if chat_type == "auto"
        else chat_type == "group"
    )

    def user_messages(user):
        return df[df["user"] == user]

    def count_contains(series, pattern, regex=False):
        return series.str.contains(pattern, case=False, na=False, regex=regex).sum()

    first, last = df["datetime"].min(), df["datetime"].max()
    total_chat_days = df["date"].nunique()
    streak, silence = day_streaks(df["date"])
    meta = [f"Kaynak: {source_name}"] if source_name else []
    meta += [
        f"{report_style.date_time(first)} – {report_style.date_time(last)}",
        "Grup sohbeti" if is_group_chat else "Birebir sohbet",
    ]
    report = report_style.Report(
        "Sohbet İstatistikleri",
        meta,
        [
            ("Mesaj", number(len(df))),
            ("Katılımcı", number(df["user"].nunique())),
            ("Sohbet günü", number(total_chat_days)),
            ("Günde ortalama mesaj", decimal(len(df) / total_chat_days)),
            ("En uzun seri", f"{number(streak[0])} gün"),
            ("En uzun sessizlik", f"{number(silence[0])} gün" if silence else "–"),
        ],
    )
    def span(run):
        return f"{run[1]:%d.%m.%Y} – {run[2]:%d.%m.%Y}"

    report.paragraph(
        f"En uzun seri: her gün yazışılan {span(streak)}"
        + (f" · En uzun sessizlik: hiç yazışılmayan {span(silence)}" if silence else ""),
        "note",
    )

    # People
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
                "Days Active": user_df["date"].nunique(),
                "Written": written,
            }
        )
    user_stats.sort(key=lambda x: x["Messages"], reverse=True)
    sorted_users = [s["User"] for s in user_stats]
    stats_by_user = {s["User"]: s for s in user_stats}

    report.section("Kişiler")
    report.table(
        ["Kişi", "Mesaj", "Pay", "Ort. harf", "Medya", "Emoji", "Link", "Anket", "Silinen"],
        [
            [
                s["User"], number(s["Messages"]), percent(100 * s["Messages"] / len(df)),
                decimal(s["AvgLetters"]), number(s["Media"]), number(s["Emojis"]),
                number(s["Links"]), number(s["Polls"]), number(s["Deleted"]),
            ]
            for s in user_stats
        ],
        numeric=range(1, 9),
        bar_column=1,
        bar_values=[s["Messages"] for s in user_stats],
        total=[
            "Toplam", number(len(df)), "", "", number(df["media"].sum()),
            number(df["emoji_count"].sum()), number(df["links"].sum()),
            number(df["poll"].sum()), number(df["deleted"].sum()),
        ],
    )
    report.paragraph(
        "Ort. harf: yazılı mesaj başına boşluksuz karakter; medya, arama ve silinen mesajlar sayılmaz.",
        "note",
    )
    if excluded_senders:
        report.paragraph(
            f"{number(min_messages)} mesajın altında kalan {number(len(excluded_senders))} kişi "
            f"rapora dahil edilmedi: {', '.join(excluded_senders)}",
            "note",
        )

    # Media
    media_stats = []
    for user in sorted_users:
        # Count different media types using standard case-insensitive matching
        # (Avoids Turkish-specific I/ı issues for these fixed system placeholders)
        msgs_clean = user_messages(user)["message"].str.replace("\u200e", "", regex=False)
        counts = [count_contains(msgs_clean, pattern) for pattern in MEDIA_TYPE_PATTERNS.values()]
        media_stats.append((user, counts))
    if any(sum(counts) for _, counts in media_stats):
        media_stats.sort(key=lambda item: sum(item[1]), reverse=True)
        column_totals = [sum(column) for column in zip(*(counts for _, counts in media_stats))]
        report.table(
            ["Kişi", *MEDIA_LABELS.values(), "Toplam"],
            [[user, *map(number, counts), number(sum(counts))] for user, counts in media_stats],
            numeric=range(1, len(MEDIA_LABELS) + 2),
            title="Medya",
            total=["Toplam", *map(number, column_totals), number(sum(column_totals))],
        )

    by_days = sorted(user_stats, key=lambda x: x["Days Active"], reverse=True)
    report.table(
        ["Kişi", "Aktif gün", "Katılım", "Aktif gün başına mesaj"],
        [
            [
                s["User"], f"{number(s['Days Active'])} / {number(total_chat_days)}",
                percent(100 * s["Days Active"] / total_chat_days),
                decimal(s["Messages"] / s["Days Active"]),
            ]
            for s in by_days
        ],
        numeric=range(1, 4),
        title="Etkinlik",
    )

    written_df = df[df["has_text"] == 1]
    style = written_df.groupby("user")[["question", "laugh"]].sum()
    styled_users = [user for user in sorted_users if user in style.index]

    def count_and_share(count, written):
        return [number(int(count)), percent(100 * count / written)]

    if styled_users:
        report.table(
            ["Kişi", "Yazılı mesaj", "Soru", "Soru oranı", "Gülme", "Gülme oranı"],
            [
                [user, number(stats_by_user[user]["Written"]),
                 *count_and_share(style.at[user, "question"], stats_by_user[user]["Written"]),
                 *count_and_share(style.at[user, "laugh"], stats_by_user[user]["Written"])]
                for user in styled_users
            ],
            numeric=range(1, 6),
            title="Üslup",
            total=["Toplam", number(len(written_df)),
                   *count_and_share(written_df["question"].sum(), len(written_df)),
                   *count_and_share(written_df["laugh"].sum(), len(written_df))],
        )
        report.paragraph(
            "Soru: soru işareti, mi/mı/mu/mü soru eki (gelcekmisin gibi bitişik de) ya da nasıl, neden, niye, "
            "niçin, kaç, hangi, nerede, kim gibi bir soru kelimesi içeren ya da yalnızca \"ne\" olan yazılı mesaj; "
            "\"???\" gibi birden çok işaret ya da ifade de bir soru sayılır. "
            "Gülme: haha, hehe, hohoho, ksksks, sjsj, zaaa, asdf, xd, :D, :) gibi bir ifade ya da 😂 🤣 içeren mesaj. "
            "Oranlar yazılı mesajlara göredir.",
            "note",
        )

    flow = conversation_stats(df, conversation_gap)
    flow_rows = sorted(
        sorted_users, key=lambda user: flow["starts"].get(user, 0), reverse=True
    )
    report.table(
        ["Kişi", "Başlattığı sohbet", "Pay", "Son söz"],
        [
            [
                user, number(flow["starts"].get(user, 0)),
                percent(100 * flow["starts"].get(user, 0) / flow["conversations"]),
                number(flow["ends"].get(user, 0)),
            ]
            for user in flow_rows
        ],
        numeric=range(1, 4),
        title="Sohbet akışı",
        bar_column=1,
        bar_values=[flow["starts"].get(user, 0) for user in flow_rows],
        total=[
            "Toplam", number(flow["conversations"]), "", number(flow["conversations"]),
        ],
    )
    gap_hours = f"{conversation_gap:g}".replace(".", ",")
    report.paragraph(
        f"En az {gap_hours} saatlik sessizlikten sonraki ilk mesaj yeni bir sohbet başlatır; "
        "sessizlikten önceki son mesaj son sözdür.",
        "note",
    )

    if is_group_chat and len(sorted_users) > 2:
        given = {user: Counter() for user in sorted_users}
        received = {user: Counter() for user in sorted_users}
        for (previous, user), count in flow["pairs"].items():
            given[user][previous] += count
            received[previous][user] += count

        def favourite(counter):
            if not counter:
                return ["–", ""]
            name, count = counter.most_common(1)[0]
            return [name, percent(100 * count / counter.total())]

        report.table(
            ["Kişi", "En çok yanıt verdiği", "Pay", "En çok yanıt aldığı", "Pay"],
            [[user, *favourite(given[user]), *favourite(received[user])] for user in sorted_users],
            numeric=[2, 4],
            title="Kim kime yanıt veriyor",
        )
        report.paragraph(
            "Yanıt, aynı sohbette sözün bir kişiden diğerine geçmesidir; dışa aktarım kimin kime "
            "cevap verdiğini içermediği için bir önceki mesajın sahibi esas alınır. Pay: kişinin "
            "verdiği ya da aldığı yanıtlar içinde o kişinin payı.",
            "note",
        )

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
        if total_calls > 0:
            call_stats.append([user, voice_calls, video_calls, total_calls - missed_calls, missed_calls, total_calls])

    if call_stats:
        report.section("Aramalar")
        call_stats.sort(key=lambda x: x[-1], reverse=True)
        report.table(
            ["Kişi", "Sesli", "Görüntülü", "Cevaplanan", "Cevapsız", "Toplam"],
            [[row[0], *map(number, row[1:])] for row in call_stats],
            numeric=range(1, 6),
        )

    # Time
    report.section("Zaman")
    days = (
        df["weekday"]
        .map(DAY_NAMES)
        .value_counts()
        .reindex(list(DAY_NAMES.values()), fill_value=0)
    )
    hours = df["hour"].value_counts().reindex(range(24), fill_value=0).sort_index()
    with report.grid(2):
        report.chart_block(
            "Haftanın günlerine göre", create_chart(DAY_SHORT, days.values)
        )
        report.chart_block(
            "Saatlere göre",
            create_chart([f"{h:02d}" for h in range(24)], hours.values, kind="line"),
        )
    month_stats = df["month"].value_counts().sort_index()
    if len(month_stats) > 1:
        month_labels = [
            f"{MONTH_NAMES[int(month[5:7]) - 1]} {month[2:4]}" for month in month_stats.index
        ]
        report.chart_block(
            "Aylara göre", create_chart(month_labels, month_stats.values, size=(10.8, 2.9))
        )
        if len(sorted_users) > 1:
            report.chart_block(
                "Aylara göre mesaj payı",
                share_chart(month_labels, monthly_shares(df, sorted_users)),
            )

    # Words and phrases were tokenized once per message in parse_chat.
    word_counts = {user: Counter() for user in sorted_users}
    bigram_counts = {user: Counter() for user in sorted_users}
    trigram_counts = {user: Counter() for user in sorted_users}
    for user, words, phrase_words in zip(df["user"], df["words"], df["phrase_words"]):
        word_counts[user].update(words)
        bigram_counts[user].update(itertools.pairwise(phrase_words))
        trigram_counts[user].update(zip(phrase_words, phrase_words[1:], phrase_words[2:]))
    all_words = sum(word_counts.values(), Counter())

    report.section("Kelimeler ve ifadeler")
    report.term_list(
        ["Kelime", "Sayı"], _top(all_words, TOP_WORDS), title="En sık kelimeler (4+ harf)",
        more=max(0, len(all_words) - TOP_WORDS),
    )
    with report.grid(2):
        report.table(["İfade", "Sayı"], _top(sum(bigram_counts.values(), Counter()), TOP_PHRASES),
                     numeric=[1], title="İkili ifadeler")
        report.table(["İfade", "Sayı"], _top(sum(trigram_counts.values(), Counter()), TOP_PHRASES),
                     numeric=[1], title="Üçlü ifadeler")

    report.section("Kişi bazında kelimeler")
    for user in sorted_users:
        stat = stats_by_user[user]
        details = [
            f"{number(stat['Messages'])} mesaj",
            f"{percent(100 * stat['Messages'] / len(df))} pay",
            f"{number(stat['Days Active'])} aktif gün",
        ]
        with report.person(user, details), report.grid(3):
            report.table(["Kelime", "Sayı"], _top(word_counts[user], TOP_PER_PERSON), numeric=[1])
            report.table(["İkili ifade", "Sayı"], _top(bigram_counts[user], TOP_PER_PERSON), numeric=[1])
            report.table(["Üçlü ifade", "Sayı"], _top(trigram_counts[user], TOP_PER_PERSON), numeric=[1])

    distinctive = {user: distinctive_words(word_counts, user) for user in sorted_users}
    if any(distinctive.values()):
        report.section("Kendine özgü kelimeler")
        report.paragraph(
            "Kişinin sohbetin geri kalanından belirgin biçimde daha sık kullandığı kelimeler "
            "(ağırlıklı log-odds, z > 1,96); en belirgini üstte.",
            "note",
        )
        with report.grid(3):
            for user, words in distinctive.items():
                if words:
                    report.table(
                        ["Kelime", "Kendisi", "Diğerleri"],
                        [[word, number(word_counts[user][word]),
                          number(all_words[word] - word_counts[user][word])] for word in words],
                        numeric=[1, 2],
                        title=user,
                    )

    # Emojis
    emoji_data = {}
    for user in sorted_users:
        user_emojis = Counter()
        for em_list in user_messages(user)["emojis"]:
            user_emojis.update(em_list)
        if user_emojis:
            emoji_data[user] = user_emojis
    if emoji_data:
        report.section("Emojiler")
        with report.grid(3):
            for user, user_emojis in emoji_data.items():
                report.table(["Emoji", "Sayı"], _top(user_emojis, TOP_EMOJIS), numeric=[1], title=user,
                             css_class="emoji")

    full_html = report.html()
    markdown_text = report.markdown()

    # Generate PDF. Both reports go to temporary files first, so a failure
    # never leaves a new Markdown file next to an old PDF.
    temporary_files = []
    try:
        font_config = FontConfiguration()
        pdf_temp = _temporary_sibling(output_file, temporary_files)
        HTML(string=full_html).write_pdf(str(pdf_temp), font_config=font_config)
        if markdown_output:
            markdown_temp = _temporary_sibling(markdown_output, temporary_files)
            markdown_temp.write_text(markdown_text, encoding="utf-8")
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


def positive_hours(value):
    try:
        hours = float(value.replace(",", "."))
    except ValueError:
        hours = 0
    if not 0 < hours < float("inf"):
        raise argparse.ArgumentTypeError("use a positive number of hours, e.g. 3 or 1.5")
    return hours


def positive_count(value):
    try:
        count = int(value)
    except ValueError:
        count = 0
    if count < 1:
        raise argparse.ArgumentTypeError("use a whole number of at least 1")
    return count


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
        "--conversation-gap",
        type=positive_hours,
        default=CONVERSATION_GAP_HOURS,
        metavar="HOURS",
        help="Hours of silence that start a new conversation (default: 3)",
    )
    parser.add_argument(
        "--min-messages",
        type=positive_count,
        default=1,
        metavar="N",
        help="Only include people with at least N records in the period (default: 1, everyone)",
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

    # The threshold applies after the date filter; the chat type was decided on the whole file.
    counts = df["user"].value_counts()
    excluded_senders = sorted(counts[counts < args.min_messages].index)
    if excluded_senders:
        df = df[~df["user"].isin(excluded_senders)]
        print(f"Left out {len(excluded_senders)} people with fewer than {args.min_messages} records.")
    if df.empty:
        print(f"Nobody has at least {args.min_messages} records in this period.", file=sys.stderr)
        return 1

    return (
        0
        if compute_stats(
            df,
            chat_type=args.chat_type,
            conversation_gap=args.conversation_gap,
            min_messages=args.min_messages,
            excluded_senders=excluded_senders,
            output_file=args.output,
            markdown_output=args.markdown_output,
            source_name=Path(args.chat_file).name,
        )
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
