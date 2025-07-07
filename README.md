# WhatsApp Chat Statistics Analyzer

> **Note:** This script works for WhatsApp chat exports in both English and Turkish languages.

A Python script that analyzes WhatsApp chat exports and generates a comprehensive, visually enhanced PDF report (`chat_stats.pdf`) with detailed statistics, emoji-enhanced headers, and clean tables.

## Features

- **User Statistics:**
  - Total messages, words, letters, media, emojis, and links per user
- **Detailed Media Statistics:**
  - Stickers, images, videos, audio, documents, GIFs, locations, and total media per user
- **Temporal Statistics:**
  - Messages by day of week, hour, month, and most active days
  - Chat timeline
- **User Activity Timeline:**
  - Days active, participation rate, messages per active day
- **Word Analysis:**
  - Most used words overall and by user
- **Emoji Analysis:**
  - Most used emojis by user
- **Beautiful PDF Output:**
  - Emoji-enhanced headers, Markdown-style tables, and modern styling

## Output Format

The script generates a PDF report (`chat_stats.pdf`) with:
- Emoji-enhanced headers for easy navigation
- Clean, styled tables for all statistics
- Organized sections with visual hierarchy
- Timeline (First Message and Last Message) on separate lines for clarity
- Comprehensive data in an easy-to-read format

### Example Output Structure

---
# WhatsApp Chat Statistics

## 📅 Chat Timeline
**First Message:** 2023-01-01 00:01:23

**Last Message:** 2023-12-31 23:59:59

---
## 👥 User Statistics
User           | Messages | Words   | Letters | Media | Emojis | Links
--------------|----------|---------|---------|-------|--------|------
Alice          | 21,436   | 87,644  | 545,572 | 3,137 | 935    | 169  
Bob            | 14,345   | 58,035  | 359,675 | 2,824 | 222    | 259  

---
## 📱 Detailed Media Statistics
User           | Stickers | Images | Videos | Audio | Documents | GIFs | Locations | Total
--------------|----------|--------|--------|-------|-----------|------|-----------|------
Alice          | 1,128    | 1,544  | 151    | 361   | 60        | 0    | 5         | 3,137
Bob            | 454      | 1,363  | 132    | 4     | 64        | 0    | 4         | 2,824

---
## ⏰ Temporal Statistics
### 📅 Messages by Day of Week
Day        | Messages
-----------|---------
Monday     | 7,970
Tuesday    | 7,842
Wednesday  | 8,687
...

### 🕐 Messages by Hour
Hour           | Messages
---------------|---------
00:00 - 00:59  | 3,496
01:00 - 01:59  | 3,616
...

### 📆 Messages by Month
Month    | Messages
---------|---------
2023-01  | 1,574
2023-02  | 5,513
...

---
## 📊 User Activity Timeline
User   | Days Active | Participation Rate | Messages per Active Day
-------|-------------|-------------------|------------------------
Alice  | 365/365     | 100.0%            | 58.7
Bob    | 364/365     | 99.7%             | 39.4

---
## 🔥 Most Active 10 Days
Date        | Messages
------------|---------
2023-07-30  | 797
2023-02-08  | 768
...

---
## 📝 Most Used Words
Word   | Count
-------|------
hello  | 5,270
world  | 5,261
...

---
## 😊 Most Used Emojis by User
### Alice
Emoji | Count
------|------
😊    | 146
❤️    | 103
...

---

## Requirements

- Python 3.6+
- Required packages (install using `pip install -r requirements.txt`):
  - pandas
  - emoji
  - weasyprint
  - markdown
  - collections
  - datetime
  - re

## Installation

1. Clone the repository:
```bash
git clone https://github.com/ataberkcemunal/Chat-Stats-for-WhatsApp.git
cd Chat-Stats-for-WhatsApp
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Export your WhatsApp chat:
   - Open the chat in WhatsApp
   - Click on the three dots menu
   - Select "More" > "Export chat"
   - Choose "Without media"
   - Save the file as `_chat.txt`

2. Run the script:
```bash
python ChatStatsForWhatsApp.py _chat.txt
```

3. View the results in `chat_stats.pdf`

## Output Files

- `chat_stats.pdf` - Main statistics report in PDF format
- `_chat.txt` - Your WhatsApp chat export (input file)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## Topics

- whatsapp
- chat-analysis
- statistics
- data-analysis
- python
- text-analysis
- social-media
- data-visualization
- emoji-analysis
- pdf-report
- natural-language-processing
- pandas
- weasyprint
- word-frequency
- temporal-analysis
- user-engagement
 
