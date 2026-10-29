import argparse
import base64
import io
import logging
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
    "Locations": "konum: https://maps.google.com",
}
# WhatsApp's own location share; its map link is part of the share, not a shared link.
LOCATION_REGEX = re.compile(r"konum:\s*https://maps\.google\.com/\S*", re.IGNORECASE)

# Regex for links, tags and system indicators (edited/deleted)
LINK_REGEX = r"https?://\S+"
# Links typed without http: www.…, a domain with a path (x.com/…), or a bare domain
# with a common ending (google.com). Ratings such as 3.5/10 are not links.
BARE_LINK_REGEX = re.compile(
    r"(?<![\w@])(?:www\.\S+|[\w-]+(?:\.[\w-]+)*\.[a-zA-Z]{2,}/\S*"
    r"|[\w-]+(?:\.[\w-]+)*\.(?:com|net|org|io|co|me|ly|be|tv|app|dev|gg|ai|tr)(?![\w.]))"
)


def strip_links(text):
    return BARE_LINK_REGEX.sub(" ", re.sub(LINK_REGEX, " ", text))


# Second-level endings under a country code: example.com.tr is one site, not com.tr.
SECOND_LEVEL = {"com", "co", "org", "net", "gov", "edu", "gen", "web", "bel", "k12", "av", "ac"}
# One name per site where it has several addresses.
SITE_ALIASES = {
    "youtu.be": "youtube.com", "twitter.com": "x.com", "fxtwitter.com": "x.com",
    "vxtwitter.com": "x.com", "fixupx.com": "x.com", "t.co": "x.com", "instagr.am": "instagram.com",
    "t.me": "telegram.org", "wa.me": "whatsapp.com", "fb.com": "facebook.com", "fb.watch": "facebook.com",
    "redd.it": "reddit.com", "amzn.to": "amazon.com", "amzn.eu": "amazon.com", "spoti.fi": "spotify.com",
    "apple.co": "apple.com", "x.co": "x.com",
}
# Link shorteners hide where a link goes, so they are counted together.
SHORTENERS = {"bit.ly", "tinyurl.com", "cutt.ly", "ow.ly", "is.gd", "shorturl.at", "rb.gy", "tiny.cc", "t.ly",
              "s.id", "buff.ly", "rebrand.ly"}
# Well-known sites are shown by name (instagram.com: Instagram); any other site by its
# address (gib.gov.tr), which says more than a made-up name would.
SITE_NAMES = {
    # global
    "youtube": "YouTube", "x": "X", "instagram": "Instagram", "tiktok": "TikTok", "facebook": "Facebook",
    "reddit": "Reddit", "threads": "Threads", "pinterest": "Pinterest", "snapchat": "Snapchat",
    "tumblr": "Tumblr", "linkedin": "LinkedIn", "telegram": "Telegram", "whatsapp": "WhatsApp",
    "discord": "Discord", "twitch": "Twitch", "kick": "Kick", "vimeo": "Vimeo", "dailymotion": "Dailymotion",
    "netflix": "Netflix", "disneyplus": "Disney+", "primevideo": "Prime Video", "spotify": "Spotify",
    "soundcloud": "SoundCloud", "deezer": "Deezer", "shazam": "Shazam", "apple": "Apple", "icloud": "iCloud",
    "microsoft": "Microsoft", "live": "Microsoft", "office": "Microsoft Office", "github": "GitHub",
    "stackoverflow": "Stack Overflow", "wikipedia": "Wikipedia", "medium": "Medium", "quora": "Quora",
    "imdb": "IMDb", "letterboxd": "Letterboxd", "goodreads": "Goodreads", "wattpad": "Wattpad",
    "chatgpt": "ChatGPT", "openai": "OpenAI", "claude": "Claude", "gemini": "Gemini", "deepl": "DeepL",
    "canva": "Canva", "notion": "Notion", "zoom": "Zoom", "dropbox": "Dropbox", "wetransfer": "WeTransfer",
    "amazon": "Amazon", "ebay": "eBay", "aliexpress": "AliExpress", "temu": "Temu", "shein": "Shein",
    "paypal": "PayPal", "booking": "Booking.com", "airbnb": "Airbnb", "tripadvisor": "Tripadvisor",
    "duolingo": "Duolingo", "change": "Change.org", "9gag": "9GAG", "bbc": "BBC", "cnn": "CNN",
    "nasa": "NASA", "yandex": "Yandex", "bing": "Bing", "steampowered": "Steam", "steamcommunity": "Steam",
    "epicgames": "Epic Games", "transfermarkt": "Transfermarkt", "chess": "Chess.com", "lichess": "Lichess",
    # Turkish
    "eksisozluk": "Ekşi Sözlük", "sahibinden": "Sahibinden", "hepsiburada": "Hepsiburada",
    "trendyol": "Trendyol", "n11": "n11", "yemeksepeti": "Yemeksepeti", "getir": "Getir", "dolap": "Dolap",
    "letgo": "letgo", "ciceksepeti": "Çiçeksepeti", "akakce": "Akakçe", "cimri": "Cimri", "iddaa": "İddaa",
    "nesine": "Nesine", "bilyoner": "Bilyoner", "mackolik": "Maçkolik", "sahadan": "Sahadan",
    "turkiye": "e-Devlet", "obilet": "obilet", "enuygun": "Enuygun", "hurriyet": "Hürriyet",
    "milliyet": "Milliyet", "sozcu": "Sözcü", "haberturk": "Habertürk", "cnnturk": "CNN Türk", "ntv": "NTV",
    "trt": "TRT", "trthaber": "TRT Haber", "onedio": "Onedio", "webtekno": "Webtekno",
    "shiftdelete": "ShiftDelete", "donanimhaber": "DonanımHaber", "technopat": "Technopat", "blutv": "BluTV",
    "exxen": "Exxen", "tabii": "tabii", "beinconnect": "beIN Connect", "puhutv": "puhutv", "fizy": "fizy",
    "muud": "Muud",
}


