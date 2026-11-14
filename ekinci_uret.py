#!/usr/bin/env python3
"""Ekinci (xmlbankasi) XML'indeki stoktaki ürünleri Foto Ekspres formatında bir kez data/yeni/ekinci.xml olarak üretir.

- Açıklamalar kaynaktan kopyalanmaz: ürün adı, kategori ve kaynaktaki teknik bilgilerden (sayılar, ölçüler,
  malzeme vb.) Foto Ekspres adına özgün metin yazılır. Kaynak firmanın ya da başka firmaların adı geçmez.
- Fiyat XML'deki price1 olduğu gibi, para birimi XML'deki gibi (TRL->TRY, USD, EUR). KDV/kur ayarı sitede yapılır.
- Ürünler pasif, grup (kategori) "EKİNCİ"; gece güncellemesi gruplar.csv'deki EKİNCİ satırıyla yapılır.
"""
import csv
import hashlib
import html
import os
import re

KOK = os.path.dirname(os.path.abspath(__file__))
HAM = os.path.join(KOK, "data", "ham", "ekincimarkalartethertools.xml")
CIKTI = os.path.join(KOK, "data", "yeni", "ekinci.xml")
KAYNAK = os.path.join(KOK, "data", "yeni", "ekinci_kaynak.csv")
KAYNAK_KOK = "https://xml1.xmlbankasi.com/p1/ekincifotograf/image/data/xml"
ILK_NO = 14697
GRUP = "EKİNCİ"
STOK_VAR = 5
STYLE = "text-align:center;color:#000000;font-family:helvetica, arial, sans-serif;font-size:14pt;"
BOS = "<div>&nbsp;</div>"
NEDEN = ["Resmi Türkiye Garantili ürün", "14 gün içinde ücretsiz iade ve değişim",
         "İstanbul içi kurye ile aynı gün teslimat imkânı", "Sirkeci mağazamızda uzman destek",
         "Havale/EFT ile ödeme seçeneği"]
ALANLAR = ["id", "name", "brand", "sku", "barcode", "price", "currency", "stock", "availability",
           "category", "description", "status"]
KISA = {"Kenko": "KNK", "Vanguard": "VNG", "Tether Tools": "TTL", "Multiblitz": "MBL", "Colorama": "CLR",
        "Digipod": "DGP", "OP/Tech USA": "OPT", "Syyd": "SYD", "Hedler": "HDL", "Westcott": "WST",
        "Aputure": "APT", "Kamerar": "KMR", "Explorer": "EXP", "Excella": "EXC", "Glidecam": "GLD"}
FIRMA = re.compile(r"ekinci|xmlbankas|www\.|https?://|\.com\b", re.I)


def esc(s):
    return html.escape(s, quote=False)


def alan(i, ad):
    m = re.search(rf"<{ad}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{ad}>", i, re.S)
    return m.group(1).strip() if m else ""


def duz_metin(h):
    h = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>|</div>|</td>|</tr>", "\n", h)
    t = html.unescape(re.sub(r"<[^>]+>", " ", h))
    return [re.sub(r"[ \t\xa0]+", " ", x).strip() for x in t.split("\n") if x.strip()]


def secim(anahtar, liste):
    """Aynı ürün için hep aynı, farklı ürünler için farklı varyant seçer."""
    return liste[int(hashlib.md5(anahtar.encode()).hexdigest(), 16) % len(liste)]


def ozellik_ciftleri(satirlar):
    ciftler = []
    for s in satirlar:
        for parca in re.split(r"(?<=[a-zçğıöşü0-9\.\)])(?=[A-ZÇĞİÖŞÜ][\wçğıöşü ]{2,30}:)", s):
            m = re.match(r"^([A-ZÇĞİÖŞÜa-zçğıöşü][\wÇĞİÖŞÜçğıöşü /()\-\.]{1,40}?)\s*:\s*(\S.{0,80})$", parca.strip())
            if m:
                k, v = m.group(1).strip(), m.group(2).strip(" .")
                if re.search(r"barkod|ürün kodu|örnek çekim|önceki boyut|sonraki boyut", k, re.I) or FIRMA.search(v):
                    continue
                ciftler.append((k[0].upper() + k[1:], v))
    tekil, gor = [], set()
    for k, v in ciftler:
        if k.lower() not in gor:
            gor.add(k.lower())
            tekil.append((k, v))
    return tekil


def barkod(satirlar):
    for s in satirlar:
        m = re.search(r"barkod[^:]*:\s*(\d{8,14})", s, re.I)
        if m:
            return m.group(1)
    return ""


# ------------------------------------------------------------------ ürün türleri
# tür: (tanım cümlesi, kullanım alanları, kutu içeriği ekleri, temel özellikler, sss)
T = {}


def tur(ana, kat, ad):
    k, a = kat.lower(), ad.lower()
    if "nd" in k and "filtre" in ana.lower():
        return "nd"
    if "polarize" in k:
        return "cpl"
    if "uv" in k:
        return "uv"
    if "konvert" in k:
        return "konv"
    if "filtre set" in k:
        return "filtreset"
    if "close" in k:
        return "closeup"
    if "extension" in k:
        return "ext"
    if "renk filt" in k:
        return "renkfiltre"
    if "parasoley" in k:
        return "parasoley"
    if "lens aksesuar" in k:
        return "lensaks"
    if "sırt" in k:
        return "sirt"
    if "omuz" in k or "el çanta" in k or "bel çanta" in k:
        return "omuz"
    if "tekerlek" in k:
        return "tekerlekli"
    if "hardcase" in k:
        return "hardcase"
    if "ışık çanta" in k or "tripod çanta" in k or "aksesuar çanta" in k or "telefon çanta" in k:
        return "kilif"
    if "video tripod" in k:
        return "videotripod"
    if "mini tripod" in k:
        return "minitripod"
    if "monopod" in k:
        return "monopod"
    if "başlık" in k:
        return "baslik"
    if "tripod aksesuar" in k:
        return "tripodaks"
    if "tripod" in k:
        return "tripod"
    if "karton fon" in k or "diğer fon" in k:
        return "fon"
    if "fon askı" in k:
        return "fonaski"
    if "softbox" in k:
        return "softbox"
    if "tas reflekt" in k:
        return "tas"
    if "panel reflekt" in k:
        return "panel"
    if "şemsiye" in k:
        return "semsiye"
    if "flaş tüp" in k:
        return "tup"
    if "tetikleyici" in k:
        return "tetik"
    if "ışık ayak" in k:
        return "ayak"
    if "ışık filtre" in k:
        return "jel"
    if "sürekli ışık" in k or "flaş set" in k:
        return "isik"
    if "aktarım kablo" in k and "tutucu" not in k:
        return "kablo"
    if "tutucu" in k or "düzenleyici" in k:
        return "kablotutucu"
    if "bilgisayar" in k:
        return "masa"
    if "askı" in k:
        return "aski"
    if "batarya" in k:
        return "batarya"
    if "yağmurluk" in k:
        return "yagmurluk"
    if "dürbün" in k:
        return "durbun"
    if "slider" in k:
        return "slider"
    if "telefon" in k:
        return "telefon"
    if "gimbal" in k:
        return "gimbal"
    return "aksesuar"


