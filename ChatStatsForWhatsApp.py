import re
from datetime import datetime
from collections import Counter
import pandas as pd
import emoji
import unicodedata
import markdown
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

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
    # Collect all markdown content
    markdown_content = []
    
    def write_header(title):
        markdown_content.append(f"# {title}\n")
    def write_subheader(title):
        markdown_content.append(f"\n## {title}\n")
    def write_line(content):
        markdown_content.append(content + "\n")
    
    write_header('WhatsApp Chat Statistics')
    
    # Chat Summary
    write_subheader('📅 Chat Timeline')
    write_line(f"**First Message:** {df['datetime'].min()}")
    write_line("")
    write_line(f"**Last Message:** {df['datetime'].max()}")
    write_line("")

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
    
    write_line("| User | Messages | Words | Letters | Media | Emojis | Links |")
    write_line("|------|----------|-------|---------|-------|--------|-------|")
    for stat in user_stats:
        write_line(f"| {stat['User']} | {stat['Messages']:,} | {stat['Words']:,} | {stat['Letters']:,} | {stat['Media']:,} | {stat['Emojis']:,} | {stat['Links']:,} |")
    write_line("")

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
    
    write_line("| User | Stickers | Images | Videos | Audio | Documents | GIFs | Locations | Total |")
    write_line("|------|----------|--------|--------|-------|-----------|------|-----------|-------|")
    for stat in media_stats:
        write_line(f"| {stat['User']} | {stat['Stickers']} | {stat['Images']} | {stat['Videos']} | {stat['Audio']} | {stat['Documents']} | {stat['GIFs']} | {stat['Locations']} | **{stat['Total Media']}** |")
    write_line("")

    # Temporal Statistics
    write_subheader('⏰ Temporal Statistics')
    
    # Messages by Day of Week
    write_line("#### 📅 Messages by Day of Week")
    days = df['weekday'].value_counts().reindex(
        ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    )
    write_line("| Day | Messages |")
    write_line("|-----|----------|")
    for d, v in days.items():
        write_line(f"| {d} | {v:,} |")
    write_line("")
    
    # Messages by Hour
    write_line("#### 🕐 Messages by Hour")
    hour_stats = df['hour'].value_counts().sort_index()
    write_line("| Hour | Messages |")
    write_line("|------|----------|")
    for h, v in hour_stats.items():
        write_line(f"| {h:02d}:00 - {h:02d}:59 | {v:,} |")
    write_line("")
    
    # Messages by Month
    write_line("#### 📆 Messages by Month")
    month_stats = df['month'].value_counts().sort_index()
    write_line("| Month | Messages |")
    write_line("|-------|----------|")
    for m, v in month_stats.items():
        write_line(f"| {m} | {v:,} |")
    write_line("")
    
    # Most Active Days
    write_line("#### 🔥 Most Active 10 Days")
    day_stats = df['date'].value_counts().head(10)
    write_line("| Date | Messages |")
    write_line("|------|----------|")
    for d, v in day_stats.items():
        write_line(f"| {d} | {v:,} |")
    write_line("")
    
    # Users First and Last Message
    write_line("#### 📊 User Activity Timeline")
    
    # Calculate total days the chat has been active
    total_chat_days = df['date'].nunique()
    write_line(f"**Total Chat Days: {total_chat_days}**")
    write_line("")
    
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
    write_line("| User | Days Active | Participation Rate | Messages per Active Day |")
    write_line("|------|-------------|-------------------|------------------------|")
    for timeline in user_timeline:
        participation_rate = (timeline['Days Active'] / total_chat_days) * 100
        user_messages = df[df['user'] == timeline['User']].shape[0]
        messages_per_day = user_messages / timeline['Days Active'] if timeline['Days Active'] > 0 else 0
        write_line(f"| {timeline['User']} | {timeline['Days Active']} / {total_chat_days} | {participation_rate:.1f}% | {messages_per_day:.1f} |")
    write_line("")

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
    
    write_line("| Word | Count |")
    write_line("|------|-------|")
    for word, count in wc.most_common(30):
        write_line(f"| {word} | {count:,} |")
    write_line("")

    # Most Used Words by User
    write_subheader('🗣️ Most Used Words by User')
    for user in df['user'].unique():
        write_line(f"\n#### {user}")
        user_words = []
        # Only process non-media messages
        user_messages = df[(df['user']==user) & (df['media']==0)]['message']
        for msg in user_messages:
            # Remove links from the message before processing
            msg = re.sub(LINK_REGEX, '', msg)
            words = re.findall(r"\b\w+\b", msg.lower())
            user_words.extend([w for w in words if len(w) > 3])
        wc = Counter(user_words)
        
        write_line("| Word | Count |")
        write_line("|------|-------|")
        for word, count in wc.most_common(20):
            write_line(f"| {word} | {count:,} |")
        write_line("")

    # Most Used Emojis by User
    write_subheader('😊 Most Used Emojis by User')
    for user in df['user'].unique():
        user_emojis = Counter()
        for em_list in df[df['user']==user]['emojis']:
            user_emojis.update(em_list)
        
        # Only include users who have emojis
        if user_emojis:
            write_line(f"\n#### {user}")
            write_line("| Emoji | Count |")
            write_line("|-------|-------|")
            for em, cnt in user_emojis.most_common(5):
                write_line(f"| {em} | {cnt:,} |")

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
        <title>WhatsApp Chat Statistics</title>
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
    args = parser.parse_args()

    df = parse_chat(args.chat_file)
    compute_stats(df)