def google_service(host, path):
    """Google's address alone says little (goo.gl is mostly shared map locations), so its
    main services are named: maps.app.goo.gl/… is Google Haritalar."""
    if host == "forms.gle" or (host.startswith("docs.google.") and path.startswith("/forms")):
        return "Google Formlar"
    if host.startswith("maps.") or path.startswith("/maps"):
        return "Google Haritalar"
    if host.startswith("drive.google."):
        return "Google Drive"
    if host.startswith("docs.google."):
        return "Google Dokümanlar"
    return "Google"


def _host_path(link):
    """A link's host (without www., port or a final dot) and its path, in lower case."""
    address = re.sub(r"^https?://", "", link, flags=re.IGNORECASE)
    host, path = re.match(r"([^/?#]*)(.*)", address, re.DOTALL).groups()
    host = host.split(":")[0].lower().rstrip(".")
    return re.sub(r"^www\.", "", host), path.lower()


def _site_address(host):
    """The address a host belongs to: open.spotify.com is spotify.com, ivd.gib.gov.tr is gib.gov.tr."""
    labels = host.split(".")
    keep = 3 if len(labels) >= 3 and labels[-2] in SECOND_LEVEL and len(labels[-1]) == 2 else 2
    site = ".".join(labels[-keep:])
    return SITE_ALIASES.get(site, site)


def site_of(link):
    """The site a link points to: by name when it is well known (https://open.spotify.com/track/…
    is Spotify), otherwise by its address (https://ivd.gib.gov.tr/… is gib.gov.tr)."""
    host, path = _host_path(link)
    if re.fullmatch(r"[\d.]+", host):
        return host  # an IP address
    site = _site_address(host)
    # share.google is Google's own ending, used for its share links.
    if site in {"goo.gl", "g.co", "forms.gle"} or "google" in (host.split(".")[-1], site.split(".")[0]):
        return google_service(host, path)
    if site in SHORTENERS:
        return "Kısa link"
    if host == "chat.whatsapp.com":
        return "WhatsApp grup daveti"
    # The name before the ending, so youtube.com and youtube.com.tr are one site.
    return SITE_NAMES.get(site.split(".")[0], site)


# What a link holds, read from its address; links that fit none (profiles, news, shops) have none.
LINK_KINDS = ["Video", "Kısa video", "Gönderi", "Müzik", "Harita"]


def link_kind(link):
    """Video, Kısa video, Gönderi, Müzik or Harita, or None when the address does not say."""
    host, path = _host_path(link)
    name = _site_address(host).split(".")[0]
    if host.startswith("music.") or name in {"spotify", "soundcloud", "deezer", "shazam", "fizy", "muud"}:
        return "Müzik"
    if site_of(link) == "Google Haritalar" or host == "maps.apple.com" or (name == "yandex" and "/maps" in path):
        return "Harita"
    if name == "tiktok" or path.startswith(("/shorts/", "/reel/", "/reels/")):
        return "Kısa video"
    if ((name == "youtube" and (host == "youtu.be" or path.startswith(("/watch", "/live", "/embed"))))
            or name in {"twitch", "kick", "vimeo", "dailymotion"} or host == "fb.watch"
            or (name in {"instagram", "facebook"} and path.startswith(("/tv/", "/watch", "/videos")))):
        return "Video"
    if ((name == "x" and "/status/" in path) or (name == "instagram" and path.startswith("/p/"))
            or (name == "reddit" and (host == "redd.it" or "/comments/" in path or "/s/" in path))
            or (name == "threads" and "/post/" in path)
            or (name == "facebook" and ("/posts/" in path or path.startswith(("/share/p/", "/photo"))))):
        return "Gönderi"
    return None


def shared_links(text):
    """The links in a message, typed with http or without; a location share is not one."""
    text = LOCATION_REGEX.sub(" ", text.replace("\u200e", ""))
    without_http = re.sub(LINK_REGEX, " ", text)
    return re.findall(LINK_REGEX, text) + BARE_LINK_REGEX.findall(without_http)


def link_sites(text):
    """The site of each link in a message."""
    return [site_of(link) for link in shared_links(text)]
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

    # A document opens its message with "name.pdf • 5 sayfa belge dahil edilmedi"; the
    # file name and page count are not written text. A caption after it is kept.
    res = re.sub(r"^.*?belge dahil edilmedi", " ", res, flags=re.IGNORECASE | re.DOTALL)

    # A location share with its map link is not written text.
    res = LOCATION_REGEX.sub(" ", res)

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


