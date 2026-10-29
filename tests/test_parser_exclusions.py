import argparse
import io
import re
import tempfile
import unittest
import sys
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from ChatStatsForWhatsApp import (
    compute_stats, conversation_stats, day_streaks, distinctive_words, get_message_stats, monthly_shares,
    link_kind, link_sites, maximal_phrases, style_flags, main, parse_chat, parse_end_date,
    positive_hours, call_details, duration,
)
from whatsapp_chat import CALL, MESSAGE


class SenderExclusionTests(unittest.TestCase):
    def test_group_creation_notice_is_not_a_sender_message(self):
        df = self.parse(
            '[10.01.2019 22:51:52] 💩: \u200eBu grubu siz oluşturdunuz\n'
            'bildirimin devamı\n'
            '[10.01.2019 22:52:38] ANNEM: Merhaba\n'
        )
        self.assertEqual(df['user'].tolist(), ['ANNEM'])
        self.assertEqual(df['message'].tolist(), ['Merhaba'])
        self.assertTrue(df.attrs['is_group_chat'])

    def test_unhinted_creation_sentence_is_kept_as_a_user_message(self):
        df = self.parse('[10.01.2019 22:52:38] ANNEM: Bu grubu siz oluşturdunuz\n')
        self.assertEqual(len(df), 1)
        self.assertFalse(df.attrs['is_group_chat'])

    def parse(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'chat.txt'
            path.write_text(text, encoding='utf-8')
            return parse_chat(path)

    def test_excluded_senders_and_their_continuations_are_removed(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: Siz ve Meta AI hakkında konuşuyoruz\n'
            '[1.10.2026 10:01:00] \u200eSiz: Görüntülü arama\n'
            'bu satır önceki kişiye eklenmemeli\n'
            '[1.10.2026 10:02:00] \u200fMeta AI\u200e: bot yanıtı\n'
            'bot yanıtının devamı\n'
            '[1.10.2026 10:03:00] Meta AI Seven: Merhaba\n'
            '[1.10.2026 10:04:00] Bora: Selam\n'
        )
        # The exporting phone's own call stays as a call; everything else from "Siz" is dropped.
        self.assertEqual(df['user'].tolist(), ['Ayşe', 'Siz', 'Meta AI Seven', 'Bora'])
        self.assertEqual(df['kind'].tolist(), [MESSAGE, CALL, MESSAGE, MESSAGE])
        self.assertEqual(df.loc[df['kind'] != CALL, 'message'].tolist(), [
            'Siz ve Meta AI hakkında konuşuyoruz', 'Merhaba', 'Selam'
        ])

    def test_only_excluded_senders_produces_empty_result(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Siz: Bu mesajı sildiniz.\n'
            '[1.10.2026 10:01:00] Meta AI: Merhaba\n'
        )
        self.assertTrue(df.empty)

    def test_group_system_event_detects_group_with_two_active_people(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Sohbet: \u200e“Aile” grubunu oluşturdunuz\n'
            '[1.10.2026 10:01:00] Ayşe: Merhaba\n'
            '[1.10.2026 10:02:00] Bora: Selam\n'
        )
        self.assertTrue(df.attrs['is_group_chat'])
        self.assertEqual(df['user'].nunique(), 2)

    def test_group_detection_survives_date_filtering(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: Merhaba\n'
            '[2.10.2026 10:00:00] Bora: Selam\n'
            '[3.10.2026 10:00:00] Can: Merhaba\n'
        )
        filtered = df[df['datetime'] >= '2026-10-03']
        self.assertTrue(filtered.attrs['is_group_chat'])

    def render(self, df, **options):
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML') as html:
            self.assertTrue(compute_stats(df, output_file=Path(directory) / 'report.pdf', **options))
            return html.call_args.kwargs['string']

    def test_direct_call_table_counts_calls_by_caller(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: Merhaba arkadaşım\n'
            '[1.10.2026 10:01:00] Bora: Görüntülü arama, 2 dk.\n'
            '[1.10.2026 10:02:00] Ayşe: Sesli arama, 1 sa 5 dk.\n'
            '[1.10.2026 10:03:00] Ayşe: \u200eCevapsız sesli arama\n'
            '[1.10.2026 10:04:00] \u200eSiz: Sesli arama, 30 sn.\n'
            '[1.10.2026 10:05:00] Bora: Selam\n'
        )
        # Calls never decide who takes part, so "Siz" keeps this a direct chat.
        self.assertFalse(df.attrs['is_group_chat'])
        for chat_type in ['auto', 'direct']:
            with self.subTest(chat_type=chat_type):
                rendered = self.render(df, chat_type=chat_type)
                self.assertIn('<h3>Aramalar</h3>', rendered)
                self.assertIn('<th class="num">Cevapsız</th>', rendered)
                self.assertNotIn('Ort. katılımcı', rendered)
                self.assertIn('1 sa 5 dk', rendered)
                self.assertIn('Aramalar mesaj sayılarına dahil değildir', rendered)
        # Calls are not messages: the people table still counts one message each.
        people = re.search(r'<td>Ayşe</td><td class="num">(?:<span[^>]*></span> )?(\d+)</td>', self.render(df))
        self.assertEqual(people[1], '1')

    def test_group_call_table_shows_participants_instead_of_missed(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: Merhaba\n'
            '[1.10.2026 10:01:00] Bora: Selam\n'
            '[1.10.2026 10:02:00] Can: Naber\n'
            '[1.10.2026 10:03:00] Ayşe: Sesli arama, 40 sn. \u2022 3 kişi katıldı\n'
            '[1.10.2026 10:04:00] Bora: Cevapsız görüntülü arama, 2 dk. \u2022 2 kişi katıldı\n'
        )
        self.assertTrue(df.attrs['is_group_chat'])
        rendered = self.render(df)
        self.assertIn('<h3>Aramalar</h3>', rendered)
        self.assertIn('Ort. katılımcı', rendered)
        self.assertNotIn('<th class="num">Cevapsız</th>', rendered)

    def test_call_table_is_hidden_without_calls(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: Merhaba\n'
            '[1.10.2026 10:01:00] Bora: Selam\n'
        )
        self.assertNotIn('Aramalar', self.render(df))

    def test_call_details_and_duration(self):
        self.assertEqual(call_details('Cevapsız görüntülü arama, 2 dk. \u2022 3 kişi katıldı'),
                         {'video': True, 'missed': True, 'seconds': 120, 'participants': 3})
        self.assertEqual(call_details('Sesli arama, 1 sa 5 dk.'),
                         {'video': False, 'missed': False, 'seconds': 3900, 'participants': None})
        self.assertEqual(call_details('Görüntülü arama, 1 saat 5 dakika')['seconds'], 3900)
        self.assertEqual(call_details('Sesli arama, 2 dakika 30 saniye')['seconds'], 150)
        self.assertEqual([duration(s) for s in [0, 45, 600, 3900]], ['–', '45 sn', '10 dk', '1 sa 5 dk'])

    def test_sample_and_custom_output_paths(self):
        sample = Path(__file__).resolve().parents[1] / 'examples/sample_chat.txt'
        df = parse_chat(sample)
        self.assertTrue(df.attrs['is_group_chat'])
        self.assertEqual(set(df['user']), {'Ayşe', 'Deniz', 'Ekin'})
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML') as html:
            output = Path(directory) / 'sample.pdf'
            markdown = Path(directory) / 'sample.md'
            self.assertTrue(compute_stats(df, output_file=output, markdown_output=markdown))
            written = Path(html.return_value.write_pdf.call_args.args[0])
            self.assertEqual(written.parent, output.parent)
            self.assertTrue(output.exists())
            self.assertFalse(written.exists())
            text = markdown.read_text(encoding='utf-8')
            self.assertNotIn('## Aramalar', text)
            self.assertNotIn('base64', text)
            # Header and alignment row stay together, so the table renders.
            self.assertIn('| Kişi | Mesaj | Pay | Aktif gün | Katılım | Aktif gün başına mesaj | Silinen |\n|---|---:|', text)

    def test_cli_rejects_output_overwriting_input(self):
        for args in [
            ['chat.txt', '--output', 'chat.txt'],
            ['chat.txt', '--markdown-output', 'chat.txt'],
            ['chat.txt', '--output', 'report.pdf', '--markdown-output', 'report.pdf'],
        ]:
            with self.subTest(args=args), patch.object(sys, 'argv', ['app', *args]):
                with self.assertRaises(SystemExit) as error:
                    main()
                self.assertEqual(error.exception.code, 2)

    def test_failed_pdf_keeps_previous_reports(self):
        df = parse_chat(Path(__file__).resolve().parents[1] / 'examples/sample_chat.txt')
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML') as html:
            root = Path(directory)
            output, markdown = root / 'report.pdf', root / 'report.md'
            output.write_text('old pdf')
            markdown.write_text('old markdown')
            html.return_value.write_pdf.side_effect = OSError('PDF unavailable')
            with patch('builtins.open'), redirect_stderr(io.StringIO()):
                self.assertFalse(compute_stats(df, output_file=output, markdown_output=markdown))
            self.assertEqual(output.read_text(), 'old pdf')
            self.assertEqual(markdown.read_text(), 'old markdown')
            self.assertEqual(sorted(path.name for path in root.iterdir()), ['report.md', 'report.pdf'])

    def test_end_date_without_time_covers_whole_day(self):
        self.assertEqual(parse_end_date('01.10.2026'), datetime(2026, 10, 1, 23, 59, 59))
        self.assertEqual(parse_end_date('01.10.2026 18:30:00'), datetime(2026, 10, 1, 18, 30))
        self.assertEqual(parse_end_date('01.10.2026 18:30'), datetime(2026, 10, 1, 18, 30))

    def test_report_escapes_names(self):
        df = self.parse(
            '[1.10.2026 10:00:00] A|B <i>: merhaba\n'
            '[1.10.2026 10:01:00] A|B <i>: \u200egörüntü dahil edilmedi\n'
            '[1.10.2026 10:02:00] Can_: selam\n'
        )
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML') as html:
            root = Path(directory)
            self.assertTrue(compute_stats(df, output_file=root / 'r.pdf', markdown_output=root / 'r.md'))
            rendered = html.call_args.kwargs['string']
            text = (root / 'r.md').read_text(encoding='utf-8')
        self.assertNotIn('<i>', rendered)
        self.assertIn('A|B &lt;i&gt;', rendered)
        self.assertIn('Can_', rendered)
        self.assertIn('| A\\|B &lt;i&gt; | 2 | %66,7 | 1 / 1 | %100,0 | 2,0 | 0 |', text)
        self.assertIn('**Paylaşımlar**\n\n| Kişi | Toplam | Görsel |\n|---|---:|---:|\n| A\\|B &lt;i&gt; | 1 | 1 |', text)

    def test_conversation_starts_ends_and_replies(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: Günaydın\n'
            '[1.10.2026 10:00:30] Ayşe: Kalktın mı?\n'
            '[1.10.2026 10:02:30] Bora: Kalktım\n'
            '[1.10.2026 10:12:30] Ayşe: Süper\n'
            # An hour or more of silence: Bora opens a new conversation and Ayşe answers.
            '[1.10.2026 16:12:30] Bora: Akşam?\n'
            '[1.10.2026 16:13:15] Ayşe: Olur\n'
        )
        flow = conversation_stats(df)
        self.assertEqual(flow['conversations'], 2)
        self.assertEqual(flow['starts'].to_dict(), {'Ayşe': 1, 'Bora': 1})
        self.assertEqual(flow['ends'].to_dict(), {'Ayşe': 2})
        # Replies as (answered, replier): the gap before Bora's evening message is not one.
        self.assertEqual(flow['pairs'], Counter({('Ayşe', 'Bora'): 1, ('Bora', 'Ayşe'): 2}))
        # With a longer gap the evening message is Bora's reply, not a new conversation.
        flow = conversation_stats(df, gap_hours=8)
        self.assertEqual(flow['conversations'], 1)
        self.assertEqual(flow['pairs'][('Ayşe', 'Bora')], 2)
        # The default gap is one hour: 59 minutes keeps the conversation going.
        self.assertEqual(conversation_stats(self.parse(
            '[1.10.2026 10:00:00] Ayşe: a\n[1.10.2026 10:59:00] Bora: b\n[1.10.2026 12:00:00] Ayşe: c\n'
        ))['conversations'], 2)

    def test_conversation_gap_option(self):
        self.assertEqual(positive_hours('1,5'), 1.5)
        self.assertEqual(positive_hours('3'), 3.0)
        for value in ['0', '-2', 'abc', 'nan', 'inf']:
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                positive_hours(value)

    def test_distinctive_words(self):
        counts = {
            # Everyone says "tamam"; only Ayşe keeps saying "kanka" and once "nadir".
            'Ayşe': Counter({'tamam': 30, 'kanka': 25, 'nadir': 1}),
            'Bora': Counter({'tamam': 30, 'hocam': 20, 'kanka': 1}),
            'Can': Counter({'tamam': 30, 'hocam': 15}),
        }
        self.assertEqual(distinctive_words(counts, 'Ayşe'), ['kanka'])
        self.assertEqual(distinctive_words(counts, 'Bora'), ['hocam'])
        self.assertEqual(distinctive_words({'Ayşe': Counter({'tamam': 3})}, 'Ayşe'), [])

    def test_report_shows_distinctive_words_in_the_person_band(self):
        lines = ''.join(
            f'[1.10.2026 10:{minute:02d}:00] {name}: {text}\n'
            for minute, (name, text) in enumerate(
                [('Ayşe', 'kanka naber tamam')] * 20 + [('Bora', 'hocam selam tamam')] * 20
            )
        )
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML'):
            root = Path(directory)
            self.assertTrue(compute_stats(self.parse(lines), output_file=root / 'r.pdf',
                                          markdown_output=root / 'r.md'))
            text = (root / 'r.md').read_text(encoding='utf-8')
        section = text[text.index('## Kendine özgü kelimeler ve ifadeler'):]
        self.assertIn('### Ayşe\n', section)
        self.assertIn('| Kelime | Kendisi | Diğerleri |\n|---|---:|---:|\n| kanka | 20 | 0 |\n| naber | 20 | 0 |\n', section)
        # Only the whole phrase is shown, not its parts ("kanka naber").
        self.assertIn('| İfade | Kendisi | Diğerleri |\n|---|---:|---:|\n| kanka naber tamam | 20 | 0 |\n\n', section)
        self.assertIn('| hocam selam tamam | 20 | 0 |\n', section)

    def test_day_streaks(self):
        days = [date(2026, 10, d) for d in (1, 2, 2, 3, 8, 9, 10, 11, 13)]
        streak, silence = day_streaks(days)
        self.assertEqual(streak, (4, date(2026, 10, 8), date(2026, 10, 11)))
        self.assertEqual(silence, (4, date(2026, 10, 4), date(2026, 10, 7)))
        self.assertEqual(day_streaks([date(2026, 10, 5)]), ((1, date(2026, 10, 5), date(2026, 10, 5)), None))

    def test_monthly_shares_group_people_after_the_limit(self):
        df = self.parse(
            '[1.09.2026 10:00:00] Ayşe: a\n'
            '[2.09.2026 10:00:00] Ayşe: b\n'
            '[3.09.2026 10:00:00] Bora: c\n'
            '[4.09.2026 10:00:00] Can: d\n'
            '[1.10.2026 10:00:00] Bora: e\n'
        )
        shares = monthly_shares(df, ['Ayşe', 'Bora', 'Can'], limit=2)
        self.assertEqual(shares.columns.tolist(), ['Ayşe', 'Bora', 'Diğer'])
        self.assertEqual(shares.loc['2026-09'].tolist(), [50.0, 25.0, 25.0])
        self.assertEqual(shares.loc['2026-10'].tolist(), [0.0, 100.0, 0.0])

    def test_style_flags(self):
        cases = {
            'ne zaman?': (1, 0),
            'ne??? nasıl???': (1, 0),        # one question per message, however many marks
            'hahaha çok iyi': (0, 1),
            'KSKSKSKS': (0, 1),
            'sjsjsj 😂': (0, 1),
            'hohoho': (0, 1),
            'ohohoho': (0, 1),
            'ohhohoh': (0, 1),
            'ohhohoho': (0, 1),
            'OHOHOHO naber?': (1, 1),
            'za': (0, 1),
            'ZAAAA': (0, 1),
            'zazaza': (0, 1),
            'tamam :D': (0, 1),
            'iyi:dd': (0, 1),
            'peki :)': (0, 0),
            'zaten zayıf': (0, 0),
            'saat 10:30, :dakika': (0, 0),
            'geldin mi': (1, 0),
            'GELİYOR MUSUN': (1, 0),
            'yapar misin': (1, 0),
            'gelcekmisin': (1, 0),
            'gidiyormuyuz yarın': (1, 0),
            'orda mıydı': (1, 0),
            'nasılsın': (1, 0),
            'nerdesin haha': (1, 1),
            'kaçta buluşalım': (1, 0),
            'kime verdin': (1, 0),
            'ne': (1, 0),
            'neeee': (1, 0),
            'evimi sattım, adamı gördüm': (0, 0),
            'resmi tatil, minimum mutlu müzik': (0, 0),
            'kalemimiz ve evimiz': (0, 0),
            'kimse yok, nasılsa gelir': (0, 0),
            'neredeyse bitti': (0, 0),
            'nerdeyse geldim': (0, 0),
            'nerdesin': (1, 0),
            'buna neden oldu': (0, 0),
            'neden geldin': (1, 0),
            'hangisi olursa olsun': (0, 0),
            'hangi film olursa olsun': (0, 0),
            'kim olursa olsun': (0, 0),
            'x.com/?a=1': (0, 0),
            'neredeyse bitti mi': (1, 0),
            'sksksk': (0, 1),
            'hshs': (0, 1),
            'kdkdkd': (0, 1),
            'jajaja': (0, 1),
            'tamam :P': (0, 0),
            'tamam :DD': (0, 1),
            '😆': (0, 1),
            'asjdkasjd': (0, 1),
            'skdjfhs ya': (0, 1),
            'pğsdlf': (0, 1),
            'ahsjsjs': (0, 1),
            # Real words and consonant abbreviations are not keyboard mashes.
            'tşkler slm kdşm akşam kaşar kardeşimler': (0, 0),
            'lights nights highlights': (0, 0),
            'ne güzel': (0, 0),
            'oho': (0, 0),
            'https://x.com/?a=1': (0, 0),
            'hayırlı akşamlar, şaka şaka, horoz': (0, 0),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                flags = style_flags(text)
                self.assertEqual((flags['question'], flags['laugh']), expected)
        # (question, only question marks): a bare "?" is a reaction, not a question.
        only = {'?': (0, 1), '???': (0, 1), ' ? ? ': (0, 1), '?!': (1, 0), 'ne?': (1, 0), 'naber': (0, 0)}
        for text, expected in only.items():
            with self.subTest(text=text):
                flags = style_flags(text)
                self.assertEqual((flags['question'], flags['only_question_mark']), expected)

    def test_style_and_reply_tables(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: naber?\n'
            '[1.10.2026 10:01:00] Bora: hahaha iyi\n'
            '[1.10.2026 10:02:00] Ayşe: SÜPER??\n'
            '[1.10.2026 10:03:00] Bora: ???\n'
            '[1.10.2026 10:04:00] Can: \u200egörüntü dahil edilmedi\n'
            '[1.10.2026 10:05:00] Bora: güzel!\n'
        )
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML'):
            root = Path(directory)
            self.assertTrue(compute_stats(df, chat_type='group', output_file=root / 'r.pdf',
                                          markdown_output=root / 'r.md'))
            text = (root / 'r.md').read_text(encoding='utf-8')
        # Can wrote nothing, so has no style row.
        self.assertIn('**Sorular**\n\n| Kişi | Soru oranı | Soru | Yalnız ? |\n|---|---:|---:|---:|\n'
                      '| Ayşe | %100,0 | 2 | 0 |\n| Bora | %0,0 | 0 | 1 |\n| Toplam | %40,0 | 2 | 1 |', text)
        self.assertIn('**Gülme**\n\n| Kişi | Gülme oranı | Gülme | haha |\n|---|---:|---:|---:|\n'
                      '| Bora | %33,3 | 1 | 1 |\n| Ayşe | %0,0 | 0 | 0 |\n| Toplam | %20,0 | 1 | 1 |', text)
        # The shares table follows the people table; activity is part of the people table.
        self.assertLess(text.index('## Kişiler'), text.index('**Paylaşımlar**'))
        self.assertNotIn('Etkinlik', text)
        self.assertNotIn('Ort. harf', text)
        # Questions, laughter and emojis follow the people, in one section; time comes last.
        self.assertLess(text.index('**Kim kime yanıt veriyor**'), text.index('## Yazış tarzı'))
        self.assertLess(text.index('## Yazış tarzı'), text.index('**Sorular**'))
        self.assertLess(text.index('**Gülme**'), text.index('## Kelimeler ve ifadeler'))
        self.assertEqual(text.rindex('\n## '), text.index('\n## Zaman'))
        self.assertNotIn('## Medya', text)
        style = text[text.index('**Sorular**'):text.index('**Gülme**')]
        self.assertNotIn('| Can |', style)
        # Replies (from → to): Bora→Ayşe, Ayşe→Bora, Bora→Ayşe, Can→Bora, Bora→Can.
        self.assertIn('| Bora | Ayşe | %66,7 | Ayşe | %50,0 |', text)
        self.assertIn('| Can | Bora | %100,0 | Bora | %100,0 |', text)
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML'):
            root = Path(directory)
            compute_stats(df, chat_type='direct', output_file=root / 'r.pdf', markdown_output=root / 'r.md')
            self.assertNotIn('Kim kime', (root / 'r.md').read_text(encoding='utf-8'))

    def test_documents_and_links_are_not_written_text(self):
        cases = {
            # text: (letters, written, links, words)
            '\u200echat_stats.pdf • \u200e5 sayfa \u200ebelge dahil edilmedi': (0, 0, 0, []),
            'Rapor 2026.pdf • 3 sayfa belge dahil edilmedi bunu oku': (7, 1, 0, ['bunu']),
            'https://x.com/someone/status/1839283746537281?s=46&t=AbCd': (0, 0, 1, []),
            'bak https://youtu.be/abc123 çok komik': (11, 1, 1, ['komik']),
            'x.com/someone/status/123': (0, 0, 1, []),
            'www.google.com': (0, 0, 1, []),
            'google.com adresine bak': (11, 1, 1, ['adresine']),
            'puan 3.5/10 verdim': (16, 1, 0, ['puan', 'verdim']),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                stats = get_message_stats(text)
                self.assertEqual((stats['has_text'], stats['links'], stats['words']), expected[1:])

    def test_phrases_stay_in_a_sentence_and_count_once(self):
        def phrases(text):
            return [' '.join(p) for p in get_message_stats(text)['phrases']]

        # Phrases of 2 to 6 words stay in a sentence; "ben de" alone is only function words.
        self.assertEqual(phrases('tamam. o zaman ben de geliyorum, sen de gel'),
                         ['ben de geliyorum', 'de gel', 'de geliyorum', 'o zaman ben de geliyorum',
                          'sen de gel', 'zaman ben de geliyorum'])
        # Laughter and keyboard mashes are not phrases and break one; a phrase written
        # twice in one message counts once; repeats such as "yavaş yavaş" count.
        self.assertEqual(phrases('evet evet haha ben geliyorum hahaha ben geliyorum'),
                         ['ben geliyorum', 'evet evet'])
        self.assertEqual(phrases('çok çok yavaş yavaş'),
                         ['yavaş yavaş', 'çok yavaş', 'çok yavaş yavaş', 'çok çok yavaş', 'çok çok yavaş yavaş'])
        self.assertEqual(phrases('asjdkasjd ne diyorsun'), ['ne diyorsun'])
        self.assertEqual(phrases('chat_stats.pdf • 5 sayfa belge dahil edilmedi'), [])
        # A tag with a word is a phrase; tags alone are not.
        self.assertEqual(phrases('@\u2068Bora Büke\u2069 kardeş'), ['@BoraBüke kardeş'])
        self.assertEqual(phrases('@\u2068Ali\u2069 @\u2068Veli\u2069'), [])

    def test_maximal_phrases(self):
        counts = Counter({
            ('doğum', 'günün'): 45, ('günün', 'kutlu'): 45, ('kutlu', 'olsun'): 100,
            ('doğum', 'günün', 'kutlu'): 45, ('günün', 'kutlu', 'olsun'): 45,
            ('doğum', 'günün', 'kutlu', 'olsun'): 45,
            ('bayramın', 'kutlu', 'olsun'): 40, ('nadir', 'kalıp'): 2,
        })
        # The parts of "doğum günün kutlu olsun" go; "kutlu olsun" stays, as no single longer
        # phrase holds most of its uses. Phrases in fewer than 3 messages go too.
        self.assertEqual(maximal_phrases(counts), Counter({
            ('doğum', 'günün', 'kutlu', 'olsun'): 45, ('bayramın', 'kutlu', 'olsun'): 40, ('kutlu', 'olsun'): 100,
        }))

    def test_link_sites(self):
        cases = {
            'https://www.youtube.com/watch?v=1 ve https://youtu.be/2': ['YouTube', 'YouTube'],
            'https://x.com/a/status/1 https://twitter.com/b https://t.co/c': ['X', 'X', 'X'],
            'https://open.spotify.com/track/1?si=2': ['Spotify'],
            'https://m.youtube.com/x https://vm.tiktok.com/ZM/': ['YouTube', 'TikTok'],
            'https://www.hepsiburada.com.tr/x https://amazon.com.tr/a https://amzn.to/b':
                ['Hepsiburada', 'Amazon', 'Amazon'],
            'https://www.instagram.com/p/1 https://redd.it/a https://eksisozluk.com/x':
                ['Instagram', 'Reddit', 'Ekşi Sözlük'],
            'https://store.steampowered.com/app/1 https://steamcommunity.com/id/a': ['Steam', 'Steam'],
            'x.com/a/status/1 ve www.google.com': ['X', 'Google'],
            'https://192.168.1.1:8080/x': ['192.168.1.1'],
            'puan 3.5/10': [],
            # Google's services are named, since goo.gl alone says little.
            'https://maps.app.goo.gl/a https://www.google.com.tr/maps/@1,2 maps.google.com/?q=1':
                ['Google Haritalar'] * 3,
            'https://drive.google.com/f https://docs.google.com/document/d/1': ['Google Drive', 'Google Dokümanlar'],
            'https://forms.gle/a https://docs.google.com/forms/d/1': ['Google Formlar'] * 2,
            'https://www.google.com/search?q=x https://goo.gl/a https://googleblog.com/x':
                ['Google', 'Google', 'googleblog.com'],
            # Well-known sites by name, others by address; shorteners and group invites by what they are.
            'https://share.google/abc https://www.iddaa.com/x https://ivd.gib.gov.tr/y': ['Google', 'İddaa', 'gib.gov.tr'],
            'https://www.sahibinden.com/ilan/1 https://example.co.uk/a': ['Sahibinden', 'example.co.uk'],
            'https://bit.ly/a https://tinyurl.com/b https://chat.whatsapp.com/c https://wa.me/1':
                ['Kısa link', 'Kısa link', 'WhatsApp grup daveti', 'WhatsApp'],
        }
        for text, sites in cases.items():
            with self.subTest(text=text):
                self.assertEqual(link_sites(text), sites)

    def test_tag_table(self):
        # The second tag of Bora is written with a no-break space after the name.
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: @\u2068Bora\u2069 @\u2068Bora\u00a0\u2069 gel @\u2068Can\u2069\n'
            '[1.10.2026 10:01:00] Ayşe: @\u2068Bora\u2069 naber @\u2068Meta AI\u2069\n'
            '[1.10.2026 10:02:00] Bora: @\u2068Ayşe\u2069 @\u2068Bora\u2069 geldim @\u2068herkes\u2069\n'
            '[1.10.2026 10:03:00] Can: selam\n'
        )
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML'):
            root = Path(directory)
            compute_stats(df, output_file=root / 'r.pdf', markdown_output=root / 'r.md')
            text = (root / 'r.md').read_text(encoding='utf-8')
        # Bora twice in one message counts once; tagging oneself or Meta AI does not count.
        self.assertIn('**Etiketleme**\n\n| Kişi | Etiketleme | Etiketlenme | 1. | 2. |\n'
                      '|---|---:|---:|---|---|\n'
                      '| Ayşe | 3 | 1 | Bora 2 | Can 1 |\n'
                      '| Bora | 2 | 2 | Ayşe 1 | Herkes 1 |\n'
                      '| Can | 0 | 1 |  |  |\n'
                      '| Toplam | 5 | 4 |  |  |', text)

    def test_link_kinds(self):
        cases = {
            'https://www.youtube.com/watch?v=1': 'Video', 'https://youtu.be/1': 'Video',
            'https://youtube.com/shorts/1': 'Kısa video', 'https://www.instagram.com/reel/1': 'Kısa video',
            'https://vm.tiktok.com/ZM/': 'Kısa video', 'https://www.instagram.com/p/1': 'Gönderi',
            'https://x.com/a/status/1': 'Gönderi', 'https://twitter.com/a/status/1': 'Gönderi',
            'https://www.reddit.com/r/a/comments/1/b': 'Gönderi', 'https://open.spotify.com/track/1': 'Müzik',
            'https://music.youtube.com/watch?v=1': 'Müzik', 'https://maps.app.goo.gl/a': 'Harita',
            'https://www.instagram.com/someone': None, 'https://www.trendyol.com/x': None,
        }
        for link, kind in cases.items():
            with self.subTest(link=link):
                self.assertEqual(link_kind(link), kind)

    def test_content_kind_table(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: https://youtu.be/1 ve https://youtube.com/shorts/2\n'
            '[1.10.2026 10:01:00] Bora: https://open.spotify.com/track/1\n'
            '[1.10.2026 10:02:00] Ayşe: https://www.youtube.com/watch?v=3 https://www.trendyol.com/x\n'
        )
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML'):
            root = Path(directory)
            compute_stats(df, output_file=root / 'r.pdf', markdown_output=root / 'r.md')
            text = (root / 'r.md').read_text(encoding='utf-8')
        # Columns by use, people by how many typed links they shared; the shop link has no kind.
        self.assertIn('**İçerik türü**\n\n| Kişi | Toplam | Video | Kısa video | Müzik |\n|---|---:|---:|---:|---:|\n'
                      '| Ayşe | 3 | 2 | 1 | 0 |\n| Bora | 1 | 0 | 0 | 1 |\n| Toplam | 4 | 2 | 1 | 1 |', text)

    def test_link_section_lists_top_sites_overall_and_per_person(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: https://www.youtube.com/watch?v=1\n'
            '[1.10.2026 10:01:00] Bora: https://x.com/a/status/1 bak\n'
            '[1.10.2026 10:02:00] Ayşe: https://youtu.be/2 ve https://open.spotify.com/track/1\n'
            '[1.10.2026 10:03:00] Can: selam\n'
        )
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML'):
            root = Path(directory)
            compute_stats(df, output_file=root / 'r.pdf', markdown_output=root / 'r.md')
            text = (root / 'r.md').read_text(encoding='utf-8')
        section = text[text.index('## Linkler'):]
        self.assertIn('| Kişi | Link | 1. | 2. | 3. |\n|---|---:|---|---|---|\n'
                      '| Ayşe | 3 | YouTube 2 | Spotify 1 |  |\n'
                      '| Bora | 1 | X 1 |  |  |\n'
                      '| Toplam | 4 | YouTube 2 | Spotify 1 | X 1 |', section)
        self.assertNotIn('| Can |', section)
        # No links, no section.
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML'):
            root = Path(directory)
            compute_stats(self.parse('[1.10.2026 10:00:00] Can: selam\n'), output_file=root / 'r.pdf',
                          markdown_output=root / 'r.md')
            self.assertNotIn('## Linkler', (root / 'r.md').read_text(encoding='utf-8'))

    def test_laughter_styles(self):
        cases = {
            'hahaha jajaja': ('haha',), 'hehe hihi': ('hehe / hihi',), 'hohoho ohhohoh': ('hoho',),
            'sksk': ('Random',), 'jsjsjs': ('Random',), 'asdasd': ('Random',), 'asjdkasjd': ('Random',),
            'ksksks asjdkasjd': ('Random',), 'zaaa': ('za',), 'xD': ('xd',), 'lol lmao': ('lol',),
            'xd lol': ('xd', 'lol'), ':D': (':D / :d',), ':d': (':D / :d',), '😁': ('Emoji',), '😅': ('Emoji',),
            'haha 😂 :D': ('haha', ':D / :d', 'Emoji'), ':) :P': (),
            # Smiles are not laughter.
            '🙂 😊 🙃 😇 ☺️': (),
        }
        for text, styles in cases.items():
            with self.subTest(text=text):
                self.assertEqual(style_flags(text)['laugh_styles'], styles)
                self.assertEqual(style_flags(text)['laugh'], int(bool(styles)))

    def test_laughter_styles_table(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: hahaha 😂\n'
            '[1.10.2026 10:01:00] Ayşe: haha\n'
            '[1.10.2026 10:02:00] Bora: ksksks\n'
            '[1.10.2026 10:03:00] Can: selam\n'
        )
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML'):
            root = Path(directory)
            compute_stats(df, output_file=root / 'r.pdf', markdown_output=root / 'r.md')
            text = (root / 'r.md').read_text(encoding='utf-8')
        # Only styles someone used; the person who laughs most first.
        self.assertIn('**Gülme**\n\n| Kişi | Gülme oranı | Gülme | haha | Random | Emoji |\n'
                      '|---|---:|---:|---:|---:|---:|\n| Ayşe | %100,0 | 2 | 2 | 0 | 1 |\n'
                      '| Bora | %100,0 | 1 | 0 | 1 | 0 |\n| Can | %0,0 | 0 | 0 | 0 | 0 |\n'
                      '| Toplam | %75,0 | 3 | 2 | 1 | 1 |', text)

    def test_sorted_laughter_styles_links_in_media_and_emojis_once_per_message(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: haha\n'
            '[1.10.2026 10:01:00] Bora: 😂😂😂 xd\n'
            '[1.10.2026 10:02:00] Bora: 😂 xd https://x.com/a\n'
            '[1.10.2026 10:03:00] Bora: xd \u200egörüntü dahil edilmedi\n'
        )
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML'):
            root = Path(directory)
            compute_stats(df, output_file=root / 'r.pdf', markdown_output=root / 'r.md')
            text = (root / 'r.md').read_text(encoding='utf-8')
        # Bora laughs most; xd is used most, then Emoji, then haha.
        self.assertIn('| Kişi | Gülme oranı | Gülme | xd | Emoji | haha |\n|---|---:|---:|---:|---:|---:|\n'
                      '| Bora | %100,0 | 3 | 3 | 2 | 0 |\n| Ayşe | %100,0 | 1 | 0 | 0 | 1 |', text)
        # Only kinds someone shared, most shared first; links are a kind of share.
        self.assertIn('**Paylaşımlar**\n\n| Kişi | Toplam | Görsel | Link |\n|---|---:|---:|---:|\n'
                      '| Bora | 2 | 1 | 1 |\n| Ayşe | 0 | 0 | 0 |\n| Toplam | 2 | 1 | 1 |', text)
        # 😂😂😂 in one message counts once.
        self.assertIn('| Bora | %66,7 | 2 | 😂 2 |', text)

    def test_words_count_once_per_message_and_tables_sort_by_rate(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: güzel güzel güzel\n'
            '[1.10.2026 10:01:00] Ayşe: güzel mi?\n'
            '[1.10.2026 10:02:00] Ayşe: tamam\n'
            '[1.10.2026 10:03:00] Bora: haha nasıl?\n'
        )
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML'):
            root = Path(directory)
            compute_stats(df, output_file=root / 'r.pdf', markdown_output=root / 'r.md')
            text = (root / 'r.md').read_text(encoding='utf-8')
        # "güzel" is in two messages, though written four times.
        self.assertIn('| güzel | 2 |', text)
        # Bora asks and laughs in every message (100%), Ayşe in one of three: Bora first.
        self.assertIn('| Bora | %100,0 | 1 | 0 |\n| Ayşe | %33,3 | 1 | 0 |', text)
        self.assertIn('| Bora | %100,0 | 1 | 1 |\n| Ayşe | %0,0 | 0 | 0 |', text)

    def test_emoji_and_link_tables_list_the_heaviest_user_first(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: selam 😂😂😂😂\n'
            '[1.10.2026 10:01:00] Ayşe: naber\n'
            '[1.10.2026 10:02:00] Ayşe: https://x.com/a\n'
            '[1.10.2026 10:03:00] Bora: 😂 https://x.com/b https://youtu.be/c\n'
            '[1.10.2026 10:04:00] Bora: 👍\n'
        )
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML'):
            root = Path(directory)
            compute_stats(df, output_file=root / 'r.pdf', markdown_output=root / 'r.md')
            text = (root / 'r.md').read_text(encoding='utf-8')
        # Ayşe writes more messages, but Bora has more messages with an emoji and links.
        # Ayşe's four emojis are in one message; Bora has two messages with an emoji.
        # The most used emojis are in the same row, one column per rank.
        # Only as many rank columns as the chat fills: two emojis, two columns.
        self.assertIn('**Emoji**\n\n| Kişi | Emoji oranı | Emoji | 1. | 2. |\n|---|---:|---:|---|---|\n'
                      '| Bora | %100,0 | 2 | 👍 1 | 😂 1 |\n'
                      '| Ayşe | %50,0 | 1 | 😂 1 |  |\n'
                      '| Toplam | %75,0 | 3 | 😂 2 | 👍 1 |', text)
        self.assertNotIn('En çok kullanılan emojiler', text)
        links = text[text.index('## Linkler'):text.index('## Zaman')]
        self.assertLess(links.index('| Bora |'), links.index('| Ayşe |'))

    def test_location_shares_are_not_links_or_text(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: \u200eKonum: https://maps.google.com/?q=41.0,29.0\n'
            '[1.10.2026 10:01:00] Ayşe: konum: evdeyim\n'
            '[1.10.2026 10:02:00] Bora: https://maps.app.goo.gl/x\n'
        )
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML'):
            root = Path(directory)
            compute_stats(df, output_file=root / 'r.pdf', markdown_output=root / 'r.md')
            text = (root / 'r.md').read_text(encoding='utf-8')
        # One WhatsApp location share; a typed "konum:" is a message and a shared map is a link.
        self.assertIn('| Kişi | Toplam | Konum | Link |', text)
        self.assertIn('| Ayşe | 1 | 1 | 0 |', text)
        self.assertIn('| Bora | 1 | 0 | 1 |', text)
        # Only "konum: evdeyim" is written text; the share's ?q= link is not a question.
        self.assertIn('**Sorular**\n\n| Kişi | Soru oranı | Soru | Yalnız ? |\n|---|---:|---:|---:|\n'
                      '| Ayşe | %0,0 | 0 | 0 |\n| Toplam | %0,0 | 0 | 0 |', text)

    def test_cli_date_range_and_failure_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / 'chat.txt', root / 'report.pdf'
            source.write_text(
                '[1.10.2026 10:00:00] Ayşe: Merhaba\n'
                '[2.10.2026 10:00:00] Bora: Selam\n'
                '[3.10.2026 10:00:00] Ayşe: Görüşürüz\n',
                encoding='utf-8',
            )
            cases = [
                (['--start-date', '02.10.2026', '--end-date', '02.10.2026'], 0, 1),
                (['--start-date', '03.10.2026', '--end-date', '01.10.2026'], 1, None),
                (['--start-date', '05.10.2026'], 1, None),
                (['--end-date', '2026-10-01'], 1, None),
            ]
            for options, code, rows in cases:
                with self.subTest(options=options), patch('ChatStatsForWhatsApp.compute_stats', return_value=True) as compute, \
                        patch.object(sys, 'argv', ['app', str(source), '--output', str(output), *options]), \
                        redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as errors:
                    self.assertEqual(main(), code)
                    if rows is None:
                        compute.assert_not_called()
                        self.assertTrue(errors.getvalue())
                    else:
                        self.assertEqual(len(compute.call_args.args[0]), rows)


    def test_cli_min_messages_leaves_out_people_after_the_date_filter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / 'chat.txt', root / 'report.pdf'
            source.write_text(
                '[1.10.2026 10:00:00] Ayşe: a\n'
                '[2.10.2026 10:00:00] Ayşe: b\n'
                '[2.10.2026 10:01:00] Bora: c\n'
                '[3.10.2026 10:00:00] Ayşe: d\n'
                '[3.10.2026 10:01:00] Bora: e\n',
                encoding='utf-8',
            )
            cases = [
                (['--min-messages', '3'], 0, ['Ayşe'], ['Bora']),
                (['--min-messages', '2', '--start-date', '02.10.2026'], 0, ['Ayşe', 'Bora'], []),
                (['--min-messages', '3', '--start-date', '02.10.2026'], 1, None, None),
                (['--min-messages', '0'], 2, None, None),
            ]
            for options, code, kept, left_out in cases:
                with self.subTest(options=options), patch('ChatStatsForWhatsApp.compute_stats', return_value=True) as compute, \
                        patch.object(sys, 'argv', ['app', str(source), '--output', str(output), *options]), \
                        redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    try:
                        result = main()
                    except SystemExit as exit:
                        result = exit.code
                    self.assertEqual(result, code)
                    if kept is None:
                        compute.assert_not_called()
                    else:
                        self.assertEqual(sorted(compute.call_args.args[0]['user'].unique()), kept)
                        self.assertEqual(compute.call_args.kwargs['excluded_senders'], left_out)

    def test_report_names_people_below_the_threshold(self):
        df = self.parse('[1.10.2026 10:00:00] Ayşe: merhaba\n')
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML'):
            root = Path(directory)
            compute_stats(df, output_file=root / 'r.pdf', markdown_output=root / 'r.md',
                          min_messages=2000, excluded_senders=['Bora', 'Can'])
            text = (root / 'r.md').read_text(encoding='utf-8')
        self.assertIn('2.000 mesajın altında kalan 2 kişi rapora dahil edilmedi: Bora, Can', text)

if __name__ == '__main__':
    unittest.main()