def ekle(ad, tanim, kullanim, kutu, temel, sss):
    T[ad] = dict(tanim=tanim, kullanim=kullanim, kutu=kutu, temel=temel, sss=sss)


ekle("nd", ["{ad}, objektife giren ışık miktarını renk dengesini bozmadan azaltan nötr yoğunluklu (ND) bir filtredir.",
            "{ad}, parlak ortamlarda uzun pozlama ve geniş diyafram kullanabilmeniz için ışığı kontrollü biçimde kısan bir ND filtredir."],
     ["Gün ışığında geniş diyaframla sığ alan derinliği elde etmek", "Akan su, bulut ve kalabalıklarda uzun pozlama efekti",
      "Videoda 180 derece enstantane kuralını korumak"],
     ["Filtre saklama kutusu"],
     [("Nötr Renk", "Işığı azaltırken renkleri değiştirmemek üzere tasarlanmıştır."),
      ("Uzun Pozlama", "Gündüz çekimlerinde yavaş enstantane kullanmanıza imkân tanır."),
      ("Video Uyumu", "Sabit enstantaneyle çekim yapan video kullanıcıları için idealdir.")],
     [("ND filtre fotoğrafın rengini değiştirir mi?", "Nötr yoğunluklu filtreler ışık miktarını azaltmak için tasarlanır; doğru beyaz dengesiyle renkler doğal kalır."),
      ("ND filtre ile netleme yapılabilir mi?", "Düşük ve orta yoğunluklarda otomatik netleme genelde çalışır; çok yoğun filtrelerde netlemeyi filtreyi takmadan önce yapmanız önerilir.")])
ekle("cpl", ["{ad}, yansımaları bastıran, gökyüzünün mavisini ve renk doygunluğunu artıran dairesel polarize (CPL) bir filtredir."],
     ["Manzara çekimlerinde daha canlı gökyüzü ve bulutlar", "Su, cam ve parlak yüzeylerdeki yansımaları azaltmak",
      "Yapraklarda ve doğada renk doygunluğunu artırmak"],
     ["Filtre saklama kutusu"],
     [("Yansıma Kontrolü", "Döner halkası sayesinde polarizasyon etkisi istenen seviyeye ayarlanır."),
      ("Canlı Renkler", "Gökyüzü ve yeşil tonlarda kontrastı belirgin şekilde artırır."),
      ("Dairesel Yapı", "Otomatik netleme ve ölçüm sistemleriyle uyumlu çalışır.")],
     [("CPL filtrenin etkisi nasıl ayarlanır?", "Filtrenin ön halkasını vizörden ya da ekrandan bakarak çevirdiğinizde etkinin arttığını veya azaldığını görürsünüz."),
      ("Polarize filtre ışığı azaltır mı?", "Evet, polarize filtreler yaklaşık 1–2 stop ışık kaybına neden olur; pozlamanızı buna göre ayarlayabilirsiniz.")])
ekle("uv", ["{ad}, objektifin ön camını toza, çizik ve darbelere karşı koruyan, morötesi ışığın etkisini azaltan bir filtredir."],
     ["Objektifin ön camını günlük kullanımda korumak", "Dış mekân ve seyahat çekimleri", "Deniz kenarı, kum ve tozlu ortamlar"],
     ["Filtre saklama kutusu"],
     [("Lens Koruması", "Ön camı çizik, toz ve parmak izine karşı korur."),
      ("Görüntü Kalitesi", "Pozlamayı değiştirmeden sürekli takılı kullanılabilir."),
      ("Kolay Bakım", "Filtre yüzeyi, objektif camına göre çok daha kolay temizlenir.")],
     [("UV filtre sürekli takılı kalabilir mi?", "Evet, pozlamayı etkilemediği için koruma amacıyla objektif üzerinde sürekli kullanılabilir."),
      ("Filtre çapımı nasıl öğrenirim?", "Objektifin ön kısmında veya kapağının iç yüzünde ⌀ işaretiyle yazan değer filtre çapıdır.")])
ekle("konv", ["{ad}, objektif ile fotoğraf makinesi gövdesi arasına takılarak odak uzaklığını artıran bir telekonvertördür."],
     ["Doğa ve kuş fotoğrafçılığı", "Spor ve uzak mesafe çekimleri", "Mevcut objektifle daha fazla yakınlaştırma"],
     ["Ön ve arka koruma kapakları"],
     [("Odak Uzaklığı", "Mevcut objektifinizin odak uzaklığını katlayarak daha uzağa ulaşmanızı sağlar."),
      ("Pratik Kullanım", "Yeni bir tele objektif almadan erişim mesafenizi artırır."),
      ("Gövde Uyumu", "Belirtilen montaj sistemine uygun gövdelerle kullanılır.")],
     [("Telekonvertör ışık kaybına yol açar mı?", "Evet; 1.4x yaklaşık 1 stop, 2x yaklaşık 2 stop ışık kaybı oluşturur."),
      ("Her objektifle kullanılabilir mi?", "Uyumluluk objektife göre değişir; satın almadan önce objektifinizi bize sorabilirsiniz.")])
for _t, _ad in (("filtreset", "filtre seti"), ("closeup", "yakın çekim filtresi"), ("ext", "uzatma tüpü seti"),
                ("renkfiltre", "renk filtresi"), ("parasoley", "parasoley"), ("lensaks", "objektif aksesuarı")):
    ekle(_t, ["{ad}, fotoğraf ekipmanınızı daha verimli kullanmanız için hazırlanmış bir " + _ad + "dir."],
         ["Makro ve yakın çekimler" if _t in ("closeup", "ext") else "Dış mekân ve manzara çekimleri",
          "Ürün ve detay fotoğrafçılığı" if _t in ("closeup", "ext") else "Portre ve seyahat fotoğrafçılığı",
          "Hobi ve profesyonel kullanım"],
         ["Saklama kutusu veya kılıfı"] if _t != "parasoley" else [],
         [("Kolay Montaj", "Objektife hızlıca takılıp çıkarılır."),
          ("Dayanıklı Yapı", "Uzun süreli kullanım için sağlam malzemeden üretilmiştir."),
          ("Taşınabilirlik", "Çanta içinde az yer kaplar.")],
         [("Objektifime uyar mı?", "Ürün adındaki çap veya montaj bilgisini objektifinizle karşılaştırın; emin olamazsanız bize sorabilirsiniz.")])
