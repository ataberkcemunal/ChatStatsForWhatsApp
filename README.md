# WhatsApp Chat Stats 📊

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Language: Turkish](https://img.shields.io/badge/Language-Turkish_Only-blue.svg)](https://github.com/ataberkcemunal/ChatStatsForWhatsApp)

> [!IMPORTANT]
> This tool is specifically optimized for WhatsApp chats exported in **Turkish**.
> [Click here for the Turkish README / Türkçe README için tıklayın](README_TR.md)

A comprehensive Python-based analyzer for WhatsApp chat exports. Transform your raw chat logs into professional, insightful PDF reports featuring detailed statistics, temporal analysis, and natural language insights.

---

## ✨ Key Features

### 👥 User Insights
- **Message Metrics**: Total messages, word counts, and letter counts per participant.
- **Engagement Analysis**: Participation rates and average messages per active day.
- **Media Tracking**: Detailed breakdown of Stickers, Images, Videos, Audio, Documents, GIFs, and Locations.

### 📝 Textual Analysis
- **Advanced Tokenization**: Smart handling of WhatsApp @mentions as single units (e.g., `@User`).
- **N-Gram Analysis**: Discover frequently used Bigrams and Trigrams to identify common catchphrases.
- **Emoji Stats**: See each user's favorite and most frequent emojis.
- **Word Frequency**: Top words used overall and per user (filtered for meaningful results).

### ⏰ Temporal Statistics
- **Activity Heatmap**: Analysis of message volume by hour of the day and day of the week.
- **Monthly Trends**: Track how your conversation has evolved over months.
- **Peak Days**: Identify the top 10 most active days in your chat history.

### 🛡️ Smart Parsing & Cleanup
- **Robust Regex**: Automatically filters out "edited" and "deleted" message indicators from statistics.
- **System Message Detection**: intelligently excludes group formation, name changes, and system notifications.
- **Call Statistics**: Accurate counts for Voice, Video, Answered, and Missed calls.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher
- [GTK+3](https://www.gtk.org/docs/installations/macos/) (Required by WeasyPrint for PDF generation)

### Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/ataberkcemunal/ChatStatsForWhatsApp.git
   cd ChatStatsForWhatsApp
   ```

2. **Setup Virtual Environment (Recommended)**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Usage

1. **Export your WhatsApp chat**:
   - Open the desired chat on your mobile device.
   - Go to **More** > **Export Chat**.
   - Select **Without Media**.
   - Save the exported `.txt` file to the project directory (e.g., as `_chat.txt`).

2. **Generate Report**:
   ```bash
   python ChatStatsForWhatsApp.py _chat.txt
   ```

3. **View Results**:
   Open the newly generated `chat_stats.pdf` to explore your statistics.

---

## 🎨 Design Aesthetics
The generated PDF report features:
- **Rich Typography**: Optimized for readability using modern sans-serif fonts.
- **Structured Layout**: Organized with emoji-enhanced headers and clean Markdown-style tables.
- **Turkish Support**: Fully optimized for Turkish language exports and character sets.

---

## 🛠️ Configuration
The script is designed to be plug-and-play, but you can easily modify `MEDIA_PATTERNS` or `group_patterns` within `ChatStatsForWhatsApp.py` to adapt to different WhatsApp localized versions if needed.

---

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.

## 🤝 Contributing
Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---
Created with ❤️ by [Ataberk Cem Ünal](https://github.com/ataberkcemunal)