# Written laughter by style, as the report shows it. Keyboard mashes (see is_keyboard_mash)
# also count as "Random".
_WORD_LAUGHS = {
    "haha": r"a?(?:h+a+){2,}h*|(?:j+a+){2,}j*",
    "hehe / hihi": r"(?:h+e+){2,}h*|(?:h+i+){2,}h*",
    "hoho": r"o?(?:h+o+){2,}h*",
    "Random": r"(?:ks){2,}k?|(?:sk){2,}s?|(?:sj){2,}s?|(?:js){2,}j?|asd\w*"
              r"|(?:hs){2,}h?|(?:sh){2,}s?|(?:kd){2,}k?|(?:dk){2,}d?",
    "za": r"(?:z+a+)+",
    "xd": r"x+d+",
    "lol": r"lo+l+|lmao+",
}
# Open-mouthed smiles and laughing faces; 🙂 😊 🙃 and the like are smiles, not laughter.
LAUGHING_EMOJIS = "😀😃😄😁😆😅🤣😂😹"
LAUGH_STYLES = {
    **{name: re.compile(rf"(?<!\w)(?:{pattern})(?!\w)") for name, pattern in _WORD_LAUGHS.items()},
    # :D is an open-mouthed laugh; :) and :P are a smile and a tongue, like 🙂 and 😛.
    ":D / :d": re.compile(r":d+(?!\w)"),
    "Emoji": re.compile(f"[{LAUGHING_EMOJIS}]"),
}
LAUGH_REGEX = re.compile("|".join(regex.pattern for regex in LAUGH_STYLES.values()))
# Keyboard mashes (asjdkasjd, skdjfhs, pğsdlf): a long word typed mostly on the home row of a
# Turkish Q keyboard with four home-row consonants in a row, which real words almost never have.
HOME_ROW = set("asdfghjklşi")
CONSONANT_RUN_REGEX = re.compile(r"[sdfghjklş]{4}")


def is_keyboard_mash(word):
    return (
        len(word) >= 6
        and bool(CONSONANT_RUN_REGEX.search(word))
        and 3 * sum(char in HOME_ROW for char in word) >= 2 * len(word)
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


def laugh_styles(lower):
    """Which laughter styles a message uses, each once."""
    styles = [name for name, regex in LAUGH_STYLES.items() if regex.search(lower)]
    # A word that already has a style (ksksks, sjsjsj) is not also a keyboard mash.
    if "Random" not in styles and any(
        is_keyboard_mash(word) and not LAUGH_REGEX.fullmatch(word) for word in re.findall(r"[^\W\d_]+", lower)
    ):
        styles.append("Random")
    return {"laugh": int(bool(styles)), "laugh_styles": tuple(styles)}


def style_flags(written):
    """Whether someone asked a question, wrote only question marks or laughed,
    once per message (links left out)."""
    text = strip_links(written)
    lower = turkish_lower(text)
    asked = NOT_QUESTION_REGEX.sub(" ", lower)
    # A reply made of question marks only ("?", "???") is a reaction, counted on its own.
    only_question_mark = bool(re.fullmatch(r"\?+", "".join(text.split())))
    question = not only_question_mark and (
        "?" in text or QUESTION_REGEX.search(asked) or ONLY_NE_REGEX.fullmatch(lower.strip())
    )
    return {
        "question": int(bool(question)),
        "only_question_mark": int(only_question_mark),
        **laugh_styles(lower),
    }


def clean_message_lower(text):
    return turkish_lower(clean_message(text))


def has_media_placeholder(cleaned_text):
    return any(pattern in cleaned_text for pattern in MEDIA_PATTERNS_LOWER)


def get_message_stats(text, kind=whatsapp_chat.MESSAGE):
    cleaned_text = clean_message_lower(text)
    written = "" if kind != whatsapp_chat.MESSAGE else clean_media_placeholders(text)
    emojis = [em["emoji"] for em in emoji.emoji_list(text)]
    # Links are shared, not typed: they count as links, not as letters or words.
    typed = " ".join(strip_links(written).split())
    links = shared_links(text)

    # Only what the person wrote counts: media placeholders, poll syntax and
    # call status text are not letters someone typed.
    return {
        "has_text": int(bool(typed)),
        "words": _get_tokens(typed, min_len=4, keep_apostrophes=True),
        **phrases(typed),
        "link_sites": [site_of(link) for link in links],
        "link_kinds": [kind for kind in map(link_kind, links) if kind],
        "links": len(links),
        "tags": tagged_names(text),
        "emojis": emojis,
        "emoji_count": len(emojis),
        "media": 1 if has_media_placeholder(cleaned_text) else 0,
        **style_flags(typed),
    }


def tagged_names(text):
    """The people a message tags with @, as their names are written in the chat; each once.
    WhatsApp's tag for the whole group, @herkes, is shown as Herkes."""
    names = {whatsapp_chat.clean_sender(name) for name in re.findall(TAG_REGEX, text)} - {""}
    return sorted("Herkes" if whatsapp_chat.turkish_lower(name) == "herkes" else name for name in names)


# Phrases stop at sentence punctuation and line ends: "tamam. ben de" holds no "tamam ben".
SENTENCE_BREAK_REGEX = re.compile(r"[.,;:!?…\n()\[\]\"“”]+")


def is_laughter(word):
    return bool(LAUGH_REGEX.fullmatch(word)) or is_keyboard_mash(word)


# Words that carry no meaning of their own: a phrase made only of these ("ben de",
# "o zaman") says nothing about a chat, so it is not counted.
FUNCTION_WORDS = set("""
a e o ben sen biz siz onlar bu şu bunlar şunlar bana sana ona bize size onlara beni seni onu bizi sizi
onları benim senin onun bizim sizin onların bunu şunu bunun şunun buna şuna bende sende onda bizde
sizde bundan ondan bir iki de da ki mi mı mu mü ne ve veya ya yada ama fakat ile için gibi kadar
daha en çok az var yok değil diye ise her hep şey şeyi şeyler sonra önce şimdi zaten artık bile hala
hâlâ yani işte bi nasıl neden niye nerede zaman olan olarak
""".split())
MAX_PHRASE_WORDS = 6
MIN_PHRASE_MESSAGES = 3  # fewer could be chance


def phrases(typed):
    """The 2- to 6-word phrases of a message, each counted once per message.

    Phrases stay within a sentence; laughter and keyboard mashes break them.
    Phrases made only of function words or tags ("ben de", "@Ali @Veli") are
    left out. Counting once per message keeps "çok çok çok çok" from filling
    the list; repeats such as "yavaş yavaş" count.
    """
    found = set()
    for sentence in SENTENCE_BREAK_REGEX.split(typed):
        # Laughter also breaks a phrase: "geliyorum haha ben" holds no "geliyorum ben".
        runs = [[]]
        for word in _get_tokens(sentence, min_len=1, keep_apostrophes=True):
            if is_laughter(word):
                runs.append([])
            else:
                runs[-1].append(word)
        for words in runs:
            for size in range(2, MAX_PHRASE_WORDS + 1):
                for gram in zip(*(words[i:] for i in range(size))):
                    if not all(word in FUNCTION_WORDS or word.startswith("@") for word in gram):
                        found.add(gram)
    return {"phrases": sorted(found)}


def maximal_phrases(counts, min_count=MIN_PHRASE_MESSAGES, cover=0.8):
    """The phrases worth showing: used in at least ``min_count`` messages and not just
    a part of a longer phrase. "kutlu olsun" is left out when "doğum günün kutlu olsun"
    holds at least ``cover`` of its uses; used often on its own as well, both stay.
    """
    frequent = {phrase: count for phrase, count in counts.items() if count >= min_count}
    longest_cover = Counter()
    for phrase, count in frequent.items():
        for size in range(2, len(phrase)):
            for part in zip(*(phrase[i:] for i in range(size))):
                longest_cover[part] = max(longest_cover[part], count)
    return Counter({phrase: count for phrase, count in frequent.items()
                    if longest_cover[phrase] < cover * count})


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
        # The name in one form, as in the headers, then without spaces: one token.
        clean_name = whatsapp_chat.clean_sender(raw_name).replace(" ", "")

        token = f"ZXTG{len(placeholders)}TX"
        formatted_name = f"@{clean_name}"
        # Store with standard lower() since our token is ascii-safe
        placeholders[token.lower()] = formatted_name
        return token

    # Remove links and system indicators
    text = strip_links(text)
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
TOP_PHRASES = 30  # two columns of 15
TOP_PER_PERSON = 15
TOP_DISTINCTIVE = 10
TOP_EMOJIS = 8  # one line per person in the Emoji table
TOP_SITES = 5
TOP_TAGGED = 5


def rank_range(size):
    """How the rank columns are named in a note: "1.–5.", or "1." for one."""
    return "1." if size == 1 else f"1.–{size}."


def ranked_cells(counter, size):
    """The ``size`` largest entries as ("name", "count") cells, one column per rank, so the
    rows line up; on equal counts, alphabetical. Empty cells fill a short list."""
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:size]
    return [(name, report_style.number(count)) for name, count in ranked] + [""] * (size - len(ranked))


