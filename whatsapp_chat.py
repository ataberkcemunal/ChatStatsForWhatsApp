"""Read Turkish WhatsApp chat exports into classified records.

The copy in Chat Stats is the original. Other local projects may carry a
copy; ``Tools/sync_shared.sh`` in the parent folder updates them.
Uses only the standard library.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path

MESSAGE = "message"
DELETED = "deleted"
CALL = "call"
SYSTEM = "system"
EXCLUDED = "excluded"

HEADER = re.compile(
    r"^\[(\d{1,2}\.\d{1,2}\.\d{4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?)\]\s+(.*?):(?:\s(.*))?$"
)
# A timestamped line without "sender:" is a system line; it ends the previous message.
TIMESTAMP_PREFIX = re.compile(r"^\[\d{1,2}\.\d{1,2}\.\d{4},?\s+\d{1,2}:\d{2}(?::\d{2})?\]")
LINE_PREFIX_CHARS = "".join(chr(i) for i in range(32)) + "\u200e\u200f"
EXCLUDED_SENDERS = {"siz", "meta ai"}
EDIT_MARKER = re.compile(r"<[^<>]*(?:mesaj düzenlendi|message was edited)>", re.IGNORECASE)
DELETED_TEXT = re.compile(
    r"^(?:bu mesaj silindi|bu mesajı sildiniz|this message was deleted)\.?$"
)
CALL_TEXT = re.compile(r"^(?:cevapsız\s+)?(?:sesli|görüntülü)\s+arama\s*(?:$|[,.•·])")
GROUP_SENDER_WORDS = ("grup", "whatsapp", "sistem", "bildirim", "güncelleme")

# System notices that can appear without WhatsApp's invisible marker.
UNMARKED_SYSTEM = [
    r"grubun adını değiştirdi",
    r"grup adını değiştirdi",
    r"grubun simgesini değiştirdi",
    r"grup simgesini değiştirdi",
    r"grubun açıklamasını değiştirdi",
    r"grup açıklamasını değiştirdi",
    r"grubun konusunu değiştirdi",
    r"grup konusunu değiştirdi",
    r"bu grubun simgesini",
    r"bu grubun adını",
    r"gelişmiş sohbet gizliliğini etkinleştirdi",
    r"gelişmiş sohbet gizliliğini devre dışı bıraktı",
    r"medya dosyalarını otomatik olarak kaydedemez",
    r"okunmamış mesajları özetleyemez",
    r'adını [“"](.*?)[”"] olarak değiştirdi',
]
# Notices that only count as system text when WhatsApp marked the line (U+200E/U+200F).
MARKED_SYSTEM = [
    r"grubunu oluştur",
    r"grubu oluştur",
    r"^bu grubu siz oluşturdunuz[.!]?$",
    r"gruba katıldı",
    r"gruptan ayrıldı",
    r"grubun (?:adını|simgesini|açıklamasını)",
    r"grup (?:adını|ayarlarını|açıklamasını|fotoğrafını|bağlantısını)",
    r"sistem mesajı",
    r"grup mesajı",
    r"grup bildirimi",
    r"grup güncellemesi",
    r"uçtan uca şifre",
    r"bir mesajı sabitledi",
    r"sizi ekledi",
    r"artık yöneticisiniz",
    r"tarafından okunabilir",
    r"kişisini (?:ekledi|çıkardı)",
    r"güvenlik kodu değişti",
    r"gelişmiş sohbet gizliliğini",
]
GROUP_EVENT = re.compile(
    r"grubunu oluştur|grubu oluştur|^bu grubu siz oluşturdunuz[.!]?$|gruba katıldı|gruptan ayrıldı|"
    r"grubun (?:adını|simgesini|açıklamasını)|grup (?:adını|ayarlarını)"
)
GROUP_NAME_PATTERNS = [
    r'[“"](.*?)[”"] grubunu oluşturdu',
    r'grubunun konusunu [“"](.*?)[”"] olarak değiştirdi',
    r'grup adını [“"](.*?)[”"] olarak değiştirdi',
]
GROUP_NAME_HINTS = ("tayfa", "grup", "ekip", "kulüp", "dernek")


@dataclass(frozen=True)
class Record:
    timestamp: datetime
    sender: str
    text: str
    kind: str


@dataclass
class Chat:
    records: list[Record]
    is_group_chat: bool


def turkish_lower(text: str) -> str:
    if not text:
        return ""
    return text.replace("İ", "i").replace("I", "ı").lower()


def clean_sender(sender: str) -> str:
    """A name as one form: invisible marks removed, any kind of space (a no-break space
    too) made one plain space, and letters in one Unicode form, so the same name written
    by a header and by an @ tag matches."""
    name = unicodedata.normalize("NFC", sender)
    name = "".join(c for c in name if not unicodedata.category(c).startswith("C") or c.isspace())
    return " ".join(name.split())


def is_excluded_sender(sender: str) -> bool:
    return turkish_lower(clean_sender(sender)).replace("ı", "i") in EXCLUDED_SENDERS


def _plain_text(text: str) -> str:
    text = EDIT_MARKER.sub(" ", text.replace("\u200e", "").replace("\u200f", ""))
    return turkish_lower(" ".join(text.split()))


def _is_system(sender: str, text: str, plain: str, marked: bool) -> bool:
    if any(word in turkish_lower(sender) for word in GROUP_SENDER_WORDS):
        return True
    # Polls can look like notices; keep them.
    if re.search(r"(?:^|\s|\u200e)ANKET:", text, re.IGNORECASE):
        return False
    if any(re.search(pattern, plain) for pattern in UNMARKED_SYSTEM):
        return True
    if not marked:
        return False
    if any(re.search(pattern, plain) for pattern in MARKED_SYSTEM):
        return True
    # A marked short line that looks like a group name rather than a message.
    stripped = text.strip("\u200e\u200f \t\r\n")
    if len(stripped) < 50:
        if stripped.isupper() and len(stripped) > 3:
            return True
        if any(hint in plain for hint in GROUP_NAME_HINTS):
            return True
    return False


def classify(sender: str, text: str, marked: bool | None = None) -> str:
    """Return MESSAGE, DELETED, CALL, SYSTEM or EXCLUDED for one record.

    ``marked`` says whether WhatsApp's invisible U+200E/U+200F marker was on the
    record's header line; when omitted it is read from the text.
    """
    if marked is None:
        marked = "\u200e" in text or "\u200f" in text
    if is_excluded_sender(sender):
        # Calls the exporter made from another device ("Siz: Görüntülü arama, Başka bir
        # cihazda cevaplandı") are written as "Siz"; they are real calls.
        if turkish_lower(clean_sender(sender)) == "siz" and CALL_TEXT.match(_plain_text(text.split("\n", 1)[0])):
            return CALL
        return EXCLUDED
    if not _plain_text(text):
        return SYSTEM
    # Notices are single lines; anything after the first line is unrelated text.
    first_line = text.split("\n", 1)[0]
    plain = _plain_text(first_line)
    if DELETED_TEXT.match(plain):
        return DELETED
    if CALL_TEXT.match(plain):
        return CALL
    if _is_system(sender, first_line, plain, marked):
        return SYSTEM
    return MESSAGE


def parse_timestamp(date: str, time: str) -> datetime:
    fmt = "%d.%m.%Y %H:%M:%S" if time.count(":") == 2 else "%d.%m.%Y %H:%M"
    return datetime.strptime(f"{date} {time}", fmt)


# An export runs forward in time. A header more than this much older than the
# newest record so far was pasted into a message (a quoted chat) and is text.
PASTED_HEADER_AGE = timedelta(days=1)


def _raw_records(path):
    """Yield (timestamp, sender, marked, text) for each "[time] sender: text" record."""
    current = None
    lines: list[str] = []
    newest = None
    with Path(path).open(encoding="utf-8-sig") as stream:
        for raw in stream:
            line = raw.rstrip("\r\n")
            # Keep leading spaces: pasted chat lines often start with one and
            # belong to the previous message.
            stripped = line.lstrip(LINE_PREFIX_CHARS)
            header = HEADER.match(stripped)
            timestamp = parse_timestamp(header[1], header[2]) if header else None
            if timestamp and newest and timestamp < newest - PASTED_HEADER_AGE:
                if current is not None:
                    lines.append(line)
                continue
            if header or TIMESTAMP_PREFIX.match(stripped):
                if current is not None:
                    yield (*current, "\n".join(lines))
                current, lines = None, []
                if header:
                    marked = "\u200e" in line or "\u200f" in line
                    current = (timestamp, header[3], marked)
                    lines = [header[4] or ""]
                    newest = max(newest, timestamp) if newest else timestamp
            elif current is not None:
                lines.append(line)
    if current is not None:
        yield (*current, "\n".join(lines))


def exporter_name(records):
    """The exporting person's name, or None: only their own deleted messages read
    "Bu mesajı sildiniz" (others' read "Bu mesaj silindi")."""
    names = Counter(record.sender for record in records
                    if record.kind == DELETED and "sildiniz" in turkish_lower(_plain_text(record.text)))
    return names.most_common(1)[0][0] if names else None


def read_chat(path) -> Chat:
    """Read an export; system notices and "Siz"/"Meta AI" records are left out,
    except calls the exporter made from another device. Those are written as "Siz" and
    are given the exporter's name when the chat shows it, else they keep "Siz"."""
    records = []
    group_names = set()
    has_group_event = False
    for timestamp, sender, marked, text in _raw_records(path):
        if marked and GROUP_EVENT.search(_plain_text(text.split("\n", 1)[0])):
            has_group_event = True
        for pattern in GROUP_NAME_PATTERNS:
            match = re.search(pattern, text.replace("\u200e", ""), re.IGNORECASE)
            if match:
                group_names.add(match[1])
        sender = clean_sender(sender)
        kind = classify(sender, text, marked)
        if kind not in (SYSTEM, EXCLUDED):
            records.append(Record(timestamp, sender, text, kind))
    # Some exports attribute notices to the group's own name.
    records = [record for record in records if record.sender not in group_names]
    me = exporter_name(records)
    if me:
        records = [replace(record, sender=me) if record.kind == CALL and turkish_lower(record.sender) == "siz"
                   else record for record in records]
    # Calls do not decide who takes part: "Siz" only ever appears on calls.
    senders = {record.sender for record in records if record.kind != CALL}
    return Chat(records, bool(has_group_event or group_names or len(senders) > 2))
