import re
import argparse
import sys
from datetime import datetime
from collections import Counter
import pandas as pd
import emoji
import unicodedata
import markdown
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

def turkish_lower(text):
    """Turkish-aware lowercasing for 'İ' and 'I'"""
    if not text:
        return ""
    # Standard Turkish rules for lingual accuracy:
    # 1. Map uppercase 'İ' to lowercase 'i'
    # 2. Map uppercase 'I' to lowercase 'ı'
    return text.replace('İ', 'i').replace('I', 'ı').lower()

# Patterns to detect media placeholders in chat. Calls are tracked separately,
# so they intentionally do not live in this list.
MEDIA_PATTERNS = [
    'Çıkartma dahil edilmedi',
    'görüntü dahil edilmedi',
    'video dahil edilmedi',
    'ses dahil edilmedi',
    'belge dahil edilmedi',
    'Konum: https://maps.google.com',
    'GIF dahil edilmedi'
]
MEDIA_PATTERNS_LOWER = [turkish_lower(pattern) for pattern in MEDIA_PATTERNS]
MEDIA_TYPE_PATTERNS = {
    'Stickers': 'çıkartma dahil edilmedi',
    'Images': 'görüntü dahil edilmedi',
    'Videos': 'video dahil edilmedi',
    'Audio': 'ses dahil edilmedi',
    'Documents': 'belge dahil edilmedi',
    'GIFs': 'GIF dahil edilmedi',
    'Locations': 'konum:',
}

SYSTEM_TEXT_PATTERNS = [
    # WhatsApp call status text can be exported as message text. These are
    # metadata, not chat content, so keep them out of word and n-gram stats.
    r'\bcevapsız\s+(?:sesli|görüntülü)?\s*arama\b',
    r'\bsesli\s+arama\b',
    r'\bgörüntülü\s+arama\b',
    r'\bgeri\s+aramak\s+için\s+dokunun\b',
    r'\bbaşka\s+bir\s+cihazda\s+cevaplandı\b',
    r'\bcevaplanmadı\b',
]

def is_group_user(user):
    """Check if a user is a group/system user that should be excluded"""
    user_lower = turkish_lower(user)
    
    # Common group/system user patterns
    group_user_patterns = [
        'grup', 'whatsapp', 'sistem',
        'bildirim', 'güncelleme'
    ]
    
    for pattern in group_user_patterns:
        if pattern in user_lower:
            return True
    return False