ekle("parasoley", T["parasoley"]["tanim"], ["Gün ışığında parlama ve yansımaları azaltmak", "Objektif ön camını darbelere karşı korumak", "Portre ve dış mekân çekimleri"],
     [], [("Parlama Kontrolü", "Yandan gelen ışığın objektife girmesini engelleyerek kontrastı korur."),
          ("Koruma", "Ön camı darbe ve parmak temasına karşı korur."), ("Hafif Yapı", "Ekipmana belirgin ağırlık eklemez.")],
     [("Parasoley ne işe yarar?", "Objektife yandan giren ışığı keserek parlamayı azaltır ve görüntüde kontrastı korur.")])
ekle("sirt", ["{ad}, fotoğraf makinesi, objektif ve aksesuarlarınızı güvenle taşımanız için tasarlanmış bir sırt çantasıdır.",
              "{ad}, ekipmanınızı iki omza dengeli dağıtarak uzun yürüyüşlerde ve seyahatte rahat taşımanızı sağlayan bir fotoğrafçı sırt çantasıdır."],
     ["Seyahat ve doğa çekimleri", "Şehir içi günlük kullanım", "Etkinlik ve saha çekimleri"],
     [],
     [("Ayarlanabilir Bölmeler", "İç bölmeler ekipmanınıza göre yeniden düzenlenebilir."),
      ("Konforlu Taşıma", "Yastıklı omuz askıları uzun süreli kullanımda rahatlık sağlar."),
      ("Koruma", "Darbe emici iç yapı ekipmanınızı korur.")],
     [("Çantaya kaç objektif sığar?", "Kapasite modele göre değişir; ölçüler ve bölme yapısı için bize danışabilirsiniz."),
      ("Dizüstü bilgisayar taşınabilir mi?", "Bilgisayar bölmesi olan modellerde belirtilen ekran boyutuna kadar bilgisayar taşınabilir.")])
ekle("omuz", ["{ad}, ekipmanınıza hızlı erişim isteyen fotoğrafçılar için tasarlanmış pratik bir omuz çantasıdır."],
     ["Sokak ve gezi fotoğrafçılığı", "Etkinlik ve düğün çekimleri", "Günlük kullanım ve kısa seyahatler"],
     [],
     [("Hızlı Erişim", "Üstten açılan kapak sayesinde makinenize saniyeler içinde ulaşırsınız."),
      ("Düzenli İç Yapı", "Bölmeler gövde, objektif ve aksesuarları ayrı tutar."),
      ("Rahat Askı", "Ayarlanabilir omuz askısı farklı boylara uyum sağlar.")],
     [("Çanta hangi makinelerle uyumlu?", "Ürün ölçülerine uyan aynasız ve DSLR gövdeleri objektifleriyle birlikte taşıyabilirsiniz.")])
ekle("tekerlekli", ["{ad}, ağır ekipmanları zahmetsizce taşımanızı sağlayan tekerlekli bir fotoğraf ve video çantasıdır."],
     ["Havalimanı ve uzun seyahatler", "Stüdyo ve set taşımaları", "Profesyonel prodüksiyon ekipleri"],
     [], [("Tekerlekli Taşıma", "Uzun mesafelerde ekipmanı sırtta taşıma zorunluluğunu ortadan kaldırır."),
          ("Teleskopik Kol", "Ayarlanabilir kol rahat bir sürüş sağlar."),
          ("Geniş Hacim", "Gövde, objektif ve aksesuarlar için bol alan sunar.")],
     [("Kabin bagajı olarak kullanılabilir mi?", "Ölçüler havayolu şirketine göre değişir; ürün ölçülerini havayolunun kabin kurallarıyla karşılaştırmanızı öneririz.")])
ekle("hardcase", ["{ad}, hassas ekipmanları darbe, toz ve neme karşı koruyan sert gövdeli bir taşıma kutusudur."],
     ["Kamera, drone ve ışık ekipmanının taşınması", "Zorlu dış mekân koşulları", "Depolama ve nakliye"],
     [], [("Sert Gövde", "Darbelere karşı yüksek koruma sağlar."),
          ("Güvenli Kapanış", "Sağlam kilit mandalları kapağı sıkıca kapatır."),
          ("Uzun Ömür", "Yoğun profesyonel kullanıma dayanacak şekilde üretilmiştir.")],
     [("Kutunun içi ekipmana göre şekillendirilebilir mi?", "Süngerli modellerde iç sünger ekipmanınızın şekline göre düzenlenebilir.")])
ekle("kilif", ["{ad}, ekipmanınızı düzenli tutmak ve taşımak için hazırlanmış pratik bir kılıf/çantadır."],
     ["Işık, tripod veya aksesuarların taşınması", "Stüdyo düzeni", "Seyahat"],
     [], [("Koruma", "Ekipmanı çizik ve toza karşı korur."), ("Kolay Taşıma", "Tutma kolu veya askısıyla rahat taşınır."),
          ("Düzen", "Parçaların bir arada ve düzenli kalmasını sağlar.")],
     [("Hangi ürünler sığar?", "İç ölçüler ürün bilgilerinde belirtilmiştir; emin olmak için bize danışabilirsiniz.")])
ekle("tripod", ["{ad}, fotoğraf makinenizi sabit ve dengeli tutarak net kareler yakalamanızı sağlayan bir tripod kitidir.",
                "{ad}, uzun pozlama, manzara ve stüdyo çekimlerinde makinenizi güvenle sabitleyen başlıklı bir tripod setidir."],
     ["Manzara ve gece fotoğrafçılığı", "Ürün ve stüdyo çekimleri", "Video ve zaman atlamalı (timelapse) çekimler"],
     [], [("Sağlam Duruş", "Ayarlanabilir bacaklar farklı zeminlerde dengeli kurulum sağlar."),
          ("Hızlı Kurulum", "Bacak kilitleri sayesinde yükseklik kısa sürede ayarlanır."),
          ("Başlık Kontrolü", "Başlık sayesinde kadrajı hassas biçimde ayarlarsınız.")],
     [("Tripod hangi makinelerle uyumlu?", "Standart 1/4\" vida kullanan fotoğraf makineleri ve kameralarla kullanılabilir; taşıma kapasitesini aşmamanız önerilir."),
      ("Tripodu seyahatte taşıyabilir miyim?", "Kapalı uzunluk ve ağırlık değerlerine bakarak çantanıza uygun olup olmadığını görebilirsiniz.")])
for _t in ("videotripod", "minitripod", "monopod", "baslik", "tripodaks"):
    T[_t] = dict(T["tripod"])
T["videotripod"] = dict(T["tripod"], tanim=["{ad}, akıcı pan ve tilt hareketleri için fluid başlıkla kullanılan bir video tripod kitidir."],
                        kullanim=["Röportaj ve belgesel çekimleri", "Etkinlik ve canlı yayın", "Kısa film ve reklam prodüksiyonları"])
