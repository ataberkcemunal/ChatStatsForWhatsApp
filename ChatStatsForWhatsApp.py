import re
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

# Patterns to detect media placeholders in chat
MEDIA_PATTERNS = [
    # Turkish
    'Çıkartma dahil edilmedi',
    'görüntü dahil edilmedi',
    'video dahil edilmedi',
    'ses dahil edilmedi',
    'belge dahil edilmedi',
    'Konum: https://maps.google.com',
    'Görüntülü arama',
    'Sesli arama',
    'Cevapsız görüntülü arama',
    'Cevapsız sesli arama',
    'GIF dahil edilmedi'
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

def clean_media_placeholders(text):
    """Removes U+200E, media placeholders, and poll system text to extract pure user content"""
    if not text:
        return ""
    # Remove markers
    res = text.replace('\u200e', '').replace('\u200f', '').replace('\u200E', '').replace('\u200F', '')
    
    # Remove standard media placeholders
    for pat in MEDIA_PATTERNS:
        res = re.sub(re.escape(pat), '', res, flags=re.IGNORECASE)
        
    # Remove Poll system text
    # ONLY if the message starts with "ANKET:" (ignoring case and leading whitespace/markers)
    # This prevents false positives in normal user messages (e.g., "Benim başka bir seçenek hakkım var")
    
    # Check if it looks like a poll system message
    # We use re.match to check the start of the cleaned string
    if re.match(r'(?:^|\s)ANKET:', res, flags=re.IGNORECASE):
        # 1. Remove "ANKET:" prefix (start of string or after space)
        res = re.sub(r'(?:^|\s)ANKET:\s*', ' ', res, flags=re.IGNORECASE)
        # 2. Remove "SEÇENEK:" globally
        res = re.sub(r'(?:^|\s)SEÇENEK:\s*', ' ', res, flags=re.IGNORECASE)
        # 3. Remove vote counts "(X oy)" globally
        res = re.sub(r'\s*\(\d+\s+oy\)', '', res, flags=re.IGNORECASE)
    
    return res.strip()

def clean_message(text):
    # Remove all invisible and control characters, normalize whitespace, and lowercase
    return ''.join(c for c in text if not unicodedata.category(c).startswith('C')).strip()

def clean_message_lower(text):
    return turkish_lower(clean_message(text))

def _get_tokens(text, min_len=2):
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
    
    # Tokenize (keeping alphanumeric and underscores)
    # Note: we use words and placeholders as tokens
    words = re.findall(r"\b\w+\b", turkish_lower(text))
    
    # Restore placeholders and filter by min_len
    tokens = []
    for w in words:
        # We use standard .lower() for the lookup because our placeholder is ASCII
        lookup_w = w.lower()
        if lookup_w in placeholders:
            tokens.append(placeholders[lookup_w])
        elif len(w) >= min_len:
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
            
            # Remove all invisible/control characters from the start of the line
            line = raw.lstrip().lstrip(''.join(chr(i) for i in range(0,32)) + '\u200e\u200f').strip('\n')

            # Message line: [DD.MM.YYYY, HH:MM:SS] User: message
            # Improved regex to handle cases with no space after colon or no content
            m = re.match(r"^\[(\d{1,2}\.\d{1,2}\.\d{4} \d{2}:\d{2}:\d{2})\] (.*?):(?: (.*))?$", line)
            if m:
                ts = datetime.strptime(m.group(1), '%d.%m.%Y %H:%M:%S')
                user = m.group(2)
                text = m.group(3) if m.group(3) else ""
                cleaned_text = clean_message_lower(text)
                
                # Remove system indicators (edited/deleted) instead of skipping the message
                text = CLEANUP_REGEX.sub('', text).strip()
                cleaned_text = clean_message_lower(text)

                # Check for group name in system messages (before they are skipped)
                for pattern in group_name_patterns:
                    match = re.search(pattern, text)
                    if match:
                        known_group_names.add(match.group(1))
                        # Also add without special chars if needed, but usually exact match works
                
                # Skip group messages
                if is_group_message(text, user, is_system_hint=is_system_hint):
                    continue

                # Calculate stats for normal messages
                word_count = len(text.split())
                letter_count = len(text.replace(' ', ''))
                links = len(re.findall(LINK_REGEX, text))
                emojis = [em['emoji'] for em in emoji.emoji_list(text)]
                emoji_count = len(emojis)
                emoji_count = len(emojis)
                media = 1 if any(pat in cleaned_text for pat in [turkish_lower(p) for p in MEDIA_PATTERNS]) else 0
                entry = {
                    'datetime': ts,
                    'user': user,
                    'message': text,
                    'media': media,
                    'word_count': word_count,
                    'letter_count': letter_count,
                    'links': links,
                    'emojis': emojis,
                    'emoji_count': emoji_count
                }
                records.append(entry)
                current = entry
            else:
                # Continuation of previous message
                if current:
                    current['message'] += ' ' + line
                    text = current['message']
                    cleaned_text = clean_message_lower(text)
                    current['word_count'] = len(text.split())
                    current['letter_count'] = len(text.replace(' ', ''))
                    current['links'] = len(re.findall(LINK_REGEX, text))
                    current['emojis'] = [em['emoji'] for em in emoji.emoji_list(text)]
                    current['emoji_count'] = len(current['emojis'])
                    current['emojis'] = [em['emoji'] for em in emoji.emoji_list(text)]
                    current['emoji_count'] = len(current['emojis'])
                    current['media'] = 1 if any(pat in cleaned_text for pat in [turkish_lower(p) for p in MEDIA_PATTERNS]) else 0
    df = pd.DataFrame(records)
    # add additional columns if not already present
    if 'date' not in df.columns:
            df['date'] = df['datetime'].dt.date
    if 'time' not in df.columns:
            df['time'] = df['datetime'].dt.time
    if 'weekday' not in df.columns:
            df['weekday'] = df['datetime'].dt.day_name()
    if 'month' not in df.columns:
            df['month'] = df['datetime'].dt.to_period('M').astype(str)
    if 'hour' not in df.columns:
            df['hour'] = df['datetime'].dt.hour
            
    # Filter out users that are actually group names
    if known_group_names:
        print(f"DEBUG: Filtering out known group names: {known_group_names}")
        df = df[~df['user'].isin(known_group_names)]
        
    return df

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
    
    write_header('WhatsApp Sohbet İstatistikleri')
    
    # _get_tokens moved to top level

    
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
        user_df = df[df['user'] == user]
        user_stats.append({
            'User': user,
            'Messages': len(user_df),
            'Words': user_df['word_count'].sum(),
            'Letters': user_df['letter_count'].sum(),
            'Media': user_df['media'].sum(),
            'Emojis': user_df['emoji_count'].sum(),
            'Links': user_df['links'].sum()
        })
    
    # Sort by message count
    user_stats.sort(key=lambda x: x['Messages'], reverse=True)
    sorted_users = [s['User'] for s in user_stats]
    
    write_line("| Kullanıcı | Mesajlar | Kelimeler | Harfler | Medya | Emojiler | Linkler |")
    write_line("|-----------|----------|-----------|---------|-------|----------|---------|")
    for stat in user_stats:
        write_line(f"| {stat['User']} | {format_number(stat['Messages'])} | {format_number(stat['Words'])} | {format_number(stat['Letters'])} | {format_number(stat['Media'])} | {format_number(stat['Emojis'])} | {format_number(stat['Links'])} |")
    write_line("")

    write_line("")

    call_stats = []
    for user in sorted_users:
        user_df = df[df['user'] == user]
        
        # We need to look at raw messages (including those marked as media)
        # remove U+200E for searching
        msgs = user_df['message'].str.replace('\u200E', '', regex=False)
        
        # Voice Calls (Initated)
        voice_calls = msgs[msgs.str.contains('Sesli arama', na=False, case=False)].shape[0]
        
        # Video Calls (Initated)
        video_calls = msgs[msgs.str.contains('Görüntülü arama', na=False, case=False)].shape[0]
        
        # Missed Calls (Initiated but not answered by other party)
        # Pattern: 'Cevapsız' (Missed call) OR 'Cevaplanmadı' (Unanswered)
        missed_calls = msgs[
            (msgs.str.contains('Sesli arama|Görüntülü arama', na=False, case=False, regex=True)) & 
            (msgs.str.contains('Cevapsız|Cevaplanmadı', na=False, case=False, regex=True))
        ].shape[0]
        
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
        write_line("| Kullanıcı | Sesli Arama | Görüntülü Arama | Cevaplanan | Cevapsız | Toplam |")
        write_line("|-----------|-------------|-----------------|------------|----------|--------|")
        for stat in call_stats:
            write_line(f"| {stat['User']} | {format_number(stat['Voice'])} | {format_number(stat['Video'])} | {format_number(stat['Answered'])} | {format_number(stat['Missed'])} | **{format_number(stat['Total'])}** |")
        write_line("")

    # Create media stats table
    media_stats = []
    for user in sorted_users:
        user_df = df[df['user'] == user]
        
        user_df = df[df['user'] == user]
        
        # Count different media types using standard case-insensitive matching
        # (Avoids Turkish-specific I/ı issues for these fixed system placeholders)
        msgs_clean = user_df['message'].str.replace('\u200E', '', regex=False)
        
        sticker_count = msgs_clean[msgs_clean.str.contains('çıkartma dahil edilmedi', case=False, na=False)].shape[0]
        image_count = msgs_clean[msgs_clean.str.contains('görüntü dahil edilmedi', case=False, na=False)].shape[0]
        video_count = msgs_clean[msgs_clean.str.contains('video dahil edilmedi', case=False, na=False)].shape[0]
        audio_count = msgs_clean[msgs_clean.str.contains('ses dahil edilmedi', case=False, na=False)].shape[0]
        document_count = msgs_clean[msgs_clean.str.contains('belge dahil edilmedi', case=False, na=False)].shape[0]
        gif_count = msgs_clean[msgs_clean.str.contains('GIF dahil edilmedi', case=False, na=False)].shape[0]
        location_count = msgs_clean[msgs_clean.str.contains('konum:', case=False, na=False)].shape[0]
        
        media_stats.append({
            'User': user,
            'Stickers': sticker_count,
            'Images': image_count,
            'Videos': video_count,
            'Audio': audio_count,
            'Documents': document_count,
            'GIFs': gif_count,
            'Locations': location_count,
            'Total Media': sticker_count + image_count + video_count + audio_count + document_count + gif_count + location_count
        })
    
    # Sort by total media
    if media_stats and any(s['Total Media'] > 0 for s in media_stats):
        write_line("")
        write_subheader('📱 Detaylı Medya İstatistikleri')
        media_stats.sort(key=lambda x: x['Total Media'], reverse=True)
        
        write_line("| Kullanıcı | Çıkartmalar | Resimler | Videolar | Sesler | Belgeler | GIFler | Konumlar | Toplam |")
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
            tokens = _get_tokens(cleaned, min_len=4)
            all_words.extend(tokens)
    wc = Counter(all_words)
    
    write_line("| Kelime | Sayı |")
    write_line("|--------|------|")
    for word, count in wc.most_common(50):
        write_line(f"| {word} | {format_number(count)} |")
    write_line("")



    # Most Used Words by User

    write_subheader('🗣️ Kullanıcılara Göre En Çok Kullanılan Kelimeler')
    for user in sorted_users:
        write_line(f"\n#### {user}")
        user_words = []
        # Process user messages, cleaning placeholders
        user_messages_raw = df[df['user']==user]['message']
        for msg in user_messages_raw:
            cleaned = clean_media_placeholders(msg)
            if cleaned:
                tokens = _get_tokens(cleaned, min_len=4)
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
        user_messages_raw = df[df['user']==user]['message']
        all_bigrams = []
        all_trigrams = []
        
        for msg in user_messages_raw:
            cleaned = clean_media_placeholders(msg)
            if cleaned:
                words = _get_tokens(cleaned, min_len=2)
                
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
        for em_list in df[df['user']==user]['emojis']:
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

    # Messages by Day of Week
    write_line("#### 📅 Haftanın Günlerine Göre Mesajlar")
    days = df['weekday'].map(day_translation).value_counts().reindex(
        ['Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi','Pazar']
    )
    write_line("| Gün | Mesajlar |")
    write_line("|-----|----------|")
    for d, v in days.items():
        write_line(f"| {d} | {format_number(v)} |")
    write_line("")
    
    # Messages by Hour
    write_line("#### 🕐 Saatlere Göre Mesajlar")
    hour_stats = df['hour'].value_counts().sort_index()
    write_line("| Saat | Mesajlar |")
    write_line("|------|----------|")
    for h, v in hour_stats.items():
        write_line(f"| {h:02d}:00 - {h:02d}:59 | {format_number(v)} |")
    write_line("")
    
    # Messages by Month
    write_line("#### 📆 Aylara Göre Mesajlar")
    month_stats = df['month'].value_counts().sort_index()
    write_line("| Ay | Mesajlar |")
    write_line("|----|----------|")
    for m, v in month_stats.items():
        write_line(f"| {m} | {format_number(v)} |")
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
        user_df = df[df['user'] == user]
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
        user_messages = df[df['user'] == timeline['User']].shape[0]
        messages_per_day = user_messages / timeline['Days Active'] if timeline['Days Active'] > 0 else 0
        write_line(f"| {timeline['User']} | {timeline['Days Active']} / {total_chat_days} | {participation_rate:.1f}% | {messages_per_day:.1f} |")
    write_line("")
    
    # Convert markdown to HTML and then to PDF
    markdown_text = ''.join(markdown_content)
    print(f"Debug: Markdown content length: {len(markdown_text)}")
    print(f"Debug: First 500 chars: {markdown_text[:500]}")
    
    # Convert markdown to HTML
    html_content = markdown.markdown(markdown_text, extensions=['tables'])
    print(f"Debug: HTML content length: {len(html_content)}")
    
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
    
    print(f"Debug: Full HTML length: {len(full_html)}")
    
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

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='WhatsApp chat statistics')
    parser.add_argument('chat_file', help='Path to exported chat text file')
    parser.add_argument('--start-date', '-s', help='Filter messages from this date onwards (Format: DD.MM.YYYY)', default=None)
    args = parser.parse_args()

    df = parse_chat(args.chat_file)
    
    if args.start_date:
        from datetime import datetime
        try:
            start_dt = datetime.strptime(args.start_date, '%d.%m.%Y')
            df = df[df['datetime'] >= start_dt]
            print(f"DEBUG: Filtered messages from {args.start_date} onwards. Remaining records: {len(df)}")
        except ValueError:
            print(f"Error: Invalid date format for --start-date. Please use DD.MM.YYYY (e.g., 08.08.2025)")
            exit(1)

    if df.empty:
        print("No messages found for the given criteria.")
        exit(0)

    compute_stats(df)