def is_group_message(text, user, is_system_hint=False):
    """Check if a message is a group/system message that should be excluded"""
    if not text:
        return True

    # First check if the user is a group/system user
    if is_group_user(user):
        return True
        
    # Explicitly keep poll messages (even if they look like system messages)
    # Check for ANKET: at start or \u200eANKET:
    if "ANKET:" in text.upper():
        # Double check it's likely a poll header
        if re.search(r'(?:^|\s|\u200e)ANKET:', text, re.IGNORECASE):
            return False
    
    text_lower = turkish_lower(text)

    # High-confidence system patterns that should be skipped regardless of is_system_hint
    # (These often appear in exports as if a user sent them)
    # Using regex to handle variations like "grubun adını", "grup adını", "grubun simgesini" etc.
    system_patterns = [
        r'grubun adını değiştirdi', r'grup adını değiştirdi',
        r'grubun simgesini değiştirdi', r'grup simgesini değiştirdi',
        r'grubun açıklamasını değiştirdi', r'grup açıklamasını değiştirdi',
        r'grubun konusunu değiştirdi', r'grup konusunu değiştirdi',
        r'grubun adını değiştirdiniz', r'grup adını değiştirdiniz',
        r'grubun simgesini değiştirdiniz', r'grup simgesini değiştirdiniz',
        r'bu grubun simgesini', r'bu grubun adını',
        r'gelişmiş sohbet gizliliğini etkinleştirdi',
        r'gelişmiş sohbet gizliliğini devre dışı bıraktı',
        r'medya dosyalarını otomatik olarak kaydedemez',
        r'okunmamış mesajları özetleyemez',
        r'grup adını [“"](.*?)[”"] olarak değiştirdi',
        r'grup adını [“"](.*?)[”"] olarak değiştirdiniz',
        r'adını [“"](.*?)[”"] olarak değiştirdi',
        r'adını [“"](.*?)[”"] olarak değiştirdiniz'
    ]
    if any(re.search(p, text_lower, re.IGNORECASE) for p in system_patterns):
        return True
    
    # If it's not a group user and no system hint is provided, it's likely a user message
    if not is_system_hint:
        return False
    
    # Common group-related patterns in message content (checked only if hinted as system)
    group_patterns = [
        r'grubu oluşturdu', r'gruba katıldı', r'gruptan ayrıldı',
        r'grup açıklamasını değiştirdi', r'grup ayarlarını değiştirdi',
        r'grup fotoğrafını değiştirdi', r'grup adını değiştirdi',
        r'grup bağlantısını değiştirdi', r'grup bağlantısını sıfırladı',
        r'grup bağlantısını kapatıp açtı', r'grup bağlantısını kapattı',
        r'grup bağlantısını sildi', r'grup bağlantısını yeniledi',
        r'sistem mesajı', r'grup mesajı', r'grup bildirimi',
        r'grup güncellemesi', r'mesajlar ve aramalar uçtan uca şifrelidir', 
        r'bir mesajı sabitlediniz', r'sizi ekledi', r'artık yöneticisiniz',
        r'tarafından okunabilir', r'uçtan uca şifrelenmeye devam ettiği için',
        r'kişisini ekledi', r'kişisini çıkardı', r'güvenlik kodu değişti'
    ]
    
    # Check for matches with group patterns
    for pattern in group_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    # Check for messages that are just group names (usually short, all caps, or contain specific keywords)
    if len(text.strip()) < 50:  # Short messages are more likely to be group names
        # Check if it's mostly uppercase (common for group names)
        if text.isupper() and len(text.strip()) > 3:
            return True
        
        # Check if it contains common group name indicators
        group_indicators = ['tayfa', 'grup', 'ekip', 'kulüp', 'dernek']
        if any(indicator in text_lower for indicator in group_indicators):
            return True
    
    return False

# Regex for links, tags and system indicators (edited/deleted)
LINK_REGEX = r'https?://\S+'
TAG_REGEX = r'@\u2068(.*?)\u2069'
CLEANUP_REGEX = re.compile(r'\u200e?<.*?(?:mesaj düzenlendi|message was edited)>|\u200e?Bu mesajı sildiniz\.|\u200e?Bu mesaj silindi\.', re.IGNORECASE)
CHAT_LINE_REGEX = re.compile(r"^\[(\d{1,2}\.\d{1,2}\.\d{4} \d{2}:\d{2}:\d{2})\] (.*?):(?: (.*))?$")
QUOTED_CHAT_HEADER_REGEX = re.compile(
    r'\[\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\]\s+[^:\n]{1,80}:'
)
LINE_PREFIX_CHARS = ''.join(chr(i) for i in range(0, 32)) + '\u200e\u200f'


def is_poll(text):
    """Check if a message is a poll based on marker or heuristic"""
    if not text:
        return False
        
    # Check for System Poll Marker (\u200e followed by ANKET:)
    has_marker = bool(re.search(r'\u200e\s*ANKET:', text, re.IGNORECASE))
    
    # Check for heuristic: Contains both "ANKET:" and "SEÇENEK:" (ignoring case)
    # This covers cases where marker is lost but structure is clear
    upper_text = str(text).upper()
    has_heuristic = "ANKET:" in upper_text and "SEÇENEK:" in upper_text
    
    return has_marker or has_heuristic