def _top(counter, limit):
    return [[" ".join(item) if isinstance(item, tuple) else item, report_style.number(count)]
            for item, count in counter.most_common(limit)]


def distinctive_words(word_counts, user, limit=TOP_DISTINCTIVE, prior=None):
    """Words (or phrases) this person uses clearly more often than everyone else.

    Weighted log-odds with the whole chat as an informative Dirichlet prior
    (Monroe, Colaresi & Quinn, 2008): each word gets a z-score, and only words
    above 1.96 (about 95% confidence) are kept, highest first. ``prior`` is
    everyone's counts together; pass it to avoid adding them up for each person.
    """
    mine = word_counts[user]
    if prior is None:
        prior = sum(word_counts.values(), Counter())
    n_mine, n_prior = mine.total(), prior.total()
    n_others = n_prior - n_mine
    if not n_mine or not n_others:
        return []
    scores = []
    for word, count in mine.items():
        alpha = prior[word]
        other = alpha - count
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


# Lengths are written short ("1 sa 5 dk.") or in full ("1 saat 5 dakika").
CALL_UNITS = {"sa": 3600, "saat": 3600, "dk": 60, "dakika": 60, "sn": 1, "saniye": 1}
CALL_DURATION_REGEX = re.compile(r"(\d+)\s*(saniye|saat|sa|dakika|dk|sn)\b")
CALL_PARTICIPANTS_REGEX = re.compile(r"(\d+)\s*kişi katıldı")


def call_details(text):
    """Kind, status, length and participants of one call record."""
    plain = turkish_lower(text.replace("\u200e", ""))
    seconds = sum(int(amount) * CALL_UNITS[unit]
                  for amount, unit in CALL_DURATION_REGEX.findall(plain))
    participants = CALL_PARTICIPANTS_REGEX.search(plain)
    return {
        "video": "görüntülü" in plain,
        "missed": bool(re.search(r"cevapsız|cevaplanmadı", plain)),
        "seconds": seconds,
        "participants": int(participants[1]) if participants else None,
    }