T["minitripod"] = dict(T["tripod"], tanim=["{ad}, masa üstü ve seyahat kullanımı için tasarlanmış hafif ve kompakt bir mini tripoddur."],
                       kullanim=["Vlog ve masa üstü çekimler", "Seyahatte pratik sabitleme", "Ürün ve yakın çekimler"])
T["monopod"] = dict(T["tripod"], tanim=["{ad}, hareket özgürlüğünüzü kısıtlamadan kamerayı destekleyen tek ayaklı bir monopoddur."],
                    kullanim=["Spor ve etkinlik çekimleri", "Uzun ve ağır objektiflerle çalışma", "Kalabalık ortamlarda hızlı çekim"])
T["baslik"] = dict(T["tripod"], tanim=["{ad}, tripod üzerinde kameranın açısını hassas biçimde ayarlamanızı sağlayan bir tripod başlığıdır."],
                   kullanim=["Manzara ve mimari fotoğrafçılık", "Stüdyo çekimleri", "Video ve panorama çekimleri"])
T["tripodaks"] = dict(T["tripod"], tanim=["{ad}, tripod ve başlık sisteminizi daha işlevsel hale getiren bir tripod aksesuarıdır."],
                      kullanim=["Tripod kurulumunu kolaylaştırmak", "Farklı ekipmanları bir arada kullanmak", "Stüdyo ve saha çekimleri"])
ekle("fon", ["{ad}, stüdyoda temiz ve kesintisiz arka plan oluşturmak için kullanılan bir fotoğraf fonudur."],
     ["Portre ve vesikalık çekimler", "Ürün ve e-ticaret fotoğrafçılığı", "Video ve YouTube çekimleri"],
     [], [("Kesintisiz Arka Plan", "Zeminden duvara kesintisiz geçiş sağlar."),
          ("Mat Yüzey", "Işığı yansıtmayan yüzeyi sayesinde temiz bir görünüm sunar."),
          ("Kolay Kullanım", "Fon askı sistemine takılarak kolayca açılıp toplanır.")],
     [("Fon nasıl asılır?", "Fon rulosu, fon askı sistemi veya iki ayak arasına yerleştirilen bir çubukla asılır."),
      ("Kirlenen bölüm ne yapılır?", "Karton fonlarda kirlenen alt kısım kesilip ruloyu aşağı çekerek temiz yüzeyle devam edilebilir.")])
ekle("fonaski", ["{ad}, stüdyoda fon rulolarını güvenle asmanızı ve kolayca indirip kaldırmanızı sağlayan bir fon askı sistemidir."],
     ["Fotoğraf stüdyoları", "Ürün çekim alanları", "Video ve yayın stüdyoları"], [],
     [("Pratik Kullanım", "Fonu hızlıca indirip kaldırmanızı sağlar."), ("Sağlam Montaj", "Ağır rulolar için güvenli taşıma sunar."),
      ("Düzen", "Birden fazla fonla düzenli çalışmayı kolaylaştırır.")],
     [("Kaç fon asılabilir?", "Asılabilecek fon sayısı sistemin modeline göre değişir; ayrıntılar için bize danışabilirsiniz.")])
ekle("softbox", ["{ad}, flaş veya sürekli ışığın önüne takılarak sert ışığı yumuşak ve dengeli bir ışığa dönüştüren bir softboxtur."],
     ["Portre ve moda çekimleri", "Ürün ve e-ticaret fotoğrafçılığı", "Video ve röportaj ışıklandırması"],
     ["Difüzör bezi"],
     [("Yumuşak Işık", "Gölgeleri yumuşatarak doğal ve hoş bir ışık sağlar."),
      ("Kolay Kurulum", "Katlanabilir yapısıyla kısa sürede kurulur."), ("Taşınabilirlik", "Toplandığında az yer kaplar.")],
     [("Softbox hangi ışıklarla uyumlu?", "Ürün adında belirtilen bayonet/montaj tipine sahip ışıklarla kullanılabilir.")])
ekle("tas", ["{ad}, ışığı belirli bir alana yönlendirip yoğunlaştıran bir tas reflektördür."],
     ["Portre ve moda çekimleri", "Arka plan ve saç ışığı", "Ürün fotoğrafçılığı"], [],
     [("Kontrollü Işık", "Işığı istenen yöne toplar."), ("Kontrast", "Daha belirgin ve canlı bir ışık karakteri sağlar."),
      ("Sağlam Yapı", "Metal gövdesi uzun ömürlüdür.")],
     [("Tas reflektör ile softbox arasındaki fark nedir?", "Tas reflektör daha sert ve kontrastlı, softbox ise daha yumuşak ve yaygın bir ışık verir.")])
ekle("panel", ["{ad}, mevcut ışığı yansıtarak gölgeleri dolduran ve ışığı yumuşatan bir reflektör panelidir."],
     ["Dış mekân portre çekimleri", "Stüdyoda dolgu ışığı", "Ürün çekimleri"], ["Taşıma çantası"],
     [("Işık Yönlendirme", "Doğal veya yapay ışığı istenen yöne yansıtır."), ("Çok Yönlü", "Farklı yüzeyleriyle ışığın karakterini değiştirir."),
      ("Katlanabilir", "Kolayca toplanıp taşınır.")],
     [("Hangi yüzey ne işe yarar?", "Gümüş daha parlak, altın daha sıcak, beyaz daha yumuşak dolgu ışığı verir; difüzör ışığı yumuşatır.")])
ekle("semsiye", ["{ad}, flaş ışığını yansıtarak veya geçirerek geniş ve yumuşak bir aydınlatma sağlayan bir stüdyo şemsiyesidir."],
     ["Portre ve aile çekimleri", "Etkinlik ve stüdyo kurulumları", "Hızlı ve pratik aydınlatma"], [],
     [("Geniş Işık", "Geniş alanı eşit şekilde aydınlatır."), ("Hızlı Kurulum", "Saniyeler içinde açılıp kapanır."),
      ("Hafif", "Taşıması kolaydır.")],
     [("Şemsiye hangi ışıklarla kullanılır?", "Şemsiye yuvası bulunan stüdyo flaşları ve tepe flaş adaptörleriyle kullanılabilir.")])
ekle("tup", ["{ad}, uyumlu stüdyo flaşlarında kullanılan yedek bir flaş tüpüdür."],
     ["Stüdyo flaşının bakım ve onarımı", "Yedek parça olarak elde bulundurma", "Profesyonel stüdyolar"], [],
     [("Uyumluluk", "Belirtilen flaş modelleriyle kullanılmak üzere üretilmiştir."), ("Performans", "Flaşınızın ışık verimini korur."),
      ("Yedek Parça", "Çekimlerde aksama yaşamamak için idealdir.")],
     [("Tüp değişimini kendim yapabilir miyim?", "Flaşın enerjisi tamamen boşaltıldıktan sonra değiştirilmelidir; emin değilseniz mağazamızdan destek alabilirsiniz.")])
