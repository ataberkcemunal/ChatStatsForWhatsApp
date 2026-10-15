# WhatsApp Chat Stats 📊

[![Python](https://img.shields.io/badge/python-3.11–3.14-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · Türkçe

Türkçe WhatsApp sohbet dışa aktarımlarından PDF ve isteğe bağlı Markdown raporu üretir. Mesajları, kelimeleri, emojileri, medyayı ve zamana göre etkinliği analiz eder. Kaynak sohbet dosyasını değiştirmez.

## Hızlı başlangıç

Proje klasöründe terminal açın. İlk kullanımda kurulumu yapın; sonraki kullanımlarda yalnızca çalıştırma komutu yeterlidir:

```bash
./setup.sh
./run.sh examples/sample_chat.txt --output sample_report.pdf
```

Bu örnek tamamen kurgu bir sohbeti analiz eder. Kendi sohbetinizi `_chat.txt` adıyla proje klasörüne koyduğunuzda `./run.sh` kullanın. Sonuç varsayılan olarak `chat_stats.pdf` dosyasına yazılır.

## Kurulum

Python **3.11–3.14** gerekir. Yerel doğrulama Python 3.14 ile yapılmıştır; GitHub Actions dört sürüm için tanımlanmıştır. İlk kurulumda paket indirmek için internet bağlantısı gerekir. Doğrudan bağımlılıklar `requirements.txt` içinde sabittir; alt bağımlılıklar pip tarafından çözülür.

Projeyi indirin veya klonlayın:

```bash
git clone https://github.com/ataberkcemunal/ChatStatsForWhatsApp.git
cd ChatStatsForWhatsApp
```

Klasör yolunuz boşluk içeriyorsa `cd "/projenin/bulunduğu/klasör"` biçiminde tırnak kullanın.

### macOS

Python ve [Homebrew](https://brew.sh) kurulu olmalıdır. Terminalde `python3 --version` ve `brew --version` ile kontrol edebilirsiniz.

```bash
./setup.sh
```

Başlatıcı eksikse Pango'yu Homebrew ile kurar, `.venv` oluşturur ve Python paketlerini bu ortama yükler. Önce mevcut `.venv` kullanılır. Ortam yoksa desteklenen bir `python3`, ardından `python3.14`, `python3.13`, `python3.12` veya `python3.11` aranır.

Sanal ortamı elle etkinleştirmeniz gerekmez. `.venv` adındaki nokta klasörü gizli yapar. Pango sistem kütüphaneleri Homebrew altında tutulur; `run.sh` bunların yolunu ayarlar.

### Linux

Önce dağıtımınıza uygun Pango sistem paketlerini kurun, ardından `./setup.sh` çalıştırın. Paket adları dağıtıma göre değişir; [WeasyPrint kurulum belgesine](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#linux) bakın.

### Windows (PowerShell)

Python 3.11–3.14 kurun ve `python` komutunun çalıştığını kontrol edin. [MSYS2](https://www.msys2.org/) kurduktan sonra **MSYS2 UCRT64** terminalinde Pango'yu yükleyin:

```bash
pacman -S mingw-w64-ucrt-x86_64-pango
```

MSYS2 terminalini kapatın. Proje klasöründe PowerShell açıp çalıştırın:

```powershell
.\setup.ps1
.\run.ps1 examples/sample_chat.txt --output sample_report.pdf
```

Varsayılan kütüphane yolu `C:\msys64\ucrt64\bin` değeridir. Farklı kurulumda her yeni PowerShell oturumunda uygun yolu belirtin:

```powershell
$env:WEASYPRINT_DLL_DIRECTORIES = 'D:\msys64\ucrt64\bin'
```

Adımlar [WeasyPrint'in Windows belgesini](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows) temel alır. Windows çalıştırması yerelde doğrulanmamıştır; CI yalnızca PowerShell sözdizimini kontrol eder. Betikler engellenirse bilgisayarınızın betik çalıştırma politikasını izleyin.

Aşağıdaki örneklerde Windows için `./run.sh` yerine `.\run.ps1` kullanın; seçenekler aynıdır.

## Sohbet dosyasını hazırlama

WhatsApp'ta sohbeti **medya olmadan** dışa aktarın. Arşiv olarak gelirse `.txt` dosyasını çıkarıp proje klasörüne kopyalayın. Varsayılan ad `_chat.txt` olsa da başka bir dosya adı verebilirsiniz.

Desteklenen UTF-8 düz metin biçimi:

```text
[1.10.2026 10:30:00] Ayşe: Merhaba
[1.10.2026 10:31:05] Deniz: Selam
```

Çok satırlı mesajlar desteklenir. Farklı dil, tarih veya dışa aktarım biçimleri doğrudan tanınmayabilir. Medya içeriği okunmaz; sayılar “görüntü dahil edilmedi” gibi metin işaretlerinden çıkarılır.

## Kullanım

Komutları proje klasöründe çalıştırın:

| Amaç | Komut |
|---|---|
| Varsayılan `_chat.txt` dosyasını analiz et | `./run.sh` |
| Başka dosya seç | `./run.sh sohbet.txt` |
| Boşluk içeren dosya adı kullan | `./run.sh "Aile Sohbeti.txt"` |
| Başlangıç tarihi belirt | `./run.sh --start-date 01.10.2026` |
| Başlangıç tarihi ve saati belirt | `./run.sh --start-date "01.10.2026 18:30:00"` |
| Grup sohbetini açıkça belirt | `./run.sh --chat-type group` |
| Birebir sohbeti açıkça belirt | `./run.sh --chat-type direct` |
| PDF'yi farklı adla kaydet | `./run.sh --output raporum.pdf` |
| Ek Markdown metni oluştur | `./run.sh --markdown-output raporum.md` |
| Yardım al | `./run.sh --help` |

Seçenekler birlikte kullanılabilir:

```bash
./run.sh "Aile Sohbeti.txt" --chat-type group --start-date 01.10.2026 --output aile.pdf
```

Tarih biçimi `GG.AA.YYYY`, saatli biçim `GG.AA.YYYY SS:DD:SS` şeklindedir. Başlangıç anı dahil edilir; bitiş tarihi seçeneği yoktur. Göreli yollar proje klasörüne göredir. Proje dışındaki dosya için `./run.sh "/tam/yol/sohbet.txt"` kullanabilirsiniz.

Başarıyla tamamlanınca `PDF report generated: chat_stats.pdf` mesajı görünür; farklı çıktı adı verdiyseniz mesajda o yol gösterilir. PDF'yi açarak raporu inceleyin.

Varsayılan PDF'nin üzerine yazılır. Önceki raporu korumak için `--output` kullanın. Girdi, PDF ve Markdown yolları farklı olmalı; hedef klasörler önceden bulunmalıdır. Markdown metninde grafiklerin yerine açıklama bulunur; grafikler PDF'dedir.

VS Code'da **Terminal → Run Build Task** ile de rapor oluşturabilirsiniz (`Cmd+Shift+B`, macOS).

## Grup ve birebir sohbetler

Varsayılan `--chat-type auto`, grup sistem bildirimleri veya ikiden fazla katılımcı varsa sohbeti grup olarak algılar. Tür, tarih filtresinden önce belirlenir. Eksik dışa aktarımlarda veya iki kişinin yazdığı gruplarda türü `group` ya da `direct` ile açıkça belirtin.

- **Grup:** Arama İstatistikleri tablosu gösterilmez.
- **Birebir:** Arama kaydı varsa tablo gösterilir. Durumlar dışa aktaran hesabın kayıtlarına dayanır. “Cevaplanan”, toplam aramadan cevapsız kayıtların çıkarılmasıdır; kimin cevapladığını kanıtlamaz.

Tablonun gizlenmesi, diğer gönderenlere ait arama kayıtlarını bütün sayımlardan kaldırmaz. Arama kayıtları mesaj toplamlarına dahil olabilir; tanınan arama durum ifadeleri kelime ve kelime kombinasyonu analizinde temizlenir.

## Raporu okuma

| Bölüm | İçerik |
|---|---|
| Sohbet Zaman Çizelgesi | Analize dahil edilen ilk ve son kaydın zamanı |
| Kullanıcı İstatistikleri | Kişi başına mesaj, ortalama karakter, medya, emoji, bağlantı, anket ve silinen mesaj sayıları |
| Arama İstatistikleri | Yalnızca birebir sohbetlerde arama kaydı varsa sesli/görüntülü arama ve durum sayıları |
| Detaylı Medya İstatistikleri | Çıkartma, resim, video, ses, belge, GIF ve konum dağılımı |
| Kelimeler ve Kombinasyonlar | Genel ve kişi bazında sık kelimeler, ikili ve üçlü ifadeler |
| Emoji İstatistikleri | Emoji kullanımı varsa kişi bazında en sık kullanılan emojiler |
| Zamansal İstatistikler | Gün, saat ve ay dağılımları; en aktif 10 gün |
| Kullanıcı Etkinlik Zaman Çizelgesi | Aktif günler, katılım oranı ve aktif gün başına mesaj |

- **Mesajlar:** Filtrelerden sonra kalan kayıt sayısı; medya ve silinen mesaj kayıtları dahil olabilir.
- **Ort. Harf:** Boşluklar çıkarıldıktan sonra mesaj başına ortalama karakter; noktalama ve semboller de dahil olabilir.
- **Aktif gün:** Kişinin en az bir kaydının bulunduğu gün.
- **Toplam sohbet günü:** En az bir kaydın bulunduğu farklı günler; aradaki sessiz takvim günleri sayılmaz.
- **Katılım oranı:** Kişinin aktif gün sayısı / toplam sohbet günü; mesaj payı değildir.
- **Aktif gün başına mesaj:** Kişinin toplam mesajı / kendi aktif gün sayısı.

Tarih filtresi kullanılırsa ölçümler yalnızca seçilen dönemi kapsar.

### Otomatik filtreler

Göndereni **“Siz”** veya **“Meta AI”** olan kayıtlar, “Siz” aramaları dahil, tüm analizden çıkarılır. Görünmez gönderen biçimlendirmeleri temizlenir; başka kişilerin mesajlarında bu adların geçmesi mesajı elemez.

Tanınan grup ve sistem bildirimleri çıkarılır; düzenleme işaretleri temizlenir. Silinen mesajlar işaretlerinden sayılır, özgün içerik geri getirilemez. “Siz” gerçek bir kişiyle eşleştirilmez; farklı yazılmış adlar otomatik birleştirilmez.

## Örnek veri ve rapor

[examples/sample_chat.txt](examples/sample_chat.txt) tamamen kurgu bir kitap kulübü sohbetidir. [SAMPLE_REPORT.md](SAMPLE_REPORT.md) bu dosyadan üretilmiştir. Grup örneğinde arama tablosu yoktur. Örneği yeniden üretmek için:

```bash
./run.sh examples/sample_chat.txt --output sample_report.pdf --markdown-output SAMPLE_REPORT.md
```

## Sorun giderme

| Durum | Çözüm |
|---|---|
| `Python ortamı bulunamadı` | `./setup.sh` çalıştırın; Windows'ta `.\setup.ps1` kullanın. |
| `Sohbet dosyası okunamadı` | Adı, yolu, okuma iznini ve UTF-8 kodlamasını kontrol edin; boşluk içeren yolları tırnak içine alın. |
| `No messages found for the given criteria.` | Satır biçimini ve tarih filtresinden sonra kayıt kalıp kalmadığını kontrol edin. |
| Pango, `libgobject` veya WeasyPrint hatası | macOS'ta `brew install pango` ve `./run.sh`; Windows'ta MSYS2 Pango kurulumunu ve DLL yolunu kontrol edin. |
| `ModuleNotFoundError` | Kurulum başlatıcısıyla paketleri yeniden yükleyin. |
| `.sh` dosyasında `Permission denied` | `sh setup.sh` veya `sh run.sh` kullanın. |
| Grup raporunda arama tablosu var | `--chat-type group` ile yeniden üretin. |
| PDF üretim hatası | Terminal hatasını ve oluşmuşsa `debug_output.html` dosyasını inceleyin. |

İlk grafik için yazı tipi önbelleği hazırlanması zaman alabilir. Kayıt bulunmazsa veya PDF üretimi başarısızsa eski PDF klasörde kalabilir; başarı mesajını ve dosyanın değiştirilme tarihini kontrol edin.

## Veriler ve paylaşım

Analiz yereldir; uygulama sohbeti bir analiz servisine göndermez. Kurulumda paket indirilmesi ayrı bir işlemdir. PDF adları, kullanılan ifadeleri ve etkinlik bilgilerini içerir; paylaşmadan önce içeriği kontrol edin.

`.gitignore`, varsayılan `_chat.txt`, `chat_stats.pdf` ve `sample_report.pdf` dosyalarını dışarıda tutar. Başka adlı sohbet ve çıktılar otomatik korunmaz. `.gitignore` klasörü elle ZIP'lerken filtre uygulamaz.

Paylaşım için yalnızca açıkça listelenmiş proje dosyalarını alan ZIP aracını kullanın:

```bash
.venv/bin/python tools/build_release.py
```

Windows:

```powershell
.venv\Scripts\python.exe tools/build_release.py
```

Çıktı `dist/ChatStatsForWhatsApp.zip` dosyasıdır. Kod, belgeler, testler ve kurgu örnek dahil edilir; özel sohbetler, raporlar, sanal ortamlar ve önbellekler alınmaz. Bu bir kaynak kod paketidir; alıcı yine kurulum yapar.

`.venv` silinirse kurulumla yeniden oluşturulmalıdır. `__pycache__` klasörleri yeniden üretilebilen Python önbellekleridir.

## Testler ve katkı

Test komutları ve geliştirme adımları [CONTRIBUTING.md](CONTRIBUTING.md) dosyasındadır. GitHub Actions, Ubuntu'da Python 3.11–3.14 için testleri, örnek PDF üretimini ve ZIP oluşturmayı çalıştıracak şekilde tanımlanmıştır. Windows işi PowerShell sözdizimini kontrol eder. Uzak sonuçlar değişiklikler GitHub'a gönderildikten sonra görülebilir.

## Lisans

[MIT](LICENSE). [Ataberk Cem Ünal](https://github.com/ataberkcemunal) tarafından geliştirilmiştir.
