import re
from datetime import datetime
from collections import Counter
import pandas as pd
import emoji

# Patterns to detect media placeholders in chat
MEDIA_PATTERNS = [
    'Çıkartma dahil edilmedi',
    'görüntü dahil edilmedi',
    'video dahil edilmedi',
    'ses dahil edilmedi',
    'belge dahil edilmedi',
    'Konum: https://maps.google.com',
    'Görüntülü arama.',
    'Sesli arama.',
    'Cevapsız görüntülü arama.',
    'Cevapsız sesli arama.',
    'Görüntülü arama. Başka bir cihazda cevaplandı',
    'Sesli arama. Başka bir cihazda cevaplandı',
    'Görüntülü arama. Cevaplanmadı',
    'Sesli arama. Cevaplanmadı',
    'Görüntülü arama. Geri aramak için dokunun',
    'Sesli arama. Geri aramak için dokunun'
]

# Regex for links
LINK_REGEX = r'https?://\S+'

# Parse chat file into DataFrame
def parse_chat(filepath):
    records = []
    current = None
    with open(filepath, encoding='utf-8') as f:
        for raw in f:
            line = raw.strip('\n')
            # If line contains U+200E, only count for media if it matches a media pattern
            if '\u200E' in line:
                m = re.match(r"^\[(\d{1,2}\.\d{1,2}\.\d{4} \d{2}:\d{2}:\d{2})\] (.*?): (.*)", line.replace('\u200E', ''))
                if m and any(pat in m.group(3) for pat in MEDIA_PATTERNS):
                    ts = datetime.strptime(m.group(1), '%d.%m.%Y %H:%M:%S')
                    user = m.group(2)
                    entry = {
                        'datetime': ts,
                        'user': user,
                        'message': m.group(3),
                        'media': 1,
                        'word_count': 0,
                        'letter_count': 0,
                        'links': 0,
                        'emojis': [],
                        'emoji_count': 0
                    }
                    records.append(entry)
                continue
            # Message line: [DD.MM.YYYY HH:MM:SS] User: message
            m = re.match(r"^\[(\d{1,2}\.\d{1,2}\.\d{4} \d{2}:\d{2}:\d{2})\] (.*?): (.*)", line)
            if m:
                ts = datetime.strptime(m.group(1), '%d.%m.%Y %H:%M:%S')
                user = m.group(2)
                text = m.group(3)
                # Calculate stats for normal messages
                word_count = len(text.split())
                letter_count = len(text.replace(' ', ''))
                links = len(re.findall(LINK_REGEX, text))
                emojis = [em['emoji'] for em in emoji.emoji_list(text)]
                emoji_count = len(emojis)
                media = 1 if any(pat in text.replace('\u200E', '') for pat in MEDIA_PATTERNS) else 0
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
                    # Recalculate stats for the updated message
                    text = current['message']
                    current['word_count'] = len(text.split())
                    current['letter_count'] = len(text.replace(' ', ''))
                    current['links'] = len(re.findall(LINK_REGEX, text))
                    current['emojis'] = [em['emoji'] for em in emoji.emoji_list(text)]
                    current['emoji_count'] = len(current['emojis'])
                    current['media'] = 1 if any(pat in text.replace('\u200E', '') for pat in MEDIA_PATTERNS) else 0
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
    return df