ekle("tetik", ["{ad}, flaşlarınızı kablosuz olarak tetiklemenizi sağlayan bir tetikleyicidir."],
     ["Stüdyo flaş kurulumları", "Dış mekân flaş kullanımı", "Çoklu ışık düzenleri"], [],
     [("Kablosuz Kontrol", "Flaşları kablo karmaşası olmadan tetikler."), ("Kolay Kullanım", "Kurulumu basittir."),
      ("Esneklik", "Işıkları istediğiniz noktaya yerleştirmenizi sağlar.")],
     [("Hangi makinelerle uyumlu?", "Uyumluluk ürün adında belirtilen sisteme göredir; makinenizi bize sorabilirsiniz.")])
ekle("ayak", ["{ad}, stüdyo ışıklarını ve aksesuarlarını güvenle taşıyan ayarlanabilir bir ışık ayağıdır."],
     ["Flaş ve sürekli ışık kurulumu", "Reflektör ve fon taşıma", "Video setleri"], [],
     [("Ayarlanabilir Yükseklik", "Işığı istediğiniz seviyeye yerleştirirsiniz."), ("Sağlam Taban", "Geniş bacakları dengeli duruş sağlar."),
      ("Taşınabilir", "Toplanınca kompakt hale gelir.")],
     [("Ayağın üstüne hangi ekipman takılır?", "Standart ışık ayağı başlığına uyan flaş, LED ve aksesuarlar takılabilir.")])
ekle("jel", ["{ad}, ışığın rengini ve karakterini değiştirmek için kullanılan bir ışık filtresidir."],
     ["Renkli arka plan efektleri", "Renk sıcaklığı düzeltme", "Yaratıcı stüdyo ışıklandırması"], [],
     [("Renk Kontrolü", "Işığa istenen tonu verir."), ("Yaratıcılık", "Farklı atmosferler oluşturmanızı sağlar."),
      ("Kolay Kullanım", "Işık kaynağının önüne hızla takılır.")],
     [("Filtre ışık gücünü azaltır mı?", "Renk filtreleri bir miktar ışık kaybına neden olur; ışık gücünü buna göre ayarlayabilirsiniz.")])
ekle("isik", ["{ad}, fotoğraf ve video çekimlerinde sürekli ve kontrollü aydınlatma sağlayan bir ışık çözümüdür."],
     ["YouTube ve içerik üretimi", "Ürün ve portre çekimleri", "Röportaj ve video prodüksiyonu"], [],
     [("Sürekli Işık", "Çekim öncesi ışığın etkisini anında görürsünüz."), ("Kolay Kurulum", "Kısa sürede kurulup kullanıma hazır hale gelir."),
      ("Çok Yönlü", "Fotoğraf ve video için uygundur.")],
     [("Video çekiminde kullanılabilir mi?", "Evet, sürekli ışık olduğu için fotoğraf kadar video çekimlerine de uygundur.")])
ekle("kablo", ["{ad}, fotoğraf makinenizi bilgisayara bağlayarak çekim yaparken kareleri anında büyük ekranda görmenizi sağlayan bir aktarım (tethering) kablosudur."],
     ["Stüdyoda bilgisayara bağlı (tethered) çekim", "Ürün ve e-ticaret fotoğrafçılığı", "Müşteriyle birlikte anlık kontrol"], [],
     [("Yüksek Görünürlük", "Turuncu renk seçeneğiyle sette fark edilir, takılma riskini azaltır."),
      ("Hızlı Aktarım", "Fotoğrafları bilgisayara hızlı ve kesintisiz iletir."),
      ("Uzun Kablo", "Kamera ile bilgisayar arasında rahat hareket alanı sunar.")],
     [("Hangi programlarla kullanılır?", "Makinenizin desteklediği bağlantılı çekim yazılımlarıyla (ör. Capture One, Lightroom, üretici yazılımları) kullanılabilir."),
      ("Makinemin girişini nasıl öğrenirim?", "Ürün adında kabloyun uç tipleri yazar; makinenizdeki USB girişiyle karşılaştırabilir veya bize sorabilirsiniz.")])
ekle("kablotutucu", ["{ad}, aktarım kablosunu kameraya ve bilgisayara güvenle sabitleyerek kopma ve takılmaları önleyen bir kablo yönetim aksesuarıdır."],
     ["Bağlantılı stüdyo çekimleri", "Kablo ve port koruması", "Düzenli çalışma alanı"], [],
     [("Port Koruması", "Kablo çekildiğinde portun zarar görmesini engeller."), ("Düzen", "Kabloları düzenli tutar."),
      ("Kolay Montaj", "Kamera veya masa düzeneğine hızla takılır.")],
     [("Hangi kablolarla kullanılır?", "Standart aktarım kablolarıyla uyumludur; ölçü bilgisi için bize danışabilirsiniz.")])
ekle("masa", ["{ad}, dizüstü bilgisayarı tripod veya ayak üzerinde güvenle konumlandırmanızı sağlayan bir çalışma platformu aksesuarıdır."],
     ["Bağlantılı stüdyo çekimleri", "Saha çalışmaları", "Video ve yayın kurulumları"], [],
     [("Sağlam Platform", "Bilgisayarı dengeli ve güvenli tutar."), ("Ergonomi", "Ekranı göz hizasına getirir."),
      ("Uyumluluk", "Standart ayak ve tripodlarla kullanılabilir.")],
     [("Hangi ayaklara takılır?", "Standart vida bağlantısına sahip tripod ve ışık ayaklarına takılabilir.")])
ekle("aski", ["{ad}, fotoğraf makinenizi rahat ve güvenli taşımanız için tasarlanmış bir askıdır."],
     ["Günlük çekimler", "Seyahat ve gezi", "Etkinlik ve uzun süreli kullanım"], [],
     [("Konfor", "Ağırlığı dengeli dağıtarak boyun ve omuz yorgunluğunu azaltır."), ("Güvenlik", "Sağlam bağlantı noktaları sunar."),
      ("Ayarlanabilir", "Uzunluk ihtiyaca göre ayarlanır.")],
     [("Her makineye takılır mı?", "Standart askı halkası olan fotoğraf makinelerinin büyük bölümüyle uyumludur.")])
ekle("batarya", ["{ad}, uyumlu cihazlarınız için güvenilir güç sağlayan bir batarya/şarj ürünüdür."],
     ["Uzun çekim günleri", "Seyahat", "Yedek güç ihtiyacı"], [],
     [("Güvenilir Güç", "Cihazınızı kesintisiz çalıştırır."), ("Uyumluluk", "Belirtilen modellerle kullanılmak üzere üretilmiştir."),
      ("Yedek", "Çekimde güç sıkıntısı yaşamamanızı sağlar.")],
     [("Cihazıma uyar mı?", "Ürün adındaki model bilgisini cihazınızla karşılaştırın veya bize sorun.")])