def is_deleted_message(text):
    """Check if a message is a 'This message was deleted' notification"""
    if not text:
        return False
    # Patterns for deleted messages (Turkish and English)
    # Handles invisible markers (\u200e) often present in WhatsApp exports
    patterns = [
        r'\u200e?Bu mesaj silindi\.',
        r'\u200e?Bu mesajı sildiniz\.',
        r'\u200e?This message was deleted\.'
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

def clean_media_placeholders(text):
    """Removes U+200E, media placeholders, and poll system text to extract pure user content"""
    if not text:
        return ""
        
    # Identify if it's a poll using the helper
    is_system_poll = is_poll(text)

    # Remove markers
    res = text.replace('\u200e', '').replace('\u200f', '').replace('\u200E', '').replace('\u200F', '')

    # Remove pasted WhatsApp headers from quoted chat snippets.
    res = QUOTED_CHAT_HEADER_REGEX.sub(' ', res)
    
    # Remove call/status text that WhatsApp inserts into exports.
    for pat in SYSTEM_TEXT_PATTERNS:
        res = re.sub(pat, '', res, flags=re.IGNORECASE)

    # Remove standard media placeholders
    for pat in MEDIA_PATTERNS:
        res = re.sub(re.escape(pat), '', res, flags=re.IGNORECASE)
        
    # Remove Poll system text
    # ONLY if it was identified as a system poll (either by marker or heuristic)
    if is_system_poll:
        flags = re.IGNORECASE
        # 1. Remove "ANKET:" prefix (start of string or after space)
        res = re.sub(r'(?:^|\s)ANKET:\s*', ' ', res, flags=flags)
        # 2. Remove "SEÇENEK:" globally
        res = re.sub(r'(?:^|\s)SEÇENEK:\s*', ' ', res, flags=flags)
        # 3. Remove vote counts "(X oy)" globally
        res = re.sub(r'\s*\(\d+\s+oy\)', '', res, flags=flags)
    
    return re.sub(r'\s+', ' ', res).strip()

def clean_message(text):
    # Remove all invisible and control characters, normalize whitespace, and lowercase
    return ''.join(c for c in text if not unicodedata.category(c).startswith('C')).strip()

def clean_message_lower(text):
    return turkish_lower(clean_message(text))


def has_media_placeholder(cleaned_text):
    return any(pattern in cleaned_text for pattern in MEDIA_PATTERNS_LOWER)


def get_message_stats(text):
    cleaned_text = clean_message_lower(text)
    emojis = [em['emoji'] for em in emoji.emoji_list(text)]

    return {
        'word_count': len(text.split()),
        'letter_count': len(text.replace(' ', '')),
        'links': len(re.findall(LINK_REGEX, text)),
        'emojis': emojis,
        'emoji_count': len(emojis),
        'media': 1 if has_media_placeholder(cleaned_text) else 0
    }


def update_message_stats(entry):
    entry.update(get_message_stats(entry['message']))


def add_time_columns(df):
    if df.empty:
        return df

    df = df.copy()
    df['date'] = df['datetime'].dt.date
    df['time'] = df['datetime'].dt.time
    df['weekday'] = df['datetime'].dt.day_name()
    df['month'] = df['datetime'].dt.to_period('M').astype(str)
    df['hour'] = df['datetime'].dt.hour
    return df


def _get_tokens(text, min_len=2, keep_apostrophes=False):
    """Helper to tokenize text while preserving tags as single units"""
    placeholders = {}
    def repl(m):
        # Extract name, remove all spaces and control characters
        raw_name = m.group(1)
        # Remove invisible/control characters and spaces
        clean_name = ''.join(c for c in raw_name if not unicodedata.category(c).startswith('C'))
        clean_name = clean_name.replace(' ', '')
        
        token = f"ZXTG{len(placeholders)}TX"
        formatted_name = f"@{clean_name}"
        # Store with standard lower() since our token is ascii-safe
        placeholders[token.lower()] = formatted_name
        return token
    
    # Remove links and system indicators
    text = re.sub(LINK_REGEX, '', text)
    text = CLEANUP_REGEX.sub('', text)
    
    # Replace tags with placeholders BEFORE tokenization
    text = re.sub(TAG_REGEX, repl, text)
    
    # Normalize apostrophes (curly to straight) for consistent processing
    text = text.replace('’', "'").replace('‘', "'")
    
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
    records = []
    current = None
    known_group_names = set()
    
    # Patterns to detect group names from system messages
    group_name_patterns = [
        r'"(.*?)" grubunu oluşturdu',
        r'[“"](.*?)[”"] grubunu oluşturdu',
        r'[“"](.*?)[”"] grubunu oluşturdunuz',
        r'grubunun konusunu "(.*?)" olarak değiştirdi',
        r'grubunun konusunu [“"](.*?)[”"] olarak değiştirdi',
        r'Grup adını "(.*?)" olarak değiştirdiniz',
        r'Grup adını [“"](.*?)[”"] olarak değiştirdiniz',
        r'Grup adını "(.*?)" olarak değiştirdi',
        r'Grup adını [“"](.*?)[”"] olarak değiştirdi'
    ]

    with open(filepath, encoding='utf-8') as f:
        for raw in f:
            # Check for system message hint (U+200E at the start or in the message)
            is_system_hint = '\u200e' in raw or '\u200f' in raw
            
            # Keep normal leading spaces: pasted/quoted chat lines often start
            # with a space and should remain part of the previous message.
            line = raw.rstrip('\n').lstrip(LINE_PREFIX_CHARS)

            # Message line: [DD.MM.YYYY, HH:MM:SS] User: message
            # Improved regex to handle cases with no space after colon or no content
            m = CHAT_LINE_REGEX.match(line)
            if m:
                ts = datetime.strptime(m.group(1), '%d.%m.%Y %H:%M:%S')
                user = m.group(2)
                text = m.group(3) if m.group(3) else ""
                
                # Check for deleted message BEFORE cleanup (as CLEANUP_REGEX removes the text)
                is_deleted = 1 if is_deleted_message(text) else 0
                
                # Remove system indicators (edited/deleted) instead of skipping the message
                text = CLEANUP_REGEX.sub('', text).strip()

                # Check for group name in system messages (before they are skipped)
                for pattern in group_name_patterns:
                    match = re.search(pattern, text)
                    if match:
                        known_group_names.add(match.group(1))
                        # Also add without special chars if needed, but usually exact match works
                
                # Skip group messages
                # Only skip if NOT a deleted message (deleted messages become empty after cleanup)
                if not is_deleted and is_group_message(text, user, is_system_hint=is_system_hint):
                    continue

                # Check for poll (only if not deleted)
                poll = 1 if (not is_deleted and is_poll(text)) else 0
                
                entry = {
                    'datetime': ts,
                    'user': user,
                    'message': text,
                    'poll': poll,
                    'deleted': is_deleted,
                }
                update_message_stats(entry)
                records.append(entry)
                current = entry
            else:
                # Continuation of previous message
                if current:
                    current['message'] += ' ' + line
                    text = current['message']
                    update_message_stats(current)
                    
                    # Re-check flags for continuation
                    # Be careful not to overwrite deleted flag if it was already set (since text might be stripped)
                    is_del = 1 if (current.get('deleted') or is_deleted_message(text)) else 0
                    current['deleted'] = is_del
                    current['poll'] = 1 if (not is_del and is_poll(text)) else 0
    df = add_time_columns(pd.DataFrame(records))
            
    # Filter out users that are actually group names
    if known_group_names:
        df = df[~df['user'].isin(known_group_names)]
        
    return df


def parse_start_date(value):
    for fmt in ('%d.%m.%Y %H:%M:%S', '%d.%m.%Y'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError("Please use DD.MM.YYYY or 'DD.MM.YYYY HH:MM:SS'")


# Compute and print statistics
def compute_stats(df):
    # Collect all markdown content
    markdown_content = []

    def write_header(title):
        markdown_content.append(f"# {title}\n")

    def write_subheader(title):
        markdown_content.append(f"\n## {title}\n")

    def write_line(content):
        markdown_content.append(content + "\n")

    def format_number(n):
        return f"{n:,}".replace(',', '.')

    def user_messages(user):
        return df[df['user'] == user]

    def count_contains(series, pattern, regex=False):
        return series.str.contains(pattern, case=False, na=False, regex=regex).sum()
    
    write_header('WhatsApp Sohbet İstatistikleri')
    
    # Chat Summary
    write_subheader('📅 Sohbet Zaman Çizelgesi')
    write_line(f"**İlk Mesaj:** {df['datetime'].min()}")
    write_line("")
    write_line(f"**Son Mesaj:** {df['datetime'].max()}")
    write_line("")

    # User Statistics
    write_subheader('👥 Kullanıcı İstatistikleri')
    
    # Create comprehensive user stats table
    user_stats = []
    for user in df['user'].unique():
        user_df = user_messages(user)
        user_stats.append({
            'User': user,
            'Messages': len(user_df),
            'Letters': user_df['letter_count'].sum(),
            'Media': user_df['media'].sum(),
            'Emojis': user_df['emoji_count'].sum(),
            'Links': user_df['links'].sum(),
            'Polls': user_df['poll'].sum() if 'poll' in user_df.columns else 0,
            'Deleted': user_df['deleted'].sum() if 'deleted' in user_df.columns else 0
        })
        
        # Calculate average letters per message
        if user_stats[-1]['Messages'] > 0:
            user_stats[-1]['AvgLetters'] = user_stats[-1]['Letters'] / user_stats[-1]['Messages']
        else:
            user_stats[-1]['AvgLetters'] = 0
    
    # Sort by message count
    user_stats.sort(key=lambda x: x['Messages'], reverse=True)
    sorted_users = [s['User'] for s in user_stats]
    
    write_line("| Kullanıcı | Ort. Harf | Medya | Emojiler | Linkler | Anketler | Silinen | **Mesajlar** |")
    write_line("|-----------|-----------|-------|----------|---------|----------|---------|----------|")
    for stat in user_stats:
        avg_letters_str = f"{stat['AvgLetters']:.1f}".replace('.', ',')
        write_line(f"| {stat['User']} | {avg_letters_str} | {format_number(stat['Media'])} | {format_number(stat['Emojis'])} | {format_number(stat['Links'])} | {format_number(stat.get('Polls', 0))} | {format_number(stat.get('Deleted', 0))} | **{format_number(stat['Messages'])}** |")
    write_line("")

    write_line("")

    call_stats = []
    for user in sorted_users:
        user_df = user_messages(user)
        
        # We need to look at raw messages (including those marked as media)
        # remove U+200E for searching
        msgs = user_df['message'].str.replace('\u200E', '', regex=False)
        
        # Voice Calls (Initated)
        voice_calls = count_contains(msgs, 'Sesli arama')
        
        # Video Calls (Initated)
        video_calls = count_contains(msgs, 'Görüntülü arama')
        
        # Missed Calls (Initiated but not answered by other party)
        # Pattern: 'Cevapsız' (Missed call) OR 'Cevaplanmadı' (Unanswered)
        call_mask = msgs.str.contains('Sesli arama|Görüntülü arama', na=False, case=False, regex=True)
        missed_mask = msgs.str.contains('Cevapsız|Cevaplanmadı', na=False, case=False, regex=True)
        missed_calls = (call_mask & missed_mask).sum()
        
        total_calls = voice_calls + video_calls
        answered_calls = total_calls - missed_calls
        
        if total_calls > 0:
            call_stats.append({
                'User': user,
                'Voice': voice_calls,
                'Video': video_calls,
                'Answered': answered_calls,
                'Missed': missed_calls,
                'Total': total_calls
            })
    
    if call_stats:
        write_line("")
        write_subheader('📞 Arama İstatistikleri')
        call_stats.sort(key=lambda x: x['Total'], reverse=True)
        write_line("| Kullanıcı | Sesli Arama | Görüntülü Arama | Cevaplanan | Cevapsız | **Toplam** |")
        write_line("|-----------|-------------|-----------------|------------|----------|--------|")
        for stat in call_stats:
            write_line(f"| {stat['User']} | {format_number(stat['Voice'])} | {format_number(stat['Video'])} | {format_number(stat['Answered'])} | {format_number(stat['Missed'])} | **{format_number(stat['Total'])}** |")
        write_line("")

    # Create media stats table
    media_stats = []
    for user in sorted_users:
        user_df = user_messages(user)

        # Count different media types using standard case-insensitive matching
        # (Avoids Turkish-specific I/ı issues for these fixed system placeholders)
        msgs_clean = user_df['message'].str.replace('\u200E', '', regex=False)
        media_counts = {
            label: count_contains(msgs_clean, pattern)
            for label, pattern in MEDIA_TYPE_PATTERNS.items()
        }

        media_stats.append({
            'User': user,
            **media_counts,
            'Total Media': sum(media_counts.values())
        })
    
    # Sort by total media
    if media_stats and any(s['Total Media'] > 0 for s in media_stats):
        write_line("")
        write_subheader('📱 Detaylı Medya İstatistikleri')
        media_stats.sort(key=lambda x: x['Total Media'], reverse=True)
        
        write_line("| Kullanıcı | Çıkartmalar | Resimler | Videolar | Sesler | Belgeler | GIFler | Konumlar | **Toplam** |")
        write_line("|-----------|-------------|----------|----------|--------|----------|--------|----------|--------|")
        for stat in media_stats:
            write_line(f"| {stat['User']} | {stat['Stickers']} | {stat['Images']} | {stat['Videos']} | {stat['Audio']} | {stat['Documents']} | {stat['GIFs']} | {stat['Locations']} | **{format_number(stat['Total Media'])}** |")
        write_line("")




    # Most Used Words
    write_subheader('📝 En Çok Kullanılan Kelimeler (>3 harf)')
    all_words = []
    # Process all messages, cleaning out media placeholders to keep only captions
    for msg in df['message']:
        cleaned = clean_media_placeholders(msg)
        if cleaned:
            tokens = _get_tokens(cleaned, min_len=4, keep_apostrophes=True)
            all_words.extend(tokens)
    wc = Counter(all_words)
    
    write_line("| Kelime | Sayı |")
    write_line("|--------|------|")
    for word, count in wc.most_common(50):
        write_line(f"| {word} | {format_number(count)} |")
    write_line("")


    # Most Used Word Combinations
    write_subheader('🔗 En Çok Kullanılan Kelime Kombinasyonları')
    all_bigrams = []
    all_trigrams = []

    for msg in df['message']:
        cleaned = clean_media_placeholders(msg)
        if cleaned:
            # Use keep_apostrophes=True for n-grams to get meaningful phrases like "Ankara'da hava"
            words = _get_tokens(cleaned, min_len=2, keep_apostrophes=True)

            if len(words) >= 2:
                all_bigrams.extend(zip(words, words[1:]))
            if len(words) >= 3:
                all_trigrams.extend(zip(words, words[1:], words[2:]))

    write_line("\n**İkili Kombinasyonlar**")
    write_line("")
    write_line("| İfade | Sayı |")
    write_line("|-------|------|")
    for bg, count in Counter(all_bigrams).most_common(20):
        write_line(f"| {' '.join(bg)} | {format_number(count)} |")
    write_line("")

    write_line("**Üçlü Kombinasyonlar**")
    write_line("")
    write_line("| İfade | Sayı |")
    write_line("|-------|------|")
    for tg, count in Counter(all_trigrams).most_common(20):
        write_line(f"| {' '.join(tg)} | {format_number(count)} |")
    write_line("")



    # Most Used Words by User

    write_subheader('🗣️ Kullanıcılara Göre En Çok Kullanılan Kelimeler')
    for user in sorted_users:
        write_line(f"\n#### {user}")
        user_words = []
        # Process user messages, cleaning placeholders
        user_messages_raw = user_messages(user)['message']
        for msg in user_messages_raw:
            cleaned = clean_media_placeholders(msg)
            if cleaned:
                tokens = _get_tokens(cleaned, min_len=4, keep_apostrophes=True)
                user_words.extend(tokens)
        wc = Counter(user_words)
        
        write_line("| Kelime | Sayı |")
        write_line("|--------|------|")
        for word, count in wc.most_common(20):
            write_line(f"| {word} | {format_number(count)} |")
        write_line("")

    # Most Used Word Combinations by User
    write_subheader('🔗 Kullanıcı Bazlı En Çok Kullanılan Kelime Kombinasyonları')
    
    for user in sorted_users:
        write_line(f"\n#### {user}")
        # Process messages, cleaning placeholders
        user_messages_raw = user_messages(user)['message']
        all_bigrams = []
        all_trigrams = []
        
        for msg in user_messages_raw:
            cleaned = clean_media_placeholders(msg)
            if cleaned:
                # Use keep_apostrophes=True for n-grams to get meaningful phrases like "Ankara'da hava"
                words = _get_tokens(cleaned, min_len=2, keep_apostrophes=True)
                
                if len(words) >= 2:
                    all_bigrams.extend(zip(words, words[1:]))
                if len(words) >= 3:
                    all_trigrams.extend(zip(words, words[1:], words[2:]))
        
        write_line("\n**İkili Kombinasyonlar**")
        write_line("")
        write_line("| İfade | Sayı |")
        write_line("|-------|------|")
        for bg, count in Counter(all_bigrams).most_common(10):
            write_line(f"| {' '.join(bg)} | {format_number(count)} |")
            
        write_line("")
        
        write_line("**Üçlü Kombinasyonlar**")
        write_line("")
        write_line("| İfade | Sayı |")
        write_line("|-------|------|")
        for tg, count in Counter(all_trigrams).most_common(10):
            write_line(f"| {' '.join(tg)} | {format_number(count)} |")
        write_line("")

    # Most Used Emojis by User
    emoji_data = {}
    for user in sorted_users:
        user_emojis = Counter()
        for em_list in user_messages(user)['emojis']:
            user_emojis.update(em_list)
        if user_emojis:
            emoji_data[user] = user_emojis
            
    if emoji_data:
        write_subheader('😊 Kullanıcılara Göre En Çok Kullanılan Emojiler')
        for user, user_emojis in emoji_data.items():
            write_line(f"\n#### {user}")
            write_line("| Emoji | Sayı |")
            write_line("|-------|------|")
            for em, cnt in user_emojis.most_common(5):
                write_line(f"| {em} | {format_number(cnt)} |")

    # Temporal Statistics
    write_subheader('⏰ Zamansal İstatistikler')
    
    # Translation for day names
    day_translation = {
        'Monday': 'Pazartesi', 'Tuesday': 'Salı', 'Wednesday': 'Çarşamba',
        'Thursday': 'Perşembe', 'Friday': 'Cuma', 'Saturday': 'Cumartesi',
        'Sunday': 'Pazar'
    }

    import base64
    import io
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    def create_chart(x_data, y_data, title, xlabel, ylabel, chart_type='bar'):
        plt.figure(figsize=(10, 6))
        
        if chart_type == 'bar':
            plt.bar(x_data, y_data, color='skyblue')
        elif chart_type == 'line':
            plt.plot(x_data, y_data, marker='o', linestyle='-', color='orange')
            plt.grid(True, linestyle='--', alpha=0.7)
            
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
        
        return f'<img src="data:image/png;base64,{img_base64}" style="width:100%; max-width:800px;" />'

    write_line("#### 📅 Haftanın Günlerine Göre Mesajlar")
    days = df['weekday'].map(day_translation).value_counts().reindex(
        ['Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi','Pazar']
    )
    # Generate Day Chart
    day_chart = create_chart(days.index, days.values, 'Haftanın Günlerine Göre Mesaj Dağılımı', 'Günler', 'Mesaj Sayısı', 'bar')
    write_line(day_chart)
    write_line("")
    
    # Messages by Hour
    write_line("#### 🕐 Saatlere Göre Mesajlar")
    hour_stats = df['hour'].value_counts().reindex(range(24), fill_value=0).sort_index()
    # Generate Hour Chart with all 24 hours on x-axis
    hour_labels = [f"{h:02d}" for h in range(24)]
    hour_chart = create_chart(hour_labels, hour_stats.values, 'Saatlere Göre Mesaj Dağılımı', 'Saat', 'Mesaj Sayısı', 'line')
    write_line(hour_chart)
    write_line("")
    
    # Messages by Month
    write_line("#### 📆 Aylara Göre Mesajlar")
    month_stats = df['month'].value_counts().sort_index()
    # Generate Month Chart
    month_chart = create_chart(month_stats.index.astype(str), month_stats.values, 'Aylara Göre Mesaj Dağılımı', 'Ay', 'Mesaj Sayısı', 'bar')
    write_line(month_chart)
    write_line("")
    write_line("")
    
    # Most Active Days
    write_line("#### 🔥 En Aktif 10 Gün")
    day_stats = df['date'].value_counts().head(10)
    write_line("| Tarih | Mesajlar |")
    write_line("|-------|----------|")
    for d, v in day_stats.items():
        write_line(f"| {d} | {format_number(v)} |")
    write_line("")
    
    # Users First and Last Message
    write_line("#### 📊 Kullanıcı Etkinlik Zaman Çizelgesi")
    
    # Calculate total days the chat has been active
    total_chat_days = df['date'].nunique()
    write_line(f"**Toplam Sohbet Günü: {total_chat_days}**")
    write_line("")
    
    user_timeline = []
    for user in sorted_users:
        user_df = user_messages(user)
        first_msg = user_df['datetime'].min()
        last_msg = user_df['datetime'].max()
        # Count unique days when user sent messages
        active_days = user_df['date'].nunique()
        user_timeline.append({
            'User': user,
            'First Message': first_msg,
            'Last Message': last_msg,
            'Days Active': active_days
        })
    
    user_timeline.sort(key=lambda x: x['Days Active'], reverse=True)
    write_line("| Kullanıcı | Aktif Günler | Katılım Oranı | Aktif Gün Başına Mesaj |")
    write_line("|-----------|--------------|---------------|------------------------|")
    for timeline in user_timeline:
        participation_rate = (timeline['Days Active'] / total_chat_days) * 100
        user_messages_count = user_messages(timeline['User']).shape[0]
        messages_per_day = user_messages_count / timeline['Days Active'] if timeline['Days Active'] > 0 else 0
        write_line(f"| {timeline['User']} | {timeline['Days Active']} / {total_chat_days} | {participation_rate:.1f}% | {messages_per_day:.1f} |")
    write_line("")
    
    # Convert markdown to HTML and then to PDF
    markdown_text = ''.join(markdown_content)

    # Convert markdown to HTML
    html_content = markdown.markdown(markdown_text, extensions=['tables'])

    # Add CSS styling for better PDF appearance
    css_content = """
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 40px; 
            font-size: 12px;
            line-height: 1.4;
        }
        h1 { 
            color: #2c3e50; 
            border-bottom: 2px solid #3498db; 
            padding-bottom: 10px; 
            font-size: 24px;
        }
        h2 { 
            color: #34495e; 
            margin-top: 30px; 
            font-size: 20px;
        }
        h3 { 
            color: #7f8c8d; 
            font-size: 16px;
        }
        table { 
            border-collapse: collapse; 
            width: 100%; 
            margin: 20px 0; 
            font-size: 10px;
        }
        th, td { 
            border: 1px solid #ddd; 
            padding: 6px; 
            text-align: left; 
        }
        th { 
            background-color: #f2f2f2; 
            font-weight: bold; 
        }
        tr:nth-child(even) { 
            background-color: #f9f9f9; 
        }
        strong { 
            color: #e74c3c; 
        }
        p {
            margin: 10px 0;
        }
    </style>
    """
    
    # Combine HTML content with CSS
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>WhatsApp Sohbet İstatistikleri</title>
        {css_content}
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    # Generate PDF
    try:
        font_config = FontConfiguration()
        HTML(string=full_html).write_pdf('chat_stats.pdf', font_config=font_config)
        print("PDF report generated: chat_stats.pdf")
    except Exception as e:
        print(f"Error generating PDF: {e}")
        # Fallback: save HTML for debugging
        with open('debug_output.html', 'w', encoding='utf-8') as f:
            f.write(full_html)
        print("Debug HTML saved to debug_output.html")

def main():
    parser = argparse.ArgumentParser(description='WhatsApp chat statistics')
    parser.add_argument('chat_file', help='Path to exported chat text file')
    parser.add_argument('--start-date', '-s', help='Filter messages from this date/time onwards (Format: DD.MM.YYYY or DD.MM.YYYY HH:MM:SS)', default=None)
    args = parser.parse_args()

    start_dt = None
    if args.start_date:
        try:
            start_dt = parse_start_date(args.start_date)
        except ValueError as exc:
            print(f"Error: Invalid date format for --start-date. {exc}")
            return 1

    df = parse_chat(args.chat_file)

    if df.empty:
        print("No messages found for the given criteria.")
        return 0

    if start_dt:
        df = df[df['datetime'] >= start_dt]
        print(f"Filtered messages from {args.start_date} onwards. Remaining records: {len(df)}")

    if df.empty:
        print("No messages found for the given criteria.")
        return 0

    compute_stats(df)
    return 0


if __name__ == '__main__':
    sys.exit(main())
