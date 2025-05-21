# WhatsApp Chat Statistics Analyzer

A Python script that analyzes WhatsApp chat exports and generates comprehensive statistics about the conversation.

## Features

- Message Statistics
  - Total messages per user
  - Most used words
  - Most used emojis
  - Longest messages
  - Message lengths

- Media Statistics
  - Stickers
  - Images
  - Videos
  - Voice messages
  - Documents
  - Location shares
  - Video calls
  - Voice calls

- Temporal Statistics
  - Messages by day of week
  - Messages by hour
  - Messages by month
  - First and last messages

## Screenshots

### Complete Output Example
```
========================================
CHAT SUMMARY
========================================
Date Range    : 2023-01-01 00:01:23  →  2023-12-31 23:59:59
Total Messages:    35781
Total Words   :   145679
Total Letters :   905247
Total Media   :     5961
Total Emojis  :     1157
Total Links   :      428

========================================
USER STATISTICS
========================================

-- Message Count --
  Alice : 21436
  Bob   : 14345

-- Word Count --
  Alice : 87644
  Bob   : 58035

-- Letter Count --
  Alice : 545572
  Bob   : 359675

-- Media --
  Alice : 3137
  Bob   : 2824

-- Emoji --
  Alice : 935
  Bob   : 222

-- Link --
  Bob   : 259
  Alice : 169

========================================
DETAILED MEDIA STATISTICS
========================================

Alice:
  • Sticker count: 1128
  • Image count: 1544
  • Video count: 151
  • Audio count: 361
  • Document count: 60
  • Location count: 5
  • Video Call count: 671
  • Voice Call count: 713

Bob:
  • Sticker count: 454
  • Image count: 1363
  • Video count: 132
  • Audio count: 4
  • Document count: 64
  • Location count: 4
  • Video Call count: 446
  • Voice Call count: 357

========================================
TEMPORAL STATISTICS
========================================

-- Messages by Day of Week --
  Monday    : 7970
  Tuesday   : 7842
  Wednesday : 8687
  Thursday  : 7691
  Friday    : 7357
  Saturday  : 7607
  Sunday    : 6993

-- Messages by Hour --
  00:00 - 00:59 : 3496
  01:00 - 01:59 : 3616
  02:00 - 02:59 : 1917
  03:00 - 03:59 : 1568
  04:00 - 04:59 : 792
  05:00 - 05:59 : 239
  06:00 - 06:59 : 51
  07:00 - 07:59 : 173
  08:00 - 08:59 : 411
  09:00 - 09:59 : 512
  10:00 - 10:59 : 712
  11:00 - 11:59 : 857
  12:00 - 12:59 : 1515
  13:00 - 13:59 : 2093
  14:00 - 14:59 : 3403
  15:00 - 15:59 : 3845
  16:00 - 16:59 : 4211
  17:00 - 17:59 : 4311
  18:00 - 18:59 : 3737
  19:00 - 19:59 : 3147
  20:00 - 20:59 : 3635
  21:00 - 21:59 : 3380
  22:00 - 22:59 : 3133
  23:00 - 23:59 : 3393

-- Messages by Month --
  2023-01: 1574
  2023-02: 5513
  2023-03: 3390
  2023-04: 2626
  2023-05: 2923
  2023-06: 3846
  2023-07: 6675
  2023-08: 5299
  2023-09: 4537
  2023-10: 3574
  2023-11: 3692
  2023-12: 4596

-- Most Active 10 Days --
  2023-07-30: 797
  2023-02-08: 768
  2023-06-18: 754
  2023-02-07: 617
  2023-08-27: 602
  2023-09-01: 598
  2023-06-21: 507
  2023-02-06: 450
  2023-06-23: 418
  2023-05-28: 408

-- Users First Message --
  Bob  : 2023-01-01 00:01:23
  Alice: 2023-01-01 00:02:45

-- Users Last Message --
  Bob  : 2023-12-31 23:58:12
  Alice: 2023-12-31 23:59:59

========================================
MOST USED WORDS (>3 letters)
========================================
  • hello: 5270
  • world: 5261
  • thank: 2910
  • great: 2738
  • happy: 1624
  • smile: 1585
  • music: 1373
  • video: 1340
  • photo: 1118
  • today: 1048
  • night: 986
  • morning: 964
  • friend: 845
  • family: 844
  • coffee: 843
  • movie: 787
  • book: 778
  • music: 747
  • dance: 697
  • laugh: 657
  • dream: 649
  • peace: 647
  • love: 624
  • hope: 588
  • time: 578
  • life: 575
  • home: 565
  • food: 553
  • work: 517
  • play: 510

========================================
MOST USED WORDS BY USER
========================================

Alice:
  • hello: 3249
  • world: 3244
  • thank: 1912
  • great: 1546
  • happy: 1328
  • smile: 1129
  • photo: 1081
  • music: 1016
  • video: 887
  • today: 757
  • night: 676
  • coffee: 651
  • friend: 624
  • morning: 602
  • book: 585
  • dance: 574
  • family: 569
  • movie: 556
  • food: 538
  • music: 518

Bob:
  • hello: 2021
  • world: 2017
  • thank: 1364
  • great: 826
  • smile: 456
  • video: 453
  • photo: 410
  • life: 391
  • time: 372
  • morning: 362
  • music: 357
  • night: 310
  • happy: 296
  • today: 291
  • movie: 288
  • hope: 263
  • https: 263
  • work: 263
  • time: 257
  • play: 257

========================================
MOST USED EMOJIS BY USER
========================================

Alice:
  • 😊 : 146
  • ❤️ : 103
  • 👍 : 45
  • 😂 : 44
  • 🎉 : 36

Bob:
  • 😄 : 15
  • 🙏 : 15
  • 🎯 : 14
  • 🌟 : 10
  • 💪 : 9
```

## Requirements

- Python 3.6+
- Required packages (install using `pip install -r requirements.txt`):
  - emoji
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

3. View the results in `chat_stats.txt`

## Output Format

The script generates a detailed report in `chat_stats.txt` containing:
- Message counts and statistics for each user
- Media usage statistics
- Temporal analysis of the conversation
- Most used words and emojis
- Longest messages
- Message length statistics

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