ekle("yagmurluk", ["{ad}, fotoğraf makinenizi ve objektifinizi yağmur ve neme karşı koruyan bir yağmurluktur."],
     ["Yağmurlu havada dış çekim", "Deniz kenarı ve şelale çekimleri", "Spor ve doğa etkinlikleri"], [],
     [("Su Koruması", "Ekipmanı yağmur ve sıçramalara karşı korur."), ("Kolay Kullanım", "Hızlıca takılıp çıkarılır."),
      ("Hafif", "Çantada az yer kaplar.")],
     [("Hangi objektiflerle uyumlu?", "Uyumluluk ürün ölçülerine göredir; ayrıntılar için bize danışabilirsiniz.")])
ekle("durbun", ["{ad}, uzaktaki detayları net ve parlak görmenizi sağlayan bir dürbündür."],
     ["Doğa ve kuş gözlemi", "Seyahat ve gezi", "Spor ve etkinlikler"], ["Taşıma kılıfı", "Boyun askısı"],
     [("Net Görüntü", "Kaliteli optikleri ile detayları netleştirir."), ("Ergonomi", "Rahat kavrama sunar."),
      ("Taşınabilirlik", "Çantada kolayca taşınır.")],
     [("Büyütme değeri ne anlama gelir?", "Ürün adındaki ilk sayı büyütmeyi, ikinci sayı ön mercek çapını (mm) gösterir.")])
for _t, _ac in (("slider", "kayar ray (slider)"), ("telefon", "telefon ve tablet tutucu"), ("gimbal", "gimbal/stabilizer"),
                ("aksesuar", "aksesuar")):
    ekle(_t, ["{ad}, fotoğraf ve video çekimlerinizi kolaylaştırmak için tasarlanmış bir " + _ac + " ürünüdür."],
         ["Video ve içerik üretimi", "Stüdyo ve saha çekimleri", "Hobi ve profesyonel kullanım"], [],
         [("Pratik Kullanım", "Kurulumu ve kullanımı kolaydır."), ("Dayanıklı Yapı", "Uzun süreli kullanıma uygundur."),
          ("Çok Yönlü", "Farklı çekim senaryolarına uyum sağlar.")],
         [("Ekipmanımla uyumlu mu?", "Uyumluluk için ürün bilgilerini kontrol edebilir veya bize danışabilirsiniz.")])


# ------------------------------------------------------------------ bilgi çıkarma
def bilgiler(ad, satirlar, ciftler):
    """Başlık ve kaynak metindeki sayısal/teknik bilgileri Foto Ekspres cümlelerine çevirir."""
    metin = " ".join(satirlar)
    out = []
    m = re.search(r"(\d{2,3})\s?mm", ad)
    if m and re.search(r"filtre|parasoley|close", ad, re.I):
        out.append(("Filtre Çapı", f"{m.group(1)} mm filtre yuvasına sahip objektiflerle kullanılır."))
    m = re.search(r"\bND\s?(\d{1,4})\b", ad, re.I)
    if m and not re.search(r"ND\s?\d{1,4}\s*[-–/ ]\s*ND\s?\d", ad, re.I):
        out.append(("Yoğunluk", f"ND{m.group(1)} değeriyle ışığı belirgin şekilde azaltarak daha yavaş enstantane ve daha geniş diyafram kullanmanıza olanak tanır."))
    m = re.search(r"(\d(?:[.,]\d)?)x\b", ad)
    if m and re.search(r"konvert", ad, re.I):
        out.append(("Büyütme", f"Odak uzaklığını {m.group(1)} kat artırır."))
    m = re.search(r"\b(\d{2,3})\s?[x×]\s?(\d{1,3})\b", ad)
    if m and not re.search(r"filtre", ad, re.I):
        if re.search(r"fon", ad, re.I) and int(m.group(2)) <= 30:
            out.append(("Ölçü", f"{m.group(1)} cm genişlik ve {m.group(2)} metre uzunlukta rulo olarak sunulur."))
        elif int(m.group(2)) >= 10:
            out.append(("Ölçü", f"{m.group(1)} x {m.group(2)} cm ölçüleriyle sunulur."))
    m = re.search(r"(\d+(?:[.,]\d+)?)\s?m\b", ad)
    if m and re.search(r"kablo|cable|fon", ad, re.I):
        out.append(("Uzunluk", f"{m.group(1)} metre uzunluğuyla geniş bir çalışma alanı sağlar."))
    m = re.search(r"(?:taşıma kapasitesi|kapasite\w*)\D{0,30}?(\d+(?:[.,]\d+)?)\s?(?:kg|kilogram)|(\d+(?:[.,]\d+)?)\s?(?:kg|kilogram)\w*\s*(?:'?a kadar|lık taşıma|lik taşıma|taşıma)", metin, re.I)
    if m and not re.search(r"fon|filtre", ad, re.I):
        out.append(("Taşıma Kapasitesi", f"{m.group(1) or m.group(2)} kg'a kadar yük taşıyabilir."))
    if False:
        out.append(("Taşıma Kapasitesi", f"{m.group(1)} kg'a kadar yük taşıyabilir."))
    m = re.search(r"(\d{2,3}(?:[.,]\d)?)\s?(?:cm|santim)\w*\s*(?:yüksekli|maksimum)|maksimum yükseklik\w*\s*:?\s*(\d{2,3}(?:[.,]\d)?)", metin, re.I)
    if m:
        out.append(("Çalışma Yüksekliği", f"Maksimum {m.group(1) or m.group(2)} cm yüksekliğe ulaşır."))
    m = re.search(r"(\d{1,2}(?:[.,]\d)?)\s?(?:\"|”|inç|inch)", metin, re.I)
    if m and re.search(r"çanta|bag", ad, re.I):
        cihaz = "tablet" if float(m.group(1).replace(",", ".")) < 12 else "dizüstü bilgisayar"
        out.append(("Bilgisayar Bölmesi", f"{m.group(1)} inç ekrana kadar {cihaz} taşıyabilir."))
    if re.search(r"karbon", ad + metin, re.I):
        out.append(("Karbon Fiber", "Karbon fiber yapısıyla hafiflik ve sağlamlığı bir arada sunar."))
    elif re.search(r"alüminyum", metin, re.I):
        out.append(("Alüminyum Yapı", "Alüminyum gövdesi dayanıklılık ve hafiflik sağlar."))
    if re.search(r"yağmur örtü|yağmurluk|rain cover", metin, re.I) and re.search(r"çanta", ad, re.I):
        out.append(("Yağmur Örtüsü", "Kötü hava koşullarında kullanılan yağmur örtüsüyle birlikte gelir."))
    if re.search(r"su terazi", metin, re.I):
        out.append(("Su Terazisi", "Dahili su terazisi ile kadrajı kolayca dengelersiniz."))
    if re.search(r"fluid", ad + metin, re.I):
        out.append(("Akıcı Hareket", "Fluid sönümleme sayesinde pan ve tilt hareketleri yumuşak olur."))
    if re.search(r"usb-?c", ad, re.I):
        out.append(("USB-C Bağlantı", "Güncel USB-C girişli makine ve bilgisayarlarla uyumludur."))
    m = re.search(r"\b(canon|nikon|sony|fujifilm|panasonic|olympus|pentax|profoto|bowens|elinchrom)\b", ad, re.I)
    if m:
        out.append(("Uyumluluk", f"{m.group(1).title()} sistemiyle kullanılmak üzere tasarlanmıştır."))
    for k, v in ciftler:
        if re.search(r"renk", k, re.I):
            out.append(("Renk", f"{v} renk seçeneğiyle sunulur."))
            break
    tekil, gor = [], set()
    for k, v in out:
        if k not in gor:
            gor.add(k)
            tekil.append((k, v))
    return tekil


