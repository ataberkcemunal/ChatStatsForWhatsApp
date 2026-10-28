import argparse
import io
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
    style_flags, main, parse_chat, parse_end_date,
    positive_hours,
)


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
        self.assertEqual(df['user'].tolist(), ['Ayşe', 'Meta AI Seven', 'Bora'])
        self.assertEqual(df['message'].tolist(), [
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

    def test_call_section_is_kept_for_direct_and_hidden_for_group(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: Merhaba arkadaşım\n'
            '[1.10.2026 10:01:00] Bora: Görüntülü arama, 2 dk.\n'
        )
        self.assertFalse(df.attrs['is_group_chat'])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.pdf'
            for chat_type, visible in [('auto', True), ('group', False), ('direct', True)]:
                with self.subTest(chat_type=chat_type), patch('ChatStatsForWhatsApp.HTML') as html:
                    self.assertTrue(compute_stats(df, chat_type=chat_type, output_file=output))
                    rendered = html.call_args.kwargs['string']
                    self.assertEqual('<h2>Aramalar</h2>' in rendered, visible)
                    self.assertIn('<h2>Kişiler</h2>', rendered)
            df.attrs['is_group_chat'] = True
            with patch('ChatStatsForWhatsApp.HTML') as html:
                self.assertTrue(compute_stats(df, output_file=output))
                self.assertNotIn('<h2>Aramalar</h2>', html.call_args.kwargs['string'])

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
            self.assertIn('| Kişi | Mesaj | Pay | Ort. harf |', text)
            # Header and alignment row stay together, so the table renders.
            self.assertIn('| Kişi | Mesaj | Pay | Ort. harf | Medya | Emoji | Link | Anket | Silinen |\n|---|---:|', text)

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

    def test_report_escapes_names_and_averages_only_written_text(self):
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
        # "merhaba" is 7 letters; the media placeholder is not written text.
        self.assertIn('| A\\|B &lt;i&gt; | 2 | %66,7 | 7,0 | 1 |', text)

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
        section = text[text.index('## Kendine özgü kelimeler'):]
        self.assertIn('**Ayşe**\n\n| Kelime | Kendisi | Diğerleri |\n|---|---:|---:|\n| kanka | 20 | 0 |\n| naber | 20 | 0 |\n', section)
        self.assertIn('**Bora**\n\n| Kelime | Kendisi | Diğerleri |\n|---|---:|---:|\n| hocam | 20 | 0 |\n| selam | 20 | 0 |\n', section)

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
            'peki :)': (0, 1),
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
            'tamam :P': (0, 1),
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
        only = {'?': 1, '???': 1, ' ? ? ': 1, '?!': 0, 'ne?': 0, 'naber': 0}
        for text, expected in only.items():
            with self.subTest(text=text):
                self.assertEqual(style_flags(text)['only_question_mark'], expected)

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
        self.assertIn('| Bora | 3 | 1 | %33,3 | 1 | 1 | %33,3 |', text)
        self.assertIn('| Ayşe | 2 | 2 | %100,0 | 0 | 0 | %0,0 |', text)
        self.assertIn('| Toplam | 5 | 3 | %60,0 | 1 | 1 | %20,0 |', text)
        # The media table follows the people table, before the other people tables.
        self.assertLess(text.index('**Medya**'), text.index('**Etkinlik**'))
        self.assertNotIn('## Medya', text)
        style = text[text.index('**Soru ve gülme**'):text.index('**Sohbet akışı**')]
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
                self.assertEqual((stats['letter_count'], stats['has_text'], stats['links'], stats['words']), expected)

    def test_phrases_stay_in_a_sentence_and_count_once(self):
        def phrases(text):
            stats = get_message_stats(text)
            return [' '.join(p) for p in stats['bigrams']], [' '.join(p) for p in stats['trigrams']]

        self.assertEqual(phrases('tamam. ben de geliyorum, sen de gel'),
                         (['ben de', 'de gel', 'de geliyorum', 'sen de'], ['ben de geliyorum', 'sen de gel']))
        # Laughter and keyboard mashes are not phrases and break one; a phrase written
        # twice in one message counts once; repeats such as "yavaş yavaş" count.
        self.assertEqual(phrases('evet evet haha haha ben de geliyorum hahaha ben de geliyorum'),
                         (['ben de', 'de geliyorum', 'evet evet'], ['ben de geliyorum']))
        self.assertEqual(phrases('çok çok çok çok yavaş yavaş'),
                         (['yavaş yavaş', 'çok yavaş', 'çok çok'],
                          ['çok yavaş yavaş', 'çok çok yavaş', 'çok çok çok']))
        self.assertEqual(phrases('asjdkasjd ne diyorsun'), (['ne diyorsun'], []))
        self.assertEqual(phrases('chat_stats.pdf • 5 sayfa belge dahil edilmedi'), ([], []))

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
