"""Tests for the shared parser; this file is copied together with whatsapp_chat.py."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import whatsapp_chat
from whatsapp_chat import CALL, DELETED, EXCLUDED, MESSAGE, SYSTEM, classify, read_chat

PROJECT = Path(__file__).resolve().parents[1]
SIBLINGS = ('Chat Stats for WhatsApp', 'Profanity Stats for WhatsApp')


class ReadChatTests(unittest.TestCase):
    def read(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'chat.txt'
            path.write_text(text, encoding='utf-8')
            return read_chat(path)

    def test_header_formats_bom_and_multiline_messages(self):
        chat = self.read(
            '\ufeff[1.10.2026, 10:00] Ayşe: Merhaba\n'
            'ikinci satır\n'
            '[1.10.2026 10:01:05] Bora:\n'
            'boş satırla başlayan mesaj\n'
        )
        self.assertEqual([(r.timestamp, r.sender, r.text) for r in chat.records], [
            (datetime(2026, 10, 1, 10, 0), 'Ayşe', 'Merhaba\nikinci satır'),
            (datetime(2026, 10, 1, 10, 1, 5), 'Bora', '\nboş satırla başlayan mesaj'),
        ])

    def test_timestamp_line_without_sender_ends_the_previous_message(self):
        chat = self.read(
            '[1.10.2026 10:00:00] Ayşe: Merhaba\n'
            '[1.10.2026 10:01:00] Sistem bildirimi\n'
            'bu satır kimseye eklenmemeli\n'
            '[1.10.2026 10:02:00] Bora: Selam\n'
        )
        self.assertEqual([r.text for r in chat.records], ['Merhaba', 'Selam'])

    def test_excluded_senders_and_their_continuations_are_left_out(self):
        chat = self.read(
            '[1.10.2026 10:00:00] \u200eSiz: Görüntülü arama\n'
            'devam\n'
            '[1.10.2026 10:01:00] \u200fMeta AI\u200e: bot yanıtı\n'
            '[1.10.2026 10:02:00] Meta AI Seven: Merhaba\n'
        )
        self.assertEqual([(r.sender, r.text) for r in chat.records], [('Meta AI Seven', 'Merhaba')])

    def test_record_kinds(self):
        chat = self.read(
            '[1.10.2026 10:00:00] Ayşe: \u200eBu mesaj silindi.\n'
            '[1.10.2026 10:01:00] Ayşe: \u200eCevapsız sesli arama\n'
            '[1.10.2026 10:02:00] Ayşe: Sesli arama yapalım mı?\n'
            '[1.10.2026 10:03:00] Ayşe: Merhaba <Bu mesaj düzenlendi>\n'
            '[1.10.2026 10:04:00] Ayşe: \u200eANKET:\nNe yiyelim?\n'
            '[1.10.2026 10:05:00] Ayşe: \u200eBora gruba katıldı\n'
            '[1.10.2026 10:06:00] Ayşe: Bora gruba katıldı mı?\n'
        )
        self.assertEqual([r.kind for r in chat.records], [DELETED, CALL, MESSAGE, MESSAGE, MESSAGE, MESSAGE])
        self.assertNotIn('\u200eBora gruba katıldı', [r.text for r in chat.records])

    def test_classify_without_header_marker(self):
        self.assertEqual(classify('💩', '\u200eBu grubu siz oluşturdunuz'), SYSTEM)
        self.assertEqual(classify('Ayşe', 'Bu grubu siz oluşturdunuz'), MESSAGE)
        self.assertEqual(classify('SİZ', 'Merhaba'), EXCLUDED)
        self.assertEqual(classify('Ayşe', '   '), SYSTEM)

    def test_group_detection(self):
        self.assertFalse(self.read(
            '[1.10.2026 10:00:00] Ayşe: Merhaba\n[1.10.2026 10:01:00] Bora: Selam\n'
        ).is_group_chat)
        self.assertTrue(self.read(
            '[1.10.2026 10:00:00] Ayşe: A\n[1.10.2026 10:01:00] Bora: B\n[1.10.2026 10:02:00] Can: C\n'
        ).is_group_chat)
        chat = self.read(
            '[1.10.2026 10:00:00] Aile: \u200e“Aile” grubunu oluşturdunuz\n'
            '[1.10.2026 10:01:00] Aile: Hoş geldiniz\n'
            '[1.10.2026 10:02:00] Ayşe: Merhaba\n'
        )
        self.assertTrue(chat.is_group_chat)
        self.assertEqual([r.sender for r in chat.records], ['Ayşe'])


class SharedCopyTests(unittest.TestCase):
    def test_copies_in_sibling_projects_are_identical(self):
        for sibling in SIBLINGS:
            other = PROJECT.parent / sibling
            if other.resolve() == PROJECT or not other.is_dir():
                continue
            for name in ('whatsapp_chat.py', 'report_style.py', 'tests/test_whatsapp_chat.py'):
                with self.subTest(project=sibling, file=name):
                    self.assertEqual(
                        (PROJECT / name).read_bytes(), (other / name).read_bytes(),
                        'Run Tools/sync_shared.sh in the parent folder after editing a shared file.',
                    )


if __name__ == '__main__':
    unittest.main()