SERI = [(r"\bzeta\b", "Zeta serisi, ince çerçevesi ve çok katmanlı kaplamasıyla yansımaları en aza indiren üst seviye bir filtre ailesidir."),
        (r"pro ?1d", "PRO1D serisi, dijital sensörler için optimize edilmiş kaplaması ve ince çerçevesiyle geniş açılı objektiflerde vinyetlemeyi azaltır."),
        (r"real ?pro", "Real Pro serisi, su ve yağ itici kaplamasıyla yüzeyin temizlenmesini kolaylaştırır."),
        (r"\bslim\b", "İnce (slim) çerçeve yapısı, geniş açılı objektiflerde köşe kararmasını (vinyetleme) azaltır."),
        (r"\bmc\b|multi ?coat", "Çok katmanlı (MC) kaplama, parlama ve yansımaları azaltarak kontrastı korur."),
        (r"variable|fader|değişken", "Değişken yapısı sayesinde tek filtreyle farklı yoğunluklar arasında geçiş yapabilirsiniz."),
        (r"\bcarbon|karbon", "Karbon fiber gövde, ağırlığı azaltırken titreşimi sönümlemeye yardımcı olur."),
        (r"orange|turuncu", "Turuncu renk, kalabalık setlerde kablonun kolayca fark edilmesini sağlar.")]
STOP = {"2": "1", "4": "2", "8": "3", "16": "4", "32": "5", "64": "6", "100": "6,6", "400": "8,6", "500": "9", "1000": "10"}
IPUCU = {
    "nd": ["Doğru yoğunluğu seçmek için çekim ortamınızın ne kadar parlak olduğunu ve hangi enstantaneye ulaşmak istediğinizi düşünün; yoğunluk arttıkça pozlama süresi uzar.",
           "Video çekiminde ND filtre, gün ışığında bile doğal hareket bulanıklığını korumanızı sağlar; fotoğrafta ise suyu ipeksi, bulutları akışkan gösterir."],
    "cpl": ["Polarize filtrenin etkisi güneşe 90 derece açıyla bakarken en belirgin hâle gelir; vizörden bakarak halkayı çevirip istediğiniz sonucu yakalayabilirsiniz.",
            "Manzara fotoğrafçıları için CPL, sonradan düzenleme programında elde edilemeyen yansıma kontrolünü çekim anında sunar."],
    "uv": ["Objektifinizin ön camını değiştirmek filtre almaktan çok daha maliyetlidir; bu yüzden UV/koruma filtresi her objektif için akıllıca bir yatırımdır.",
           "Filtreyi takarken dişleri zorlamadan çevirmeniz ve yüzeyi mikrofiber bezle temizlemeniz uzun ömürlü kullanım sağlar."],
    "sirt": ["Çanta seçerken makinenizin gövdesi, en uzun objektifiniz ve taşımak istediğiniz bilgisayar boyutunu birlikte düşünmeniz önerilir.",
             "Sırt çantaları, ağırlığı iki omza dağıttığı için uzun yürüyüşlerde ve seyahatlerde omuz çantalarına göre daha konforludur."],
    "omuz": ["Omuz çantaları, çekim sırasında makineye hızlı erişim isteyen sokak ve etkinlik fotoğrafçılarının ilk tercihidir.",
             "Çantanın bölmelerini gövde ve objektiflerinize göre düzenleyerek ekipmanınızın taşıma sırasında birbirine çarpmasını önleyebilirsiniz."],
    "tripod": ["Tripod seçerken taşıma kapasitesinin, kullandığınız gövde ve en ağır objektifin toplam ağırlığından fazla olmasına dikkat edin.",
               "Uzun pozlamalarda deklanşöre dokunurken oluşan titreşimi önlemek için zamanlayıcı veya uzaktan kumanda ile birlikte kullanmanızı öneririz."],
    "fon": ["Fonu ışıktan biraz uzak konumlandırmak, öznenin gölgesinin fona düşmesini engeller ve daha temiz bir arka plan sağlar.",
            "Farklı renklerde fonlar kullanarak aynı stüdyoda birbirinden farklı atmosferler oluşturabilirsiniz."],
    "kablo": ["Bağlantılı çekim, kareleri anında büyük ekranda görmenizi ve netlik ile pozlamayı çekim sırasında kontrol etmenizi sağlar.",
              "Uzun kablolarda bağlantının kopmaması için kablo tutucu ve port koruyucu aksesuarlarla birlikte kullanmanızı öneririz."],
    "softbox": ["Softbox özneye ne kadar yakın olursa ışık o kadar yumuşak olur; bu yüzden portrelerde kadrajın hemen dışına yerleştirmeniz önerilir."],
}


def seri_bilgileri(ad):
    out = []
    for desen, cumle in SERI:
        if re.search(desen, ad, re.I):
            out.append(cumle)
    m = re.search(r"ND\s?(\d{1,4})\s*[-–/ ]\s*ND\s?(\d{1,4})", ad, re.I)
    if m:
        out.append(f"ND{m.group(1)} ile ND{m.group(2)} arasında ayarlanabilen yoğunluğu, değişen ışık koşullarına hızla uyum sağlamanızı sağlar.")
    else:
        m = re.search(r"\bND\s?(\d{1,4})\b", ad, re.I)
        if m and m.group(1) in STOP:
            out.append(f"ND{m.group(1)} yoğunluğu, ışığı yaklaşık {STOP[m.group(1)]} stop azaltır.")
    return out


def kisa_ad(ad, marka):
    k = re.sub(rf"^{re.escape(marka)}\s+", "", ad, flags=re.I)
    return k if len(k) > 3 else ad