def duration(seconds):
    """Write a call length briefly in Turkish: 45 sn, 12 dk, 3 sa 25 dk."""
    if not seconds:
        return "–"  # missed calls have no length
    if seconds < 60:
        return f"{seconds} sn"
    minutes = round(seconds / 60)
    hours, minutes = divmod(minutes, 60)
    if not hours:
        return f"{minutes} dk"
    return f"{hours} sa {minutes} dk" if minutes else f"{hours} sa"


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
    # Calls have their own table and are not messages: no message count includes them.
    calls = df[df["kind"] == whatsapp_chat.CALL]
    df = df[df["kind"] != whatsapp_chat.CALL]

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
                # Messages with an emoji: "😂😂😂" is one, like the emoji tables.
                "Emojis": (user_df["emoji_count"] > 0).sum(),
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
        ["Kişi", "Mesaj", "Pay", "Aktif gün", "Katılım", "Aktif gün başına mesaj", "Silinen"],
        [
            [
                s["User"], number(s["Messages"]), percent(100 * s["Messages"] / len(df)),
                f"{number(s['Days Active'])} / {number(total_chat_days)}",
                percent(100 * s["Days Active"] / total_chat_days),
                decimal(s["Messages"] / s["Days Active"]), number(s["Deleted"]),
            ]
            for s in user_stats
        ],
        numeric=range(1, 7),
        bar_column=1,
        bar_values=[s["Messages"] for s in user_stats],
        total=[
            "Toplam", number(len(df)), "", number(total_chat_days), "",
            decimal(len(df) / total_chat_days), number(df["deleted"].sum()),
        ],
    )
    report.paragraph(
        "Aktif gün: kişinin en az bir mesajı olan gün; Katılım: aktif gün ÷ sohbet günü.",
        "note",
    )
    if excluded_senders:
        report.paragraph(
            f"{number(min_messages)} mesajın altında kalan {number(len(excluded_senders))} kişi "
            f"rapora dahil edilmedi: {', '.join(excluded_senders)}",
            "note",
        )

    # Shares: media, location shares, polls and links, each kind counted per person.
    shares = {}
    for user in sorted_users:
        # Fixed WhatsApp placeholders; standard case-insensitive matching avoids
        # Turkish I/ı issues.
        msgs_clean = user_messages(user)["message"].str.replace("\u200e", "", regex=False)
        shares[user] = {
            **{label: count_contains(msgs_clean, MEDIA_TYPE_PATTERNS[key]) for key, label in MEDIA_LABELS.items()},
            "Anket": int(stats_by_user[user]["Polls"]),
            "Link": int(stats_by_user[user]["Links"]),
        }
    kind_totals = Counter()
    for counts in shares.values():
        kind_totals.update(counts)
    # Most shared kind first, from left to right; kinds nobody shared are left out.
    kinds = sorted((kind for kind in shares[sorted_users[0]] if kind_totals[kind]), key=lambda kind: -kind_totals[kind])
    if kinds:
        sharers = sorted(sorted_users, key=lambda user: -sum(shares[user][kind] for kind in kinds))
        # The total comes first, like the laughter table: how much, then of what.
        report.table(
            ["Kişi", "Toplam", *kinds],
            [[user, number(sum(shares[user][kind] for kind in kinds)), *(number(shares[user][kind]) for kind in kinds)]
             for user in sharers],
            numeric=range(1, len(kinds) + 2),
            title="Paylaşımlar",
            bar_column=1,
            bar_values=[sum(shares[user][kind] for kind in kinds) for user in sharers],
            total=["Toplam", number(sum(kind_totals.values())), *(number(kind_totals[kind]) for kind in kinds)],
        )
        if "Konum" in kinds:
            report.paragraph(
                "Konum: WhatsApp'ın konum paylaşma özelliğiyle gönderilen konumlar; bunların harita linki Link sayılmaz.",
                "note",
            )

    # Calls, by the person who started them ("Siz" is the exporting phone).
    if not calls.empty:
        details = [call_details(text) for text in calls["message"]]
        per_caller = {}
        for caller, detail in zip(calls["user"], details):
            per_caller.setdefault(caller, []).append(detail)

        def call_row(items):
            row = {
                "total": len(items),
                "voice": sum(not item["video"] for item in items),
                "video": sum(item["video"] for item in items),
                "missed": sum(item["missed"] for item in items),
                "seconds": sum(item["seconds"] for item in items),
            }
            counted = [item["participants"] for item in items if item["participants"]]
            row["participants"] = decimal(sum(counted) / len(counted)) if counted else "–"
            return row

        callers = sorted(per_caller, key=lambda caller: -len(per_caller[caller]))
        rows = {caller: call_row(per_caller[caller]) for caller in callers}
        total = call_row(details)
        if is_group_chat:
            # In a group "missed" only means the exporting phone did not join, so it is not shown.
            headers = ["Kişi", "Toplam", "Sesli", "Görüntülü", "Süre", "Ort. katılımcı"]
            cells = lambda row: [number(row["total"]), number(row["voice"]), number(row["video"]),
                                 duration(row["seconds"]), row["participants"]]
            note = ("Süre: aramaların toplam uzunluğu; Ort. katılımcı: kayıttaki katılımcı sayısının ortalaması. ")
        else:
            headers = ["Kişi", "Toplam", "Sesli", "Görüntülü", "Cevaplanan", "Cevapsız", "Süre"]
            cells = lambda row: [number(row["total"]), number(row["voice"]), number(row["video"]),
                                 number(row["total"] - row["missed"]), number(row["missed"]),
                                 duration(row["seconds"])]
            note = "Cevapsız: açılmayan aramalar; Süre: konuşmaların toplam uzunluğu. "
        report.table(
            headers,
            [[caller, *cells(rows[caller])] for caller in callers],
            numeric=range(1, len(headers)),
            title="Aramalar",
            bar_column=1,
            bar_values=[rows[caller]["total"] for caller in callers],
            total=["Toplam", *cells(total)],
        )
        whose = "Aramalar, aramayı başlatan kişiye göre sayılır"
        if "Siz" in per_caller:
            whose += "; Siz: dışa aktaran telefonun başlattığı aramalar"
        report.paragraph(f"{whose}. {note}Aramalar mesaj sayılarına dahil değildir.", "note")

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

    # Tags: who tags whom with @. Someone tagged twice in one message counts once; tagging
    # oneself does not count.
    tag_counts = {user: Counter() for user in sorted_users}
    for user, tags in zip(df["user"], df["tags"]):
        # Meta AI is a bot, not a person, like everywhere else in the report.
        tag_counts[user].update(tag for tag in tags
                                if tag != user and not whatsapp_chat.is_excluded_sender(tag))
    all_tagged = sum(tag_counts.values(), Counter())
    if all_tagged:
        # As many rank columns as the longest list fills: four people tag at most three others.
        tag_ranks = min(TOP_TAGGED, max(len(counts) for counts in tag_counts.values()))
        tag_order = sorted((user for user in sorted_users if tag_counts[user] or all_tagged[user]),
                           key=lambda user: (-tag_counts[user].total(), -all_tagged[user]))
        report.table(
            ["Kişi", "Etiketleme", "Etiketlenme", *(f"{rank}." for rank in range(1, tag_ranks + 1))],
            [[user, number(tag_counts[user].total()), number(all_tagged[user]),
              *ranked_cells(tag_counts[user], tag_ranks)] for user in tag_order],
            numeric=[1, 2],
            title="Etiketleme",
            bars={1: [tag_counts[user].total() for user in tag_order],
                  2: [all_tagged[user] for user in tag_order]},
            # Who is tagged most is the Etiketlenme column already, so the ranks stay empty here.
            total=["Toplam", number(all_tagged.total()), number(sum(all_tagged[user] for user in tag_order)),
                   *[""] * tag_ranks],
            css_class="tags",
        )
        report.paragraph(
            "Etiketleme: kişinin @ ile yaptığı etiketler; Etiketlenme: başkalarının onu etiketlemesi. "
            f"{rank_range(tag_ranks)}: en çok etiketlediği kişiler. Bir mesajda aynı kişi bir kez sayılır; "
            "kendini etiketlemek ve Meta AI'ı etiketlemek sayılmaz.",
            "note",
        )

    # How people write: questions, laughter and emojis.
    report.section("Yazış tarzı")
    written_df = df[df["has_text"] == 1].assign(has_emoji=lambda frame: frame["emoji_count"] > 0)
    style = written_df.groupby("user")[["question", "only_question_mark", "laugh", "has_emoji"]].sum()
    styled_users = [user for user in sorted_users if user in style.index]

    def by_rate(column):
        """People with written text, highest share of messages with ``column`` first."""
        return sorted(styled_users, key=lambda user: -style.at[user, column] / stats_by_user[user]["Written"])

    def share_and_count(count, written):
        # The share comes first in these tables: they are sorted by it and it carries the bar.
        return [percent(100 * count / written), number(int(count))]

    def share_bars(column, users):
        return [style.at[user, column] / stats_by_user[user]["Written"] for user in users]

    if styled_users:
        report.table(
            ["Kişi", "Soru oranı", "Soru", "Yalnız ?"],
            [
                [user, *share_and_count(style.at[user, "question"], stats_by_user[user]["Written"]),
                 number(int(style.at[user, "only_question_mark"]))]
                for user in by_rate("question")
            ],
            numeric=range(1, 4),
            title="Sorular",
            bar_column=1,
            bar_values=share_bars("question", by_rate("question")),
            total=["Toplam", *share_and_count(written_df["question"].sum(), len(written_df)),
                   number(int(written_df["only_question_mark"].sum()))],
        )
        report.paragraph(
            "Soru: soru işareti, mi/mı/mu/mü soru eki (gelcekmisin gibi bitişik de) ya da nasıl, neden, niye, "
            "niçin, kaç, hangi, nerede, kim gibi bir soru kelimesi içeren ya da yalnızca \"ne\" olan yazılı mesaj; "
            "\"ne???\" gibi birden çok işaret ya da ifade de bir soru sayılır. "
            "Yalnız ?: yalnızca soru işaretinden oluşan mesaj (\"?\", \"???\"); bunlar Soru'ya dahil değildir. "
            "Oran yazılı mesajlara göredir.",
            "note",
        )

    # Laughter: how much and in which style, each style once per message.
    laugh_style_counts = {user: Counter() for user in sorted_users}
    for user, styles in zip(written_df["user"], written_df["laugh_styles"]):
        laugh_style_counts[user].update(styles)
    style_totals = sum(laugh_style_counts.values(), Counter())
    # Most used style first, from left to right; the person who laughs most first.
    used_styles = sorted((name for name in LAUGH_STYLES if style_totals[name]), key=lambda name: -style_totals[name])
    laughing_order = by_rate("laugh")
    if used_styles:
        report.table(
            ["Kişi", "Gülme oranı", "Gülme", *used_styles],
            [
                [user, *share_and_count(style.at[user, "laugh"], stats_by_user[user]["Written"]),
                 *(number(laugh_style_counts[user][name]) for name in used_styles)]
                for user in laughing_order
            ],
            numeric=range(1, len(used_styles) + 3),
            title="Gülme",
            bar_column=1,
            bar_values=share_bars("laugh", laughing_order),
            total=["Toplam", *share_and_count(written_df["laugh"].sum(), len(written_df)),
                   *(number(style_totals[name]) for name in used_styles)],
        )
        report.paragraph(
            "Gülme: haha, hehe, hohoho, jajaja, ksksks, sjsj, zaaa, asdf, xd, lol, :D gibi bir ifade, "
            f"asjdkasjd gibi rastgele klavye yazımı ya da {' '.join(LAUGHING_EMOJIS)} içeren yazılı mesaj; "
            "oran yazılı mesajlara göredir. Tarzlar: her tarz bir mesajda bir kez sayılır, bir mesajda birden çok "
            "tarz olabilir. haha: jajaja dahil; hoho: ohohoh, ohhohoh dahil; lol: lmao dahil; "
            "Random: ksksks, sksksk, sjsjsj, jsjs, asdasd, hshs, kdkd ve asjdkasjd gibi rastgele yazımlar; "
            ":D / :d: :DD dahil; :) ve :P gülümseme sayılır, gülme değil. Kimsenin kullanmadığı tarzlar gösterilmez.",
            "note",
        )

    # Emojis: how often each person uses one, then which, most used first. An emoji
    # repeated in one message ("😂😂😂") counts once for that message.
    emoji_order = by_rate("has_emoji")
    emoji_counts = {user: Counter() for user in sorted_users}
    for user, emojis in zip(written_df["user"], written_df["emojis"]):
        emoji_counts[user].update(set(emojis))
    all_emojis = sum(emoji_counts.values(), Counter())
    emoji_ranks = min(TOP_EMOJIS, len(all_emojis))  # no empty rank columns

    def top_emojis(counter):
        # One column per rank, so the emojis line up from row to row.
        return ranked_cells(counter, emoji_ranks)

    if written_df["has_emoji"].any():
        report.table(
            ["Kişi", "Emoji oranı", "Emoji", *(f"{rank}." for rank in range(1, emoji_ranks + 1))],
            [[user, *share_and_count(style.at[user, "has_emoji"], stats_by_user[user]["Written"]),
              *top_emojis(emoji_counts[user])]
             for user in emoji_order],
            numeric=[1, 2],
            title="Emoji",
            bar_column=1,
            bar_values=share_bars("has_emoji", emoji_order),
            total=["Toplam", *share_and_count(written_df["has_emoji"].sum(), len(written_df)), *top_emojis(all_emojis)],
            css_class="emojis",
        )
        report.paragraph(
            "Emoji: emoji içeren yazılı mesaj sayısı; bir mesajdaki emojiler kaç tane olursa olsun bir kez sayılır. "
            f"{rank_range(emoji_ranks)}: en çok kullanılan emojiler ve geçtikleri mesaj sayısı. Oran yazılı mesajlara göredir.",
            "note",
        )

    # Words and phrases were tokenized once per message in parse_chat. A word, like a
    # phrase, counts once per message: "çok çok güzel" holds "güzel" once.
    word_counts = {user: Counter() for user in sorted_users}
    phrase_counts = {user: Counter() for user in sorted_users}
    for user, words, found in zip(df["user"], df["words"], df["phrases"]):
        word_counts[user].update(set(words))
        phrase_counts[user].update(found)
    all_words = sum(word_counts.values(), Counter())
    # Only whole phrases are shown, chosen over the whole chat, so everyone's lists
    # hold the same phrases and not their parts.
    all_phrases = maximal_phrases(sum(phrase_counts.values(), Counter()))
    phrase_counts = {user: Counter({phrase: count for phrase, count in counts.items() if phrase in all_phrases})
                     for user, counts in phrase_counts.items()}

    report.section("Kelimeler ve ifadeler")
    report.term_list(
        ["Kelime", "Mesaj"], _top(all_words, TOP_WORDS), title="En sık kelimeler (4+ harf)",
        more=max(0, len(all_words) - TOP_WORDS),
    )
    report.term_list(
        ["İfade", "Mesaj"], _top(all_phrases, TOP_PHRASES), title="En sık ifadeler", columns=2,
        more=max(0, len(all_phrases) - TOP_PHRASES),
    )
    report.paragraph(
        "Sayılar, kelimenin ya da ifadenin geçtiği mesaj sayısıdır; bir mesajdaki tekrarlar bir kez sayılır. "
        f"İfadeler bir cümle içinde kalan, en az {MIN_PHRASE_MESSAGES} mesajda geçen 2–{MAX_PHRASE_WORDS} "
        "kelimelik kalıplardır; daha uzun bir kalıbın parçası olarak geçenler yalnızca o kalıpla gösterilir "
        "(\"kutlu olsun\" yerine \"doğum günün kutlu olsun\"). Yalnızca \"ben de\", \"o zaman\" gibi kelimelerden "
        "ya da etiketlerden oluşanlar sayılmaz; gülmeler ifadeyi böler.",
        "note",
    )

    report.section("Kişi bazında kelimeler")
    for user in sorted_users:
        stat = stats_by_user[user]
        details = [
            f"{number(stat['Messages'])} mesaj",
            f"{percent(100 * stat['Messages'] / len(df))} pay",
            f"{number(stat['Days Active'])} aktif gün",
        ]
        with report.person(user, details), report.grid(2):
            report.table(["Kelime", "Mesaj"], _top(word_counts[user], TOP_PER_PERSON), numeric=[1])
            report.table(["İfade", "Mesaj"], _top(phrase_counts[user], TOP_PER_PERSON), numeric=[1])

    kinds = [("Kelime", word_counts, all_words), ("İfade", phrase_counts, all_phrases)]
    distinctive = {user: [distinctive_words(counts, user, prior=total) for _, counts, total in kinds]
                   for user in sorted_users}
    if any(any(lists) for lists in distinctive.values()):
        report.section("Kendine özgü kelimeler ve ifadeler")
        report.paragraph(
            "Kişinin sohbetin geri kalanından belirgin biçimde daha sık kullandığı kelime ve ifadeler "
            "(ağırlıklı log-odds, z > 1,96); en belirgini üstte. Kendisi ve Diğerleri: geçtiği mesaj sayısı.",
            "note",
        )
        for user, lists in distinctive.items():
            if not any(lists):
                continue
            with report.person(user, []), report.grid(2):
                for (header, counts, total), terms in zip(kinds, lists):
                    if terms:
                        report.table(
                            [header, "Kendisi", "Diğerleri"],
                            [[" ".join(term) if isinstance(term, tuple) else term,
                              number(counts[user][term]), number(total[term] - counts[user][term])]
                             for term in terms],
                            numeric=[1, 2],
                        )

    # Links
    site_counts = {user: Counter() for user in sorted_users}
    for user, sites in zip(df["user"], df["link_sites"]):
        site_counts[user].update(sites)
    all_sites = sum(site_counts.values(), Counter())

    def top_sites(counter):
        return ranked_cells(counter, min(TOP_SITES, len(all_sites)))

    if all_sites:
        # The person who shares the most links first.
        link_order = sorted((user for user in sorted_users if site_counts[user]),
                            key=lambda user: -site_counts[user].total())
        report.section("Linkler")
        report.table(
            ["Kişi", "Link", *(f"{rank}." for rank in range(1, min(TOP_SITES, len(all_sites)) + 1))],
            [[user, number(site_counts[user].total()), *top_sites(site_counts[user])] for user in link_order],
            numeric=[1],
            bar_column=1,
            bar_values=[site_counts[user].total() for user in link_order],
            total=["Toplam", number(all_sites.total()), *top_sites(all_sites)],
            css_class="sites",
        )
        report.paragraph(
            f"Link: paylaşılan link sayısı; {rank_range(min(TOP_SITES, len(all_sites)))}: en çok paylaşılan siteler. Bilinen siteler adıyla, "
            "diğerleri adresiyle gösterilir; bir sitenin tüm adresleri birlikte sayılır (youtu.be: YouTube, "
            "t.co: X). bit.ly gibi kısaltıcılar Kısa link sayılır; Google linkleri hizmetine göre ayrılır "
            "(Haritalar, Drive, Dokümanlar, Formlar).",
            "note",
        )

        # Content kinds: what the links hold, where the address says it.
        kind_counts = {user: Counter() for user in sorted_users}
        for user, kinds in zip(df["user"], df["link_kinds"]):
            kind_counts[user].update(kinds)
        all_kinds = sum(kind_counts.values(), Counter())
        if all_kinds:
            # Columns by overall use; kinds nobody shared are left out.
            kinds = sorted(all_kinds, key=lambda kind: (-all_kinds[kind], LINK_KINDS.index(kind)))
            kind_order = sorted((user for user in sorted_users if kind_counts[user]),
                                key=lambda user: -kind_counts[user].total())
            report.table(
                ["Kişi", "Toplam", *kinds],
                [[user, number(kind_counts[user].total()), *(number(kind_counts[user][kind]) for kind in kinds)]
                 for user in kind_order],
                numeric=range(1, len(kinds) + 2),
                title="İçerik türü",
                bar_column=1,
                bar_values=[kind_counts[user].total() for user in kind_order],
                total=["Toplam", number(all_kinds.total()), *(number(all_kinds[kind]) for kind in kinds)],
            )
            report.paragraph(
                "Linkin adresinden anlaşılan içerik: Video (YouTube videoları, Twitch…), Kısa video (Shorts, "
                "Reels, TikTok), Gönderi (X, Instagram, Reddit, Threads, Facebook gönderileri), Müzik (Spotify, "
                "YouTube Music, SoundCloud…), Harita (Google Haritalar…). Türü anlaşılmayan linkler (profiller, "
                "haberler, mağazalar…) sayılmaz.",
                "note",
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
    # Calls are not messages; "Siz", who only ever appears on calls, keeps them.
    counts = df.loc[df["kind"] != whatsapp_chat.CALL, "user"].value_counts()
    excluded_senders = sorted(counts[counts < args.min_messages].index)
    if excluded_senders:
        df = df[~df["user"].isin(excluded_senders)]
        print(f"Left out {len(excluded_senders)} people with fewer than {args.min_messages} messages.")
    if (df["kind"] != whatsapp_chat.CALL).sum() == 0:
        print(f"Nobody has at least {args.min_messages} messages in this period.", file=sys.stderr)
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
