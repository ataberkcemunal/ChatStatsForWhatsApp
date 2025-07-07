import re
from datetime import datetime
from collections import Counter
import pandas as pd
import emoji
import unicodedata

# Patterns to detect media placeholders in chat
MEDIA_PATTERNS = [
    # Turkish
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
    'Sesli arama. Geri aramak için dokunun',
    # English
    'sticker omitted',
    'image omitted',
    'video omitted',
    'audio omitted',
    'document omitted',
    'GIF omitted',
    'location: https://maps.google.com',
    'Contact card omitted',
    'Missed voice call',
    'Missed video call',
    'Incoming voice call',
    'Incoming video call',
    'Outgoing voice call',
    'Outgoing video call'
]

# Regex for links
LINK_REGEX = r'https?://\S+'

def clean_message(text):
    # Remove all invisible and control characters, normalize whitespace, and lowercase
    return ''.join(c for c in text if not unicodedata.category(c).startswith('C')).strip().lower()

# Parse chat file into DataFrame
def parse_chat(filepath):
    records = []
    current = None
    with open(filepath, encoding='utf-8') as f:
        for raw in f:
            # Remove all invisible/control characters from the start of the line
            line = raw.lstrip().lstrip(''.join(chr(i) for i in range(0,32)) + '\u200e\u200f').strip('\n')
            # Also remove U+200E from anywhere in the line
            line = line.replace('\u200E', '').replace('\u200F', '')
            # If line contains U+200E, only count for media if it matches a media pattern
            if '\u200E' in line:
                m = re.match(r"^\[(\d{1,2}\.\d{1,2}\.\d{4} \d{2}:\d{2}:\d{2})\] (.*?): (.*)", line.replace('\u200E', ''))
                if m and any(pat in m.group(3) for pat in MEDIA_PATTERNS):
                    ts = datetime.strptime(m.group(1), '%d.%m.%Y, %H:%M:%S')
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
            # Message line: [DD.MM.YYYY, HH:MM:SS] User: message
            m = re.match(r"^\[(\d{1,2}\.\d{1,2}\.\d{4}, \d{2}:\d{2}:\d{2})\] (.*?): (.*)", line)
            if m:
                ts = datetime.strptime(m.group(1), '%d.%m.%Y, %H:%M:%S')
                user = m.group(2)
                text = m.group(3)
                cleaned_text = clean_message(text)
                
                # Skip edited message indicators
                if '<this message was edited>' in cleaned_text:
                    continue
                # Debug: print suspected media lines
                if ('omitted' in cleaned_text or 'dahil edilmedi' in cleaned_text or 'arama' in cleaned_text or 'konum' in cleaned_text or 'location:' in cleaned_text):
                    print(f"DEBUG: user={user}, original='{text}', cleaned='{cleaned_text}'")
                    for pat in [p.lower() for p in MEDIA_PATTERNS]:
                        if pat in cleaned_text:
                            print(f"  MATCH: pattern='{pat}'")
                # Calculate stats for normal messages
                word_count = len(text.split())
                letter_count = len(text.replace(' ', ''))
                links = len(re.findall(LINK_REGEX, text))
                emojis = [em['emoji'] for em in emoji.emoji_list(text)]
                emoji_count = len(emojis)
                media = 1 if any(pat in cleaned_text for pat in [p.lower() for p in MEDIA_PATTERNS]) else 0
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
                    cleaned_text = clean_message(text)
                    current['word_count'] = len(text.split())
                    current['letter_count'] = len(text.replace(' ', ''))
                    current['links'] = len(re.findall(LINK_REGEX, text))
                    current['emojis'] = [em['emoji'] for em in emoji.emoji_list(text)]
                    current['emoji_count'] = len(current['emojis'])
                    current['media'] = 1 if any(pat in cleaned_text for pat in [p.lower() for p in MEDIA_PATTERNS]) else 0
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
    with open('chat_stats.md', 'w', encoding='utf-8') as f:
        def write_header(title):
            f.write(f"# {title}\n")
        def write_subheader(title):
            f.write(f"\n## {title}\n")
        
        write_header('WhatsApp Chat Statistics')
        
        # Chat Summary
        write_subheader('📅 Chat Timeline')
        f.write(f"**First Message:** {df['datetime'].min()}\n")
        f.write(f"**Last Message:** {df['datetime'].max()}\n\n")

        # User Statistics
        write_subheader('👥 User Statistics')
        
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
        
        f.write("| User | Messages | Words | Letters | Media | Emojis | Links |\n")
        f.write("|------|----------|-------|---------|-------|--------|-------|\n")
        for stat in user_stats:
            f.write(f"| {stat['User']} | {stat['Messages']:,} | {stat['Words']:,} | {stat['Letters']:,} | {stat['Media']:,} | {stat['Emojis']:,} | {stat['Links']:,} |\n")
        f.write("\n")

        # Detailed Media Statistics
        write_subheader('📱 Detailed Media Statistics')
        
        # Create media stats table
        media_stats = []
        for user in df['user'].unique():
            user_df = df[df['user'] == user]
            
            # Count different media types
            sticker_count = user_df[user_df['message'].str.replace('\u200E', '', regex=False).str.lower().str.contains('sticker omitted', na=False)].shape[0]
            image_count = user_df[user_df['message'].str.replace('\u200E', '', regex=False).str.lower().str.contains('image omitted', na=False)].shape[0]
            video_count = user_df[user_df['message'].str.replace('\u200E', '', regex=False).str.lower().str.contains('video omitted', na=False)].shape[0]
            audio_count = user_df[user_df['message'].str.replace('\u200E', '', regex=False).str.lower().str.contains('audio omitted', na=False)].shape[0]
            document_count = user_df[user_df['message'].str.replace('\u200E', '', regex=False).str.lower().str.contains('document omitted', na=False)].shape[0]
            gif_count = user_df[user_df['message'].str.replace('\u200E', '', regex=False).str.lower().str.contains('gif omitted', na=False)].shape[0]
            location_count = user_df[user_df['message'].str.replace('\u200E', '', regex=False).str.lower().str.contains('location:', na=False)].shape[0]
            
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
        media_stats.sort(key=lambda x: x['Total Media'], reverse=True)
        
        f.write("| User | Stickers | Images | Videos | Audio | Documents | GIFs | Locations | Total |\n")
        f.write("|------|----------|--------|--------|-------|-----------|------|-----------|-------|\n")
        for stat in media_stats:
            f.write(f"| {stat['User']} | {stat['Stickers']} | {stat['Images']} | {stat['Videos']} | {stat['Audio']} | {stat['Documents']} | {stat['GIFs']} | {stat['Locations']} | **{stat['Total Media']}** |\n")
        f.write("\n")

        # Temporal Statistics
        write_subheader('⏰ Temporal Statistics')
        
        # Messages by Day of Week
        f.write("#### 📅 Messages by Day of Week\n")
        days = df['weekday'].value_counts().reindex(
            ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
        )
        f.write("| Day | Messages |\n")
        f.write("|-----|----------|\n")
        for d, v in days.items():
            f.write(f"| {d} | {v:,} |\n")
        f.write("\n")
        
        # Messages by Hour
        f.write("#### 🕐 Messages by Hour\n")
        hour_stats = df['hour'].value_counts().sort_index()
        f.write("| Hour | Messages |\n")
        f.write("|------|----------|\n")
        for h, v in hour_stats.items():
            f.write(f"| {h:02d}:00 - {h:02d}:59 | {v:,} |\n")
        f.write("\n")
        
        # Messages by Month
        f.write("#### 📆 Messages by Month\n")
        month_stats = df['month'].value_counts().sort_index()
        f.write("| Month | Messages |\n")
        f.write("|-------|----------|\n")
        for m, v in month_stats.items():
            f.write(f"| {m} | {v:,} |\n")
        f.write("\n")
        
        # Most Active Days
        f.write("#### 🔥 Most Active 10 Days\n")
        day_stats = df['date'].value_counts().head(10)
        f.write("| Date | Messages |\n")
        f.write("|------|----------|\n")
        for d, v in day_stats.items():
            f.write(f"| {d} | {v:,} |\n")
        f.write("\n")
        
        # Users First and Last Message
        f.write("#### 📊 User Activity Timeline\n")
        
        # Calculate total days the chat has been active
        total_chat_days = df['date'].nunique()
        f.write(f"**Total Chat Days: {total_chat_days}**\n\n")
        
        user_timeline = []
        for user in df['user'].unique():
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
        f.write("| User | Days Active | Participation Rate | Messages per Active Day |\n")
        f.write("|------|-------------|-------------------|------------------------|\n")
        for timeline in user_timeline:
            participation_rate = (timeline['Days Active'] / total_chat_days) * 100
            user_messages = df[df['user'] == timeline['User']].shape[0]
            messages_per_day = user_messages / timeline['Days Active'] if timeline['Days Active'] > 0 else 0
            f.write(f"| {timeline['User']} | {timeline['Days Active']} / {total_chat_days} | {participation_rate:.1f}% | {messages_per_day:.1f} |\n")
        f.write("\n")

        # Most Used Words
        write_subheader('📝 Most Used Words (>3 letters)')
        all_words = []
        # Only process non-media messages
        non_media_messages = df[df['media']==0]['message']
        for msg in non_media_messages:
            # Remove links from the message before processing
            msg = re.sub(LINK_REGEX, '', msg)
            words = re.findall(r"\b\w+\b", msg.lower())
            all_words.extend([w for w in words if len(w) > 3])
        wc = Counter(all_words)
        
        f.write("| Word | Count |\n")
        f.write("|------|-------|\n")
        for word, count in wc.most_common(30):
            f.write(f"| {word} | {count:,} |\n")
        f.write("\n")

        # Most Used Words by User
        write_subheader('🗣️ Most Used Words by User')
        for user in df['user'].unique():
            f.write(f"\n#### {user}\n")
            user_words = []
            # Only process non-media messages
            user_messages = df[(df['user']==user) & (df['media']==0)]['message']
            for msg in user_messages:
                # Remove links from the message before processing
                msg = re.sub(LINK_REGEX, '', msg)
                words = re.findall(r"\b\w+\b", msg.lower())
                user_words.extend([w for w in words if len(w) > 3])
            wc = Counter(user_words)
            
            f.write("| Word | Count |\n")
            f.write("|------|-------|\n")
            for word, count in wc.most_common(20):
                f.write(f"| {word} | {count:,} |\n")
            f.write("\n")

        # Most Used Emojis by User
        write_subheader('😊 Most Used Emojis by User')
        for user in df['user'].unique():
            user_emojis = Counter()
            for em_list in df[df['user']==user]['emojis']:
                user_emojis.update(em_list)
            
            # Only include users who have emojis
            if user_emojis:
                f.write(f"\n#### {user}\n")
                f.write("| Emoji | Count |\n")
                f.write("|-------|-------|\n")
                for em, cnt in user_emojis.most_common(5):
                    f.write(f"| {em} | {cnt:,} |\n")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='WhatsApp chat statistics')
    parser.add_argument('chat_file', help='Path to exported chat text file')
    args = parser.parse_args()

    df = parse_chat(args.chat_file)
    compute_stats(df)