def aciklama(ad, marka, kat_ad, tip, satirlar, ciftler, sku):
    s = T.get(tip, T["aksesuar"])
    bilgi = bilgiler(ad, satirlar, ciftler)
    giris = [secim(sku, s["tanim"]).format(ad=ad)]
    if re.search(r"\bset", ad, re.I) and re.search(r"(filtresi|aksesuarı|tüpü seti)dir\.$", giris[0]):
        giris[0] = re.sub(r"bir (.+?) ?(filtresi|aksesuarı|tüpü seti)dir\.$", lambda m: f"bir {m.group(1)} {'filtre' if m.group(2)=='filtresi' else 'aksesuar' if m.group(2)=='aksesuarı' else 'uzatma tüpü'} setidir.", giris[0])
    giris.append(secim(sku + "g", [
        f"{marka} kalitesini Foto Ekspres güvencesiyle sunuyoruz; ürün Resmi Türkiye Garantili olarak gönderilir.",
        f"Foto Ekspres olarak {marka} ürünlerini garantili ve güvenli alışveriş imkânıyla sunuyoruz.",
        f"{kat_ad} kategorisinde güvenilir bir tercih arayanlar için {marka} imzalı bu ürünü Foto Ekspres farkıyla sunuyoruz."]))
    if bilgi:
        giris.append(secim(sku + "b", ["Öne çıkan teknik detayları aşağıda bulabilirsiniz.",
                                       "Ürünün sunduğu avantajları aşağıda özetledik.",
                                       "Satın almadan önce bilmeniz gereken detayları aşağıda derledik."]))
    giris += seri_bilgileri(ad)
    ip = IPUCU.get(tip) or IPUCU.get({"videotripod": "tripod", "minitripod": "tripod", "monopod": "tripod",
                                      "tekerlekli": "sirt", "kablotutucu": "kablo"}.get(tip, ""), [])
    if ip:
        giris.append(secim(sku + "i", ip))
    ozel = (bilgi + s["temel"])[:6]
    kutu = [f"1 adet {kisa_ad(ad, marka)}"] + s["kutu"]
    teknik = [("Marka", marka), ("Ürün Grubu", kat_ad)] + [(k, v) for k, v in ciftler][:4]
    if len(teknik) < 5:
        for k, v in bilgi:
            if k in ("Filtre Çapı", "Ölçü", "Uzunluk", "Taşıma Kapasitesi", "Büyütme", "Çalışma Yüksekliği") and len(teknik) < 6:
                kisa = re.search(r"\d+(?:[.,]\d+)?(?: cm genişlik ve \d+ metre| x \d+)?\s?(?:mm|cm|metre|kg'a|kat)?", v)
                if kisa:
                    teknik.append((k, kisa.group(0).replace("kg'a", "kg").replace(" genişlik ve ", " x ").strip()))
    sss = list(s["sss"])
    sss.append(("Ürün garantili mi?", "Evet, Foto Ekspres'te satılan tüm ürünler Resmi Türkiye Garantili olarak gönderilir."))
    sss = sss[:3]
    out = [f'<div style="{STYLE}">', f"<div><strong>{esc(ad)}</strong></div>", BOS]
    out += [f"<div>{esc(x)}</div>" for x in giris] + [BOS]
    out += ["<div><strong>Öne Çıkan Özellikler</strong></div>"]
    out += [f"<div><strong>{esc(k)}:</strong> {esc(v)}</div>" for k, v in ozel] + [BOS]
    out += ["<div><strong>Kullanım Alanları</strong></div>"] + [f"<div>{esc(x)}</div>" for x in s["kullanim"][:3]] + [BOS]
    out += ["<div><strong>Kutu İçeriği</strong></div>"] + [f"<div>{esc(x)}</div>" for x in kutu[:5]] + [BOS]
    out += ["<div><strong>Teknik Özellikler</strong></div>"] + [f"<div>{esc(k)}: {esc(v)}</div>" for k, v in teknik[:6]] + [BOS]
    out += ["<div><strong>Sık Sorulan Sorular</strong></div>"]
    for q, a in sss:
        out += [f"<div><strong>{esc(q)}</strong></div>", f"<div>{esc(a)}</div>"]
    out += [BOS, "<div><strong>Neden Foto Ekspres?</strong></div>"] + [f"<div>{x}</div>" for x in NEDEN] + ["</div>"]
    return "\n".join(out)


def cdata(s):
    return "<![CDATA[" + str(s).replace("]]>", "]]]]><![CDATA[>") + "]]>"


def uret(yaz=True):
    xml = open(HAM, encoding="utf-8").read()
    items = [i for i in re.findall(r"<item>.*?</item>", xml, re.S) if float(alan(i, "stockAmount") or 0) > 0
             and float(alan(i, "price1") or 0) > 0]
    items.sort(key=lambda i: (alan(i, "mainCategory"), alan(i, "category"), alan(i, "label")))
    urunler, kaynak = [], []
    for n, i in enumerate(items):
        kod, ad, marka = alan(i, "stockCode"), re.sub(r"\s+", " ", alan(i, "label")), alan(i, "brand")
        sku = f"FE-{KISA.get(marka, 'EKN')}-{ILK_NO + n}"
        satirlar = duz_metin(alan(i, "details"))
        satirlar = [x for x in satirlar if not FIRMA.search(x)]
        ciftler = ozellik_ciftleri(satirlar)
        tip = tur(alan(i, "mainCategory"), alan(i, "category"), ad)
        imgs = [alan(i, f"picture{k}Path") for k in range(1, 9)]
        para = {"TRL": "TRY", "TL": "TRY"}.get(alan(i, "currencyAbbr"), alan(i, "currencyAbbr") or "TRY")
        fiyat = f"{float(alan(i, 'price1')):.2f}".rstrip("0").rstrip(".")
        urunler.append(dict(id="", name=ad, brand=marka, sku=sku, barcode=barkod(satirlar), price=fiyat,
                            currency=para, stock=str(STOK_VAR), availability="https://schema.org/InStock",
                            category=GRUP, description=aciklama(ad, marka, alan(i, "category"), tip, satirlar, ciftler, sku),
                            status="passive", imgs=[x for x in imgs if x]))
        kaynak.append([sku, f"{KAYNAK_KOK}/{kod}", kod, ad])
    if yaz:
        os.makedirs(os.path.dirname(CIKTI), exist_ok=True)
        with open(CIKTI, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<products>\n')
            for u in urunler:
                f.write(" <product>\n")
                for a in ALANLAR:
                    f.write(f"  <{a}>{cdata(u[a])}</{a}>\n" if u[a] != "" else f"  <{a}/>\n")
                for k, g in enumerate(u["imgs"][:8], 1):
                    f.write(f"  <image{k}>{cdata(g)}</image{k}>\n")
                f.write(" </product>\n")
            f.write("</products>\n")
        with open(KAYNAK, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["sku", "url", "kaynak_kod", "ad"])
            w.writerows(kaynak)
    return urunler


def calistir():
    """sync.py çağırır: data/yeni/ekinci.xml yoksa ve ham veri varsa bir kez üretir."""
    if os.path.exists(CIKTI) or not os.path.exists(HAM):
        return
    u = uret()
    print(f"ekinci_uret: {len(u)} ürün data/yeni/ekinci.xml dosyasına yazıldı")


if __name__ == "__main__":
    calistir()