# Compute and print statistics
def compute_stats(df):
    with open('chat_stats.txt', 'w', encoding='utf-8') as f:
        def write_header(title):
            f.write(f"\n{'='*40}\n{title}\n{'='*40}\n")
        def write_subheader(title):
            f.write(f"\n-- {title} --\n")
        write_header('CHAT SUMMARY')
        f.write(f"Date Range    : {df['datetime'].min()}  →  {df['datetime'].max()}\n")
        f.write(f"Total Messages: {len(df):>8}\n")
        f.write(f"Total Words   : {df['word_count'].sum():>8}\n")
        f.write(f"Total Letters : {df['letter_count'].sum():>8}\n")
        f.write(f"Total Media   : {df['media'].sum():>8}\n")
        f.write(f"Total Emojis  : {df['emoji_count'].sum():>8}\n")
        f.write(f"Total Links   : {df['links'].sum():>8}\n")

        write_header('USER STATISTICS')
        for stat, col in [
            ("Message Count", 'user'),
            ("Word Count", 'word_count'),
            ("Letter Count", 'letter_count'),
            ("Media", 'media'),
            ("Emoji", 'emoji_count'),
            ("Link", 'links')
        ]:
            write_subheader(stat)
            if col == 'user':
                counts = df['user'].value_counts()
            else:
                counts = df.groupby('user')[col].sum().sort_values(ascending=False)
            maxlen = max(len(str(u)) for u in counts.index)
            for u, v in counts.items():
                f.write(f"  {u:<{maxlen}} : {v}\n")

        # Add detailed media type statistics
        write_header('DETAILED MEDIA STATISTICS')
        for user in df['user'].unique():
            f.write(f"\n{user}:\n")
            user_df = df[df['user'] == user]
            # Map full patterns to shorter names
            media_names = {
                'Çıkartma dahil edilmedi': 'Sticker',
                'görüntü dahil edilmedi': 'Image',
                'video dahil edilmedi': 'Video',
                'ses dahil edilmedi': 'Audio',
                'belge dahil edilmedi': 'Document',
                'Konum: https://maps.google.com': 'Location',
                'Görüntülü arama.': 'Video Call',
                'Sesli arama.': 'Voice Call',
                'Cevapsız görüntülü arama.': 'Missed Video Call',
                'Cevapsız sesli arama.': 'Missed Voice Call',
                'Görüntülü arama. Başka bir cihazda cevaplandı': 'Video Call (Other Device)',
                'Sesli arama. Başka bir cihazda cevaplandı': 'Voice Call (Other Device)',
                'Görüntülü arama. Cevaplanmadı': 'Missed Video Call',
                'Sesli arama. Cevaplanmadı': 'Missed Voice Call',
                'Görüntülü arama. Geri aramak için dokunun': 'Video Call (Call Back)',
                'Sesli arama. Geri aramak için dokunun': 'Voice Call (Call Back)'
            }

            # First write normal media stats
            normal_media = {
                'Çıkartma dahil edilmedi': 'Sticker',
                'görüntü dahil edilmedi': 'Image',
                'video dahil edilmedi': 'Video',
                'ses dahil edilmedi': 'Audio',
                'belge dahil edilmedi': 'Document',
                'Konum: https://maps.google.com': 'Location'
            }
            
            for pattern, name in normal_media.items():
                count = user_df[user_df['message'].str.replace('\u200E', '', regex=False).str.contains(pattern, na=False)].shape[0]
                f.write(f"  • {name} count: {count}\n")

            # Then write call stats in a consistent format
            f.write(f"  • Video Call count: {user_df[user_df['message'].str.replace('\u200E', '', regex=False).str.contains('Görüntülü arama.', na=False)].shape[0]}\n")
            f.write(f"  • Voice Call count: {user_df[user_df['message'].str.replace('\u200E', '', regex=False).str.contains('Sesli arama.', na=False)].shape[0]}\n")

        write_header('TEMPORAL STATISTICS')
        write_subheader('Messages by Day of Week')
        days = df['weekday'].value_counts().reindex(
            ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
        )
        for d, v in days.items():
            f.write(f"  {d:<10}: {v}\n")
        write_subheader('Messages by Hour')
        for h, v in df['hour'].value_counts().sort_index().items():
            f.write(f"  {h:02d}:00 - {h:02d}:59 : {v}\n")
        write_subheader('Messages by Month')
        for m, v in df['month'].value_counts().sort_index().items():
            f.write(f"  {m}: {v}\n")
        write_subheader('Most Active 10 Days')
        for d, v in df['date'].value_counts().head(10).items():
            f.write(f"  {d}: {v}\n")
        write_subheader('Users First Message')
        for u, v in df.groupby('user')['datetime'].min().items():
            f.write(f"  {u}: {v}\n")
        write_subheader('Users Last Message')
        for u, v in df.groupby('user')['datetime'].max().items():
            f.write(f"  {u}: {v}\n")

        write_header('MOST USED WORDS (>3 letters)')
        all_words = []
        # Only process non-media messages
        non_media_messages = df[df['media']==0]['message']
        for msg in non_media_messages:
            # Remove links from the message before processing
            msg = re.sub(LINK_REGEX, '', msg)
            words = re.findall(r"\b\w+\b", msg.lower())
            all_words.extend([w for w in words if len(w) > 3])
        wc = Counter(all_words)
        for word, count in wc.most_common(30):
            f.write(f"  • {word}: {count}\n")

        write_header('MOST USED WORDS BY USER')
        for user in df['user'].unique():
            f.write(f"\n{user}:\n")
            user_words = []
            # Only process non-media messages
            user_messages = df[(df['user']==user) & (df['media']==0)]['message']
            for msg in user_messages:
                # Remove links from the message before processing
                msg = re.sub(LINK_REGEX, '', msg)
                words = re.findall(r"\b\w+\b", msg.lower())
                user_words.extend([w for w in words if len(w) > 3])
            wc = Counter(user_words)
            for word, count in wc.most_common(20):
                f.write(f"  • {word}: {count}\n")

        write_header('MOST USED EMOJIS BY USER')
        for user in df['user'].unique():
            f.write(f"\n{user}:\n")
            user_emojis = Counter()
            for em_list in df[df['user']==user]['emojis']:
                user_emojis.update(em_list)
            for em, cnt in user_emojis.most_common(5):
                f.write(f"  • {em} : {cnt}\n")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='WhatsApp chat statistics')
    parser.add_argument('chat_file', help='Path to exported chat text file')
    args = parser.parse_args()

    df = parse_chat(args.chat_file)
    compute_stats(df)