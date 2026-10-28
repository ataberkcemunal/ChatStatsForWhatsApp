import argparse
import io
import tempfile
import unittest
import sys
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from ChatStatsForWhatsApp import (
    compute_stats, conversation_stats, distinctive_words, duration, main, parse_chat, parse_end_date,
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

    def test_conversation_starts_ends_and_reply_times(self):
        df = self.parse(
            '[1.10.2026 10:00:00] Ayşe: Günaydın\n'
            '[1.10.2026 10:00:30] Ayşe: Kalktın mı?\n'
            '[1.10.2026 10:02:30] Bora: Kalktım\n'
            '[1.10.2026 10:12:30] Ayşe: Süper\n'
            # Six hours of silence: Bora opens a new conversation and Ayşe answers.
            '[1.10.2026 16:12:30] Bora: Akşam?\n'
            '[1.10.2026 16:13:15] Ayşe: Olur\n'
        )
        flow = conversation_stats(df)
        self.assertEqual(flow['conversations'], 2)
        self.assertEqual(flow['starts'].to_dict(), {'Ayşe': 1, 'Bora': 1})
        self.assertEqual(flow['ends'].to_dict(), {'Ayşe': 2})
        # Ayşe answered after 10 min and 45 s; Bora after 2 min. The gap is not a reply.
        self.assertEqual(flow['reply'].to_dict(), {'Ayşe': 322.5, 'Bora': 120.0})
        self.assertEqual(flow['reply_all'], 120.0)
        # With a longer gap the evening message is Bora's reply, not a new conversation.
        flow = conversation_stats(df, gap_hours=8)
        self.assertEqual(flow['conversations'], 1)
        self.assertEqual(flow['reply']['Bora'], (120 + 6 * 3600) / 2)

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
        self.assertIn('### Ayşe\n\n20 mesaj · %50,0 pay · 1 aktif gün\n\nKendine özgü: kanka, naber\n', text)
        self.assertIn('Kendine özgü: hocam, selam\n', text)

    def test_duration_format(self):
        for seconds, text in [(45, '45 sn'), (322.5, '5 dk'), (3600, '1 sa'), (7500, '2 sa 5 dk'),
                              (float('nan'), '–')]:
            self.assertEqual(duration(seconds), text)

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


if __name__ == '__main__':
    unittest.main()
