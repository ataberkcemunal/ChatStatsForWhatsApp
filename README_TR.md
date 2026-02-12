# WhatsApp Chat Stats 📊

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Dil: Türkçe](https://img.shields.io/badge/Dil-T%C3%BCrk%C3%A7e-blue.svg)](https://github.com/ataberkcemunal/ChatStatsForWhatsApp)

WhatsApp sohbet dışa aktarımları için kapsamlı bir analiz aracı. Ham sohbet kayıtlarınızı; detaylı istatistikler, zamansal analizler ve doğal dil içgörüleri içeren profesyonel bir PDF raporuna dönüştürün.

---

## ✨ Temel Özellikler

### 👥 Kullanıcı Analizleri
- **Mesaj Metrikleri**: Katılımcı başına toplam mesaj, kelime ve harf sayıları.
- **Etkileşim Analizi**: Katılım oranları ve aktif gün başına ortalama mesaj sayısı.
- **Medya Takibi**: Çıkartma, Resim, Video, Ses, Belge, GIF ve Konum bazlı detaylı kırılım.

### 📝 Metin Analizi
- **Gelişmiş Belirteçleme**: WhatsApp @etiketlerinin (mentions) tek bir birim olarak (örn: `@Kullanıcı`) akıllıca işlenmesi.
- **N-Gram Analizi**: En sık kullanılan ikili ve üçlü kelime kombinasyonlarını keşfederek ortak kalıpları belirleme.
- **Emoji İstatistikleri**: Her kullanıcının en favori ve en sık kullandığı emojiler.
- **Kelime Frekansı**: Genel ve kullanıcı bazlı en çok kullanılan kelimeler (anlamlı sonuçlar için filtrelenmiş).

### ⏰ Zamansal İstatistikler
- **Aktivite Haritası**: Günün saatlerine ve haftanın günlerine göre mesaj trafiği analizi.
- **Aylık Trendler**: Sohbetin aylar içindeki gelişimini takip edin.
- **Zirve Günler**: Sohbet geçmişindeki en aktif 10 günü belirleyin.

### 🛡️ Akıllı Ayrıştırma ve Temizleme
- **Güçlü Regex**: "Düzenlendi" ve "Silindi" ibarelerini istatistiklerden otomatik olarak filtreler.
- **Sistem Mesajı Tespiti**: Grup oluşturma, isim değişiklikleri ve sistem bildirimlerini akıllıca hariç tutar.
- **Arama İstatistikleri**: Sesli, Görüntülü, Cevaplanan ve Cevapsız aramalar için doğru sayımlar.

---

## 🚀 Başlarken

### Gereksinimler
- Python 3.8 veya üzeri
- [GTK+3](https://www.gtk.org/docs/installations/macos/) (PDF oluşturma için WeasyPrint tarafından gereklidir)

### Kurulum

1. **Depoyu Klonlayın**
   ```bash
   git clone https://github.com/ataberkcemunal/ChatStatsForWhatsApp.git
   cd ChatStatsForWhatsApp
   ```

2. **Sanal Ortam Oluşturun (Önerilir)**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # macOS/Linux için
   ```

3. **Bağımlılıkları Yükleyin**
   ```bash
   pip install -r requirements.txt
   ```

### Kullanım

1. **WhatsApp sohbetinizi dışa aktarın**:
   - Mobil cihazınızda ilgili sohbeti açın.
   - **Diğer** > **Sohbeti Dışa Aktar** yolunu izleyin.
   - **Medya Olmadan** seçeneğini seçin.
   - Dışa aktarılan `.txt` dosyasını proje dizinine kaydedin (örn: `_chat.txt`).

2. **Rapor Oluşturun**:
   ```bash
   python ChatStatsForWhatsApp.py _chat.txt
   ```

3. **Sonuçları Görüntüleyin**:
   İstatistiklerinizi keşfetmek için yeni oluşturulan `chat_stats.pdf` dosyasını açın.

---

## 🎨 Tasarım Estetiği
Oluşturulan PDF raporunun özellikleri:
- **Zengin Tipografi**: Modern sans-serif fontlar kullanılarak okunabilirlik için optimize edilmiştir.
- **Yapılandırılmış Düzen**: Emoji destekli başlıklar ve temiz Markdown tarzı tablolarla düzenlenmiştir.
- **Türkçe Desteği**: Türkçe karakter setleri ve dışa aktarım formatları için tam optimize edilmiştir.

---

## 🛠️ Yapılandırma
Script tak-çalıştır şeklinde tasarlanmıştır, ancak ihtiyaç duyulması halinde farklı yerelleştirilmiş WhatsApp sürümlerine uyum sağlamak için `ChatStatsForWhatsApp.py` içindeki `MEDIA_PATTERNS` veya `group_patterns` bölümlerini kolayca değiştirebilirsiniz.

---

## 📄 Lisans
MIT Lisansı altında dağıtılmaktadır. Daha fazla bilgi için `LICENSE` dosyasına bakın.

## 🤝 Katkıda Bulunma
Katkılarınız bu projeyi daha iyi bir yer haline getirir. Katkıda bulunmak isterseniz lütfen:

1. Projeyi Forklayın
2. Özellik Dalınızı (Feature Branch) oluşturun (`git checkout -b feature/HarikaOzellik`)
3. Değişikliklerinizi Commit yapın (`git commit -m 'HarikaOzellik eklendi'`)
4. Dalınızı Pushlayın (`git push origin feature/HarikaOzellik`)
5. Bir Pull Request açın

---
❤️ [Ataberk Cem Ünal](https://github.com/ataberkcemunal) tarafından oluşturuldu.
