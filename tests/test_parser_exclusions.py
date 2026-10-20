import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

from ChatStatsForWhatsApp import parse_chat, compute_stats, main


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
        for chat_type, visible in [('auto', True), ('group', False), ('direct', True)]:
            with self.subTest(chat_type=chat_type), patch('ChatStatsForWhatsApp.HTML') as html:
                self.assertTrue(compute_stats(df, chat_type=chat_type))
                rendered = html.call_args.kwargs['string']
                self.assertEqual('📞 Arama İstatistikleri' in rendered, visible)
                self.assertIn('Kullanıcı İstatistikleri', rendered)
        df.attrs['is_group_chat'] = True
        with patch('ChatStatsForWhatsApp.HTML') as html:
            self.assertTrue(compute_stats(df))
            self.assertNotIn('📞 Arama İstatistikleri', html.call_args.kwargs['string'])

    def test_sample_and_custom_output_paths(self):
        sample = Path(__file__).resolve().parents[1] / 'examples/sample_chat.txt'
        df = parse_chat(sample)
        self.assertTrue(df.attrs['is_group_chat'])
        self.assertEqual(set(df['user']), {'Ayşe', 'Deniz', 'Ekin'})
        with tempfile.TemporaryDirectory() as directory, patch('ChatStatsForWhatsApp.HTML') as html:
            output = Path(directory) / 'sample.pdf'
            markdown = Path(directory) / 'sample.md'
            self.assertTrue(compute_stats(df, output_file=output, markdown_output=markdown))
            self.assertEqual(html.return_value.write_pdf.call_args.args[0], str(output))
            text = markdown.read_text(encoding='utf-8')
            self.assertNotIn('Arama İstatistikleri', text)
            self.assertNotIn('base64', text)
            self.assertIn('| Kullanıcı | Ort. Harf', text)
            self.assertNotIn('|\n\n|', text)

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


if __name__ == '__main__':
    unittest.main()
