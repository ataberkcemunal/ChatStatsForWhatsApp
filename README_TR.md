# WhatsApp Chat Stats 📊

[![Python](https://img.shields.io/badge/python-3.11–3.14-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · Türkçe

**Türkçe** bir WhatsApp sohbet dışa aktarımından PDF rapor üretir. Raporda kimin ne kadar yazdığı, hangi kelimeleri, emojileri ve medyayı kullandığı ve sohbetin en çok ne zaman hareketlendiği yer alır. İsteğe bağlı olarak raporun Markdown kopyası da alınabilir. Her şey bilgisayarınızda çalışır ve sohbet dosyası hiçbir zaman değiştirilmez.

## Hızlı başlangıç

```bash
./setup.sh                                    # bir kez
./run.sh examples/sample_chat.txt --output sample_report.pdf
```

Bu komut kurgusal bir örnek sohbetten rapor üretir. Kendi sohbetiniz için dosyayı bu klasöre `_chat.txt` adıyla kopyalayıp `./run.sh` çalıştırın. Rapor `chat_stats.pdf` dosyasına yazılır.

Windows'ta `.\setup.ps1` ve `.\run.ps1` kullanın; aşağıdaki tüm seçenekler aynı şekilde çalışır.

## Kurulum

Python **3.11–3.14** ve PDF'i çizmek için WeasyPrint'in kullandığı Pango kütüphanesi gerekir. Kurulum, paketleri indirmek için bir kez internet bağlantısı ister.

```bash
git clone https://github.com/ataberkcemunal/ChatStatsForWhatsApp.git
cd ChatStatsForWhatsApp
```

### macOS

[Homebrew](https://brew.sh) kurun, ardından `./setup.sh` çalıştırın. Betik şunları yapar:

1. Pango eksikse Homebrew ile kurar,
2. desteklenen bir Python ile (`python3`, sonra `python3.14` … `python3.11`) `.venv` klasörünü oluşturur,
3. `requirements.txt` içinde sürümü sabitlenmiş paketleri kurar.

`.venv` ortamını elle etkinleştirmeniz gerekmez; `run.sh` onu kullanır ve WeasyPrint'e Homebrew kütüphanelerinin yerini gösterir.

### Linux

Dağıtımınızın Pango paketlerini kurun ([WeasyPrint listesi](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#linux)), ardından `./setup.sh` çalıştırın.

### Windows (PowerShell)

1. Python 3.11–3.14 ve [MSYS2](https://www.msys2.org/) kurun.
2. **MSYS2 UCRT64** terminalinde `pacman -S mingw-w64-ucrt-x86_64-pango` çalıştırın.
3. Proje klasöründe PowerShell açıp `.\setup.ps1` çalıştırın.

`run.ps1`, Pango'yu `C:\msys64\ucrt64\bin` içinde arar. MSYS2 başka bir yerdeyse önce yolu belirtin:

```powershell
$env:WEASYPRINT_DLL_DIRECTORIES = 'D:\msys64\ucrt64\bin'
```

CI; kurulumu, testleri ve örnek PDF'i Windows'ta Windows PowerShell 5.1 ve `C:\msys64` içindeki MSYS2 Pango ile çalıştırır.

## Sohbeti dışa aktarma

WhatsApp'ta sohbeti **medya olmadan** dışa aktarın. ZIP gelirse içindeki `.txt` dosyasını çıkarın. Dosya şu biçimde UTF-8 metin olmalıdır:

```text
[1.10.2026 10:30:00] Ayşe: Merhaba
[1.10.2026 10:31:05] Deniz: Selam
```

Tarihten sonra virgül ve saniyesiz saat (`[1.10.2026, 10:30]`) de kabul edilir. Birden çok satıra yayılan mesajlar desteklenir. Başka bir sohbetten yapıştırılmış satırlar (önceki mesajlardan bir günden daha eski tarihli başlıklar) yapıştırıldıkları mesajın parçası sayılır. Başka diller ve tarih biçimleri tanınmaz. Medya dosyaları okunmaz; medya “görüntü dahil edilmedi” gibi yer tutuculardan sayılır.

## Kullanım

```bash
./run.sh [sohbet_dosyası] [seçenekler]
```

| Seçenek | Anlamı | Varsayılan |
|---|---|---|
| `chat_file` | İncelenecek sohbet dosyası | `_chat.txt` |
| `--start-date`, `-s` | Yalnızca bu andan itibarenki kayıtlar (o an dahil). `GG.AA.YYYY`, `"GG.AA.YYYY SS:DD"` veya `"GG.AA.YYYY SS:DD:SS"` | tüm sohbet |
| `--end-date`, `-e` | Yalnızca bu ana kadarki kayıtlar (o an dahil). Saatsiz tarih o günün tamamını kapsar | tüm sohbet |
| `--chat-type` | `auto`, `group` veya `direct` | `auto` |
| `--conversation-gap` | Kaç saatlik sessizlikten sonraki kaydın yeni sohbet başlatacağı (ör. `0.5`) | `1` |
| `--min-messages N` | Yalnızca dönemde (tarih filtresinden sonra) en az N kaydı olan kişileri dahil et; diğerleri kişiler tablosunun altında yazılır | `1` (herkes) |
| `--output`, `-o` | PDF yolu | `chat_stats.pdf` |
| `--markdown-output` | Raporu Markdown olarak da yaz (grafikler PDF'te kalır) | kapalı |
| `--help` | Tüm seçenekleri göster | |

Örnekler:

```bash
./run.sh "Aile Sohbeti.txt"
./run.sh --start-date "20.10.2026 14:50:00" --output ekim.pdf
./run.sh --start-date 01.10.2026 --end-date 31.10.2026 --output sadece-ekim.pdf
./run.sh "/tam/yol/_chat.txt" --chat-type group --markdown-output rapor.md
```

- `run.sh` önce proje klasörüne geçer; bu yüzden göreli yollar proje klasörüne göredir. Başka yerdeki dosyalar için tam yol verin.
- Boşluk içeren yolları tırnak içine alın.
- PDF, Markdown ve sohbet yolları birbirinden farklı olmalı, çıktı klasörü önceden var olmalıdır.
- Aynı adlı eski rapor silinip yenisi yazılır. Eskisini korumak için `--output` kullanın.

Başarılı çalışma sonunda `PDF report generated: <yol>` yazılır ve çıkış kodu 0 olur. Raporlanacak mesaj yoksa, tarih geçersizse ya da PDF üretilemezse hata stderr'e yazılır ve çıkış kodu 1 olur. VS Code'da **Terminal → Run Build Task** (`Cmd+Shift+B`) `run.sh` betiğini varsayılan ayarlarla çalıştırır.

## Raporun içeriği

| Bölüm | İçerik |
|---|---|
| Özet kutuları | Mesaj, katılımcı, sohbet günü, günde ortalama mesaj, en uzun seri ve en uzun sessizlik; tarihleri altında |
| Kişiler | Kişi başına mesaj (çubukla), pay, aktif gün, katılım, aktif gün başına mesaj ve silinen mesaj, toplam satırıyla; ardından **Paylaşımlar**: kişi başına görsel, video, ses, çıkartma, GIF, belge, konum, anket ve link ile toplam (çubukla), en çok paylaşılan tür önde, kimsenin paylaşmadığı türler gizli; ardından **Aramalar** (arama varsa) aramayı başlatana göre: toplam, sesli, görüntülü ve süre, ayrıca birebir sohbetlerde cevaplanan ve cevapsız, gruplarda ortalama katılımcı sayısı; ardından başlattığı sohbet ve son söz; gruplarda kişinin en çok yanıt verdiği ve en çok yanıt aldığı kişi; ardından **Etiketleme** (@ ile etiketleme varsa): yaptığı ve aldığı etiketler (ikisi de çubukla) ve en çok etiketlediği kişiler |
| Yazış tarzı | **Sorular**: kişi başına soru (oran, sayı ve yalnızca soru işaretinden oluşan mesajlar), oranı en yüksek önde; **Gülme**: gülme içeren mesajlar (oran ve sayı) ve kişilerin gülme tarzları (haha, hehe / hihi, hoho, ksksks, sjsj ve klavye karmaşaları için Random, za, xd, lol, :D / :d, emoji), oranı en yüksek kişi ve en çok kullanılan tarz önde; **Emoji**: emoji içeren mesajlar (oran ve sayı) ve kişinin en çok kullandığı sekiz emoji sıra sütunlarında, toplam satırında sohbetin geneli. Hepsi bir mesajda bir kez sayılır ("😂😂😂" bir kez) |
| Kelimeler ve ifadeler | Üç sütunda en sık 45 kelime (4+ harf) ve iki sütunda en sık 30 ifade |
| Kişi bazında kelimeler | Her kişi için vurgulu bir bant (mesaj, pay, aktif gün) ve en sık 15 kelime ve ifade yan yana |
| Kendine özgü kelimeler ve ifadeler | Her kişinin diğerlerinden belirgin biçimde daha sık kullandığı en fazla on kelime ve on ifade; kendisinin ve diğerlerinin bunları içeren mesaj sayısıyla |
| Linkler | Kişi başına bir satır (en çok link paylaşan önde): link sayısı (çubukla) ve en çok link paylaştığı beş site sıra sütunlarında, sayısı adının altında; toplam satırında sohbetin geneli. Ardından **İçerik türü**: linkler, adresinden anlaşılan içeriğe göre (video, kısa video, gönderi, müzik, harita) |
| Zaman | Yan yana gün ve saat grafikleri; sohbet birden çok ayı kapsıyorsa ay grafiği ve kişilerin aylık mesaj payı (en çok yazan beş kişi, kalanlar "Diğer") |

Sayıların tanımları:

- **Mesaj**: Filtrelemeden sonra kalan her kayıt; medya ve silinen mesaj kayıtları dahil, aramalar hariç.
- **Konum**: WhatsApp'ın konum paylaşma özelliğiyle gönderilen konum; harita linki link sayılmaz, "konum:" yazmak konum sayılmaz.
- **Aktif gün**: Kişinin en az bir kaydı olan gün.
- **Sohbet günü**: Sohbette en az bir kayıt olan gün; sessiz günler sayılmaz.
- **En uzun seri**: Her gün en az bir kayıt olan en uzun ardışık takvim günü dizisi. **En uzun sessizlik**: İlk ve son kayıt arasında hiç kayıt olmayan en uzun ardışık gün dizisi.
- **Katılım**: Kişinin aktif günleri ÷ sohbet günü (mesaj payı değildir).
- **Aktif gün başına mesaj**: Kişinin mesajları ÷ kendi aktif gün sayısı.
- **Sohbet**: Aralarında 1 saat (`--conversation-gap` ile değiştirilebilir) veya daha uzun sessizlik olmayan kayıtlar. Böyle bir sessizlikten sonraki ilk kayıt yeni bir sohbet başlatır; sessizlikten önceki son kayıt **son söz** sayılır.
- **İfade**: Bir cümle içinde kalan, en az 3 mesajda geçen 2–6 kelimelik kalıp. Çoğunlukla daha uzun bir kalıbın içinde geçen ifade yalnızca o uzun kalıpla gösterilir (ayrıca "kutlu olsun" değil, "doğum günün kutlu olsun"). Yalnızca "ben de", "o zaman" gibi kelimelerden ya da yalnızca etiketlerden oluşanlar sayılmaz; gülmeler ifadeyi böler. Kelimeler ve ifadeler geçtikleri mesaj sayısıyla sayılır; bir mesajdaki tekrar bir kez sayılır.
- **Kendine özgü**: Kişinin sohbetin geri kalanından belirgin biçimde daha sık kullandığı en fazla on kelime ve on ifade (ağırlıklı log-odds, z > 1,96). Kısa sohbetlerde hiç çıkmayabilir.
- **Site**: Bilinen siteler adıyla (instagram.com: Instagram, sahibinden.com: Sahibinden), diğerleri adresiyle (gib.gov.tr) gösterilir. Alt adresler ve uzantılar sitesiyle birlikte sayılır (open.spotify.com ve spotify.com: Spotify), sitenin kendi kısa linkleri de (youtu.be: YouTube, t.co ve twitter.com: X). bit.ly gibi kısaltıcılar nereye gittiğini göstermediği için Kısa link sayılır; chat.whatsapp.com linkleri WhatsApp grup davetidir. Google linkleri hizmetine göre adlandırılır (goo.gl konum linkleri dahil Google Haritalar, Google Drive, Google Dokümanlar, Google Formlar, diğerleri Google). Her link ayrı sayılır; bir mesajdaki iki link iki sayılır.
- **Arama**: Aramayı başlatan kişiye sayılır, mesaj sayılmaz. Dışa aktaran kişinin başka bir cihazdan (örneğin bilgisayardan) yaptığı aramalar dışa aktarımda “Siz” olarak yazılır; bunlar dışa aktaran kişinin adına sayılır. Bu ad, yalnızca dışa aktaranın kendi sildiği mesajlarda görünen “Bu mesajı sildiniz” satırlarından bulunur; bulunamazsa “Siz” olarak kalır.
- **Etiket**: Mesajdaki @ etiketi; bir mesajda aynı kişi iki kez etiketlense de bir kez sayılır, kendini ya da Meta AI'ı etiketlemek sayılmaz. WhatsApp'ın tüm grubu çağıran etiketi Herkes olarak gösterilir.
- **Soru ve gülme**: Soru (soru işareti, gelcekmisin gibi bitişik yazılanlar dahil mi/mı/mu/mü soru eki, nasıl, neden, niye, niçin, kaç, hangi, nerede, kim gibi bir soru kelimesi ya da yalnızca "ne" olan mesaj; "ne???" de tek soru sayılır; neredeyse, neden olmak, "hangisi/kim/ne olursa olsun" ve linklerdeki ? sayılmaz) ya da gülme (haha, hehe, hohoho, jajaja, ksksks, sksksk, sjsj, hshs, kdkd, zaaa, asdf, xd, :D, 😀 😃 😄 😁 😆 😅 🤣 😂 😹 (:), :P, 🙂 😊 🙃 gibi gülümsemeler sayılmaz) ya da asjdkasjd gibi rastgele klavye yazımı: çoğu orta sıra tuşlarından yazılmış, en az altı harfli ve art arda dört orta sıra ünsüzü içeren kelime) içeren yazılı mesajlar; her mesaj bir kez sayılır, oran kişinin yazılı mesajlarına göredir. Tablo ayrıca yalnızca soru işaretinden oluşan mesajları ("?", "???") sayar; bunlar tepki sayılır, soruya dahil edilmez.
- **Kim kime yanıt veriyor**: Dışa aktarım bir mesajın hangi mesaja cevap olduğunu kaydetmez; aynı sohbette bir önceki kaydın sahibi esas alınır.

Sayılar Türkçe biçimde yazılır: binlik için `1.234`, ondalık için `12,5`, yüzde için `%45,3`.

`--start-date` veya `--end-date` verildiğinde tüm değerler yalnızca seçilen dönemi kapsar.

### Grup veya birebir sohbet

`--chat-type auto`, grup sistem olayları ya da ikiden fazla katılımcı bulursa sohbeti grup kabul eder. Bu karar tarih filtresinden önce, dosyanın tamamına bakılarak verilir. Dışa aktarım eksikse ya da grupta yalnızca iki aktif kişi varsa `group` veya `direct` seçeneğini kendiniz belirtin.

Arama tablosu farklıdır: birebir sohbette cevaplanan ve cevapsız aramalar, grupta bunların yerine ortalama katılımcı sayısı gösterilir; çünkü grupta “cevapsız” yalnızca dışa aktaran telefonun katılmadığını gösterir. Yalnızca gerçek arama kayıtları arama sayılır; “sesli arama yapalım mı?” gibi bir mesaj sayılmaz. Arama durum ifadeleri kelime analizine girmez.

### Filtrelenenler

- **“Siz”** veya **“Meta AI”** tarafından gönderilen kayıtlar; “Siz” olarak yazılan aramalar hariç (bkz. Arama). Başkalarının mesajlarında bu adların geçmesi sorun değildir; o mesajlar korunur.
- Tanınan grup ve sistem bildirimleri, boş kayıtlar ve göndereni olmayan zaman damgalı satırlar. “Düzenlendi” işaretleri metinden temizlenir.
- Adlardaki görünmez biçimlendirme karakterleri. Bölünmez boşluk, çift boşluk ya da farklı kodlanmış harflerle yazılan ad aynı ad sayılır.

Silinen mesajlar sayılır ama içerikleri geri getirilemez. Aynı kişinin iki farklı adla kaydedilmesi birleştirilmez.

## Örnek rapor

[examples/sample_chat.txt](examples/sample_chat.txt) kurgusal bir kitap kulübü grup sohbetidir; [SAMPLE_REPORT.md](SAMPLE_REPORT.md) bu sohbetten üretilen rapordur. İkisini yeniden üretmek için:

```bash
./run.sh examples/sample_chat.txt --output sample_report.pdf --markdown-output SAMPLE_REPORT.md
```

## Sorun giderme

| Mesaj veya sorun | Yapılacak |
|---|---|
| `Python environment missing` | `./setup.sh` çalıştırın (Windows: `.\setup.ps1`). |
| `Could not read chat file` | Dosya adını, yolunu, izinleri ve UTF-8 olduğunu kontrol edin. Boşluklu yolları tırnağa alın. |
| `No messages found for the given criteria.` | Satır biçimini ve `--start-date` / `--end-date` değerlerini kontrol edin. |
| Pango, `libgobject` veya WeasyPrint hatası | macOS: `brew install pango`, sonra `./run.sh` kullanın. Windows: MSYS2 Pango ve `WEASYPRINT_DLL_DIRECTORIES` değerini kontrol edin. |
| `ModuleNotFoundError` | Kurulum betiğini yeniden çalıştırın. |
| `.sh` dosyasında `Permission denied` | `sh setup.sh` / `sh run.sh` kullanın. |
| Grup raporunda arama tablosu cevaplanan ve cevapsız aramaları gösteriyor | `--chat-type group` ile yeniden çalıştırın. |
| `Error generating PDF` | Hatayı okuyun; HTML incelemek için `debug_output.html` olarak kaydedilir. Aynı adlı mevcut raporlara dokunulmaz. |

İlk çalıştırma, Matplotlib yazı tipi önbelleğini oluştururken yavaş olabilir. PDF ve Markdown dosyaları ikisi de hazır olduktan sonra birlikte değiştirilir. Çalıştırma başarısız olursa klasördeki raporlar olduğu gibi kalır; başarı mesajını ve dosyanın değiştirilme zamanını kontrol edin.

## Gizlilik ve paylaşım

Analiz yereldir; sohbetiniz hiçbir yere gönderilmez. Kurulum yalnızca paket indirir. Raporlar isimler, ifadeler ve etkinlik bilgisi içerir; paylaşmadan önce gözden geçirin.

`.gitignore`, `_chat.txt`, `chat_stats.pdf`, `sample_report.pdf` ve `debug_output.html` dosyalarını kapsar. Başka adlı dosyalar korunmaz ve `.gitignore` elle hazırladığınız bir ZIP'e uygulanmaz. Projeyi paylaşmak için GitHub'daki **Code → Download ZIP** seçeneğini kullanın: yalnızca depodaki dosyaları içerir, sohbetleriniz ve raporlarınız asla pakete girmez. Paketi alanların yine kurulumu çalıştırması gerekir.

## Testler ve katkı

Test komutları ve geliştirme notları [CONTRIBUTING.md](CONTRIBUTING.md) dosyasındadır. GitHub Actions; testleri çalıştırır ve örnek PDF'i Ubuntu üzerinde Python 3.11–3.14 ile üretir. Windows'ta PowerShell betiklerini denetler, kurulumu ve testleri çalıştırır ve örnek PDF'i Python 3.14 ile üretir.

## Lisans

[MIT](LICENSE) · Geliştiren: [Ataberk Cem Ünal](https://github.com/ataberkcemunal)
