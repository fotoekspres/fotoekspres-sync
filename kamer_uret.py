#!/usr/bin/env python3
"""Kamer İthalat XML'indeki stoktaki ürünleri Foto Ekspres formatında bir kez data/yeni/kamer.xml olarak üretir.

- Açıklama yazıcısı ekinci_uret.py ile ortaktır: kaynaktan kopyalanmaz, ürün adı ve teknik bilgilerden
  Foto Ekspres adına özgün metin yazılır; kaynak firmanın adı/linki/telefonu ve gömülü videolar alınmaz.
- Fiyat: price1 + %2,5 (kuruşlu), para birimi XML'deki gibi (USD/EUR/GBP). KDV/kur ayarı sitede yapılır.
- Sitede zaten olan ürünler (HARIC) eklenmez. Ürünler pasif, grup "KAMER".
"""
import csv
import os
import re

import ekinci_uret as E

KOK = os.path.dirname(os.path.abspath(__file__))
HAM = os.path.join(KOK, "data", "ham", "index.php?xml_service_id=36")
CIKTI = os.path.join(KOK, "data", "yeni", "kamer.xml")
KAYNAK = os.path.join(KOK, "data", "yeni", "kamer_kaynak.csv")
KAYNAK_KOK = "https://www.kamerithalat.com/outputxml"
ILK_NO = 15435
GRUP = "KAMER"
MARJ = 2.5
KISA = {"Benro": "BNR", "Elinchrom": "ELC", "Kaiser Fototechnik": "KSR", "Tenba": "TNB", "Lee Filter": "LEE",
        "Kata": "KTA", "Heliopan": "HLP", "Lensgo": "LNG", "DataColor": "DTC", "Neewer": "NWR",
        "weeylite": "WYL", "Shimoda": "SHM"}
MARKA = {"weeylite": "Weeylite", "Lee Filter": "LEE Filters", "Kaiser Fototechnik": "Kaiser"}
# Sitede başka kaynaktan zaten bulunan ürünler (Lensgo ve Benro gimbal)
HARIC = set("""1603XM 1603XD 140DM1TEKLİ 140DM1İKİLİ 140DMM2 140LYM-DM30 140348CBLACK1V1 140348CYELLOW1V1
140348CWHİTE1V1 140348CBLACK1V2 140348CYELLOW1V2 140348CWHİTE1V2 140318CBLACKTEKLİ 140318CWHİTETEKLİ
140LWM-338CTEKLİ 140LWM-338CİKİLİ 140LWM-328CTEKLİ 140LWM-328CİKİLİ 140518CIOS 140518CTYPE-C""".split())
FIRMA = re.compile(r"kamer ?ithalat|kamerithalat|\bkamer\b(?!a)|www\.|https?://|\.com\b|iframe|youtube", re.I)

E.ekle("flas", ["{ad}, stüdyo ve saha çekimlerinde güçlü, tutarlı ve kontrol edilebilir ışık sağlayan bir flaş çözümüdür.",
                "{ad}, portre, moda ve ürün fotoğrafçılığında profesyonel sonuç almak isteyenler için tasarlanmış bir stüdyo flaşıdır."],
       ["Portre ve moda stüdyoları", "Ürün ve e-ticaret çekimleri", "Düğün, etkinlik ve dış mekân çekimleri"], [],
       [("Tutarlı Işık", "Ardışık çekimlerde renk ve güç tutarlılığı sağlar."),
        ("Hassas Güç Ayarı", "Işık gücünü ihtiyaca göre ince ayarlarla belirlemenize imkân tanır."),
        ("Geniş Aksesuar Uyumu", "Softbox, reflektör ve şemsiye gibi ışık şekillendiricilerle kullanılabilir.")],
       [("Hangi ışık şekillendiricilerle uyumludur?", "Ürünün montaj sistemine uygun softbox, reflektör ve şemsiyelerle kullanılabilir; uyum konusunda bize danışabilirsiniz."),
        ("Kablosuz tetiklenebilir mi?", "Uyumlu tetikleyici/alıcı ile kablosuz olarak tetiklenebilir; detaylar için ürün bilgilerine bakabilirsiniz.")])
E.ekle("kalibrasyon", ["{ad}, ekran ve çekim renklerinizi doğru ve tutarlı hale getirmek için kullanılan bir renk yönetimi ürünüdür."],
       ["Fotoğraf düzenleme ve rötuş", "Baskı öncesi renk doğruluğu", "Video renk düzenleme"], [],
       [("Renk Doğruluğu", "Gördüğünüz renklerin gerçeğe ve baskıya yakın olmasını sağlar."),
        ("Tutarlılık", "Farklı ekranlar ve cihazlar arasında renk tutarlılığı sağlar."),
        ("Profesyonel İş Akışı", "Fotoğraf ve video düzenleme süreçlerini hızlandırır.")],
       [("Ne sıklıkla kalibrasyon yapılmalı?", "Profesyonel kullanımda ekranların ayda bir kalibre edilmesi önerilir.")])
E.ekle("mikrofon", ["{ad}, video ve içerik çekimlerinde net ve anlaşılır ses kaydı için tasarlanmış bir mikrofon setidir."],
       ["Röportaj ve vlog çekimleri", "YouTube ve sosyal medya içerikleri", "Eğitim ve sunum videoları"], [],
       [("Net Ses", "Konuşma sesini ortam gürültüsünden ayırarak daha anlaşılır kayıt sağlar."),
        ("Kolay Kurulum", "Kamera veya telefona hızlıca bağlanır."), ("Taşınabilirlik", "Hafif yapısıyla her yere taşınabilir.")],
       [("Telefonla kullanılabilir mi?", "Uygun bağlantı/adaptör ile akıllı telefonlarla da kullanılabilir.")])
E.ekle("karanlikoda", ["{ad}, analog fotoğrafçılık ve film banyosu süreçlerinde kullanılan bir karanlık oda ekipmanıdır."],
       ["Film banyosu ve baskı", "Analog fotoğraf atölyeleri", "Hobi ve eğitim amaçlı kullanım"], [],
       [("Pratik Kullanım", "Karanlık oda işlemlerini kolaylaştırır."), ("Dayanıklı Yapı", "Kimyasallara karşı dayanıklı malzemeden üretilmiştir."),
        ("Analog Fotoğrafçılık", "Film fotoğrafçılığı tutkunları için tasarlanmıştır.")],
       [("Yeni başlayanlar için uygun mu?", "Evet, analog fotoğrafçılığa başlayanlar için de pratik bir yardımcıdır.")])
E.ekle("kumanda", ["{ad}, fotoğraf makinesini dokunmadan tetikleyerek titreşimsiz çekim yapmanızı sağlayan bir uzaktan kumandadır."],
       ["Uzun pozlama ve gece çekimleri", "Makro ve ürün fotoğrafçılığı", "Zaman atlamalı (timelapse) çekimler"], [],
       [("Titreşimsiz Çekim", "Deklanşöre dokunmadan çekim yaparak netliği korur."), ("Kolay Kullanım", "Tak ve kullan yapısındadır."),
        ("Uyumluluk", "Ürün adında belirtilen makine sistemleriyle kullanılır.")],
       [("Makineme uyar mı?", "Ürün adındaki uyumlu sistem bilgisini makinenizle karşılaştırın veya bize sorun.")])


E.ekle("isikaks", ["{ad}, stüdyo flaşı ve ışık sisteminizi tamamlayan, ışığı daha verimli kullanmanızı sağlayan bir aksesuardır."],
       ["Stüdyo ışık kurulumları", "Portre ve ürün çekimleri", "Mevcut ışık sisteminin geliştirilmesi"], [],
       [("Sistem Uyumu", "Uyumlu ışık sistemleriyle doğrudan kullanılır."), ("Işık Kontrolü", "Işığın yönünü ve karakterini şekillendirmenize yardımcı olur."),
        ("Profesyonel Kalite", "Yoğun stüdyo kullanımına uygun üretilmiştir.")],
       [("Hangi flaşlarla uyumlu?", "Ürün adında belirtilen sistem/montaj ile uyumludur; emin olmak için bize danışabilirsiniz.")])
E.T["tripodaks"] = dict(E.T["tripodaks"], temel=[
    ("Hızlı Bağlantı", "Ekipmanı tripod ve başlıklara hızlı ve güvenli şekilde bağlamanızı sağlar."),
    ("Sağlam Yapı", "Metal gövdesi uzun süreli kullanımda güvenilir bağlantı sunar."),
    ("Sistem Uyumu", "Uyumlu tripod ve başlık sistemleriyle birlikte kullanılır.")])
E.T["baslik"] = dict(E.T["baslik"], temel=[
    ("Hassas Ayar", "Kadrajı istediğiniz açıya hassas biçimde ayarlamanızı sağlar."),
    ("Güvenli Kilit", "Kilit mekanizması makineyi istenen konumda sabit tutar."),
    ("Hızlı Bağlantı", "Hızlı bağlantı plakası ile makineyi kolayca takıp çıkarırsınız.")])
E.T["monopod"] = dict(E.T["monopod"], temel=[
    ("Hareket Özgürlüğü", "Tripoda göre çok daha hızlı konum değiştirmenizi sağlar."),
    ("Destek", "Ağır objektiflerin yükünü taşıyarak kol yorgunluğunu azaltır."),
    ("Kompakt Yapı", "Kapalı hâlde az yer kaplar ve kolay taşınır.")])


def tur(ana, ad):
    a, k = ad.lower(), ana.lower()
    if re.search(r"plate|plaka|leveling|quick.?release|arca", a):
        return "tripodaks"
    if re.search(r"ampul|fanus|deflector|grid|snoot|hi-?sync|bayonet|speedring", a):
        return "isikaks"
    if re.search(r"format mask|slayt|giyotin|negatif|banyo|büyüteç|lup\b", a):
        return "karanlikoda"
    if re.search(r"kablo deklanşör|deklanşör|remote|kumanda", a):
        return "kumanda"
    if re.search(r"phone holder|telefon", a):
        return "telefon"
    if re.search(r"küp stüdyo|aydınlatma|gün ışığı|lightbox", a):
        return "isik"
    if re.search(r"capsule|pouch|wallet|insert", a):
        return "kilif"
    if re.search(r"adapt[oe]r ring|filtre tutucu|filter holder|filtre taşıyıcı|lens adaptor", a):
        return "lensaks"
    if re.search(r"black mist|siyah sis|mist", a):
        return "renkfiltre"
    if re.search(r"spyder|kalibr", a):
        return "kalibrasyon"
    if "mikrofon" in k or re.search(r"mikrofon|microphone", a):
        return "mikrofon"
    if re.search(r"\bnd\b|nd ?\d|stopper|neutral density", a) and "filt" in a + k:
        return "nd"
    if re.search(r"polariz|\bcpl\b", a):
        return "cpl"
    if re.search(r"\buv\b|protector|skylight", a):
        return "uv"
    if re.search(r"adapt[oö]r ring|holder|tutucu|filter slot|hood", a) and "filt" in k:
        return "lensaks"
    if "filt" in k:
        return "filtreset" if re.search(r"set|kit", a) else "renkfiltre"
    if re.search(r"kumanda|remote", a):
        return "kumanda"
    if re.search(r"banyo|tank|ölçek|maşa|tepsi|değiştirme torbası|kimyasal|film", a) and "kaiser" in a:
        return "karanlikoda"
    if re.search(r"askı|strap", a) and "çanta" not in a:
        return "aski"
    if re.search(r"tekerlekli|spinner|roller|trolley", a):
        return "tekerlekli"
    if re.search(r"sırt|backpack", a):
        return "sirt"
    if re.search(r"hardcase|tool box|case\b", a):
        return "hardcase"
    if "çanta" in k or re.search(r"çanta|bag|sling|pouch|wallet|insert", a):
        return "omuz" if re.search(r"omuz|shoulder|messenger|sling", a) else "kilif"
    if re.search(r"gimbal", a):
        return "gimbal"
    if re.search(r"slider|rail", a):
        return "slider"
    if re.search(r"monopod", a):
        return "monopod"
    if re.search(r"mini|tabletop|pocketpod|koalapod", a) and "tripod" in a:
        return "minitripod"
    if re.search(r"video.*(tripod|kafa)|fluid", a):
        return "videotripod"
    if re.search(r"kafa|head|ball|\bbaşlık", a) and "flash head" not in a:
        return "baslik"
    if re.search(r"plate|plaka|leveling|spreader|dolly|mount|adaptör|clamp|kelepçe", a) and "tripod" in k + a:
        return "tripodaks"
    if "tripod" in k or "tripod" in a:
        return "tripod"
    if re.search(r"softbox|rotalux|octa|strip|recta", a):
        return "softbox"
    if re.search(r"şemsiye|umbrella", a):
        return "semsiye"
    if re.search(r"reflekt|reflector", a):
        return "tas"
    if re.search(r"ayağı|ayak|stand\b|boom|deve boynu", a) and "copy stand" not in a:
        return "ayak"
    if re.search(r"skyport|transmitter|receiver|tetik|trigger", a):
        return "tetik"
    if re.search(r"tüp|tube", a):
        return "tup"
    if re.search(r"flash|flaş|elc|d-lite|ranger|elb|monolight|\bkit\b|set", a) and "elinchrom" in a:
        return "flas"
    if re.search(r"led|video ışı|video işı|panel|copy stand|lightbox|ışık", a):
        return "isik"
    if re.search(r"batarya|battery|şarj|charger", a):
        return "batarya"
    if re.search(r"temizl|clean|kapak|cap\b|koruyucu", a):
        return "lensaks"
    return "aksesuar"


KAT_AD = {"flas": "Stüdyo Flaşları", "kalibrasyon": "Renk Kalibrasyonu", "mikrofon": "Mikrofonlar",
          "nd": "ND Filtreler", "cpl": "Polarize Filtreler", "uv": "UV Filtreler", "lensaks": "Filtre ve Lens Aksesuarları",
          "filtreset": "Filtre Setleri", "renkfiltre": "Filtreler", "kumanda": "Uzaktan Kumandalar",
          "karanlikoda": "Karanlık Oda Ekipmanları", "aski": "Kamera Askıları", "tekerlekli": "Tekerlekli Çantalar",
          "sirt": "Sırt Çantaları", "hardcase": "Taşıma Kutuları", "omuz": "Omuz Çantaları", "kilif": "Çanta ve Kılıflar",
          "gimbal": "Gimballar", "slider": "Sliderlar", "monopod": "Monopodlar", "minitripod": "Mini Tripodlar",
          "videotripod": "Video Tripodlar", "baslik": "Tripod Başlıkları", "tripodaks": "Tripod Aksesuarları",
          "tripod": "Tripodlar", "softbox": "Softboxlar", "semsiye": "Stüdyo Şemsiyeleri", "tas": "Reflektörler",
          "ayak": "Işık Ayakları", "tetik": "Tetikleyiciler", "tup": "Flaş Tüpleri", "isik": "Işık ve Aydınlatma",
          "batarya": "Batarya ve Şarj", "aksesuar": "Fotoğraf Aksesuarları",
          "isikaks": "Işık Aksesuarları", "telefon": "Telefon Tutucular"}


def fiyat_yaz(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def uret(yaz=True):
    xml = open(HAM, encoding="utf-8").read()
    items = [i for i in re.findall(r"<item>.*?</item>", xml, re.S)
             if float(E.alan(i, "stockAmount") or 0) > 0 and float(E.alan(i, "price1") or 0) > 0
             and E.alan(i, "stockCode") not in HARIC]
    items.sort(key=lambda i: (E.alan(i, "brand"), E.alan(i, "mainCategory"), E.alan(i, "label")))
    urunler, kaynak, gor = [], [], set()
    for i in items:
        kod = E.alan(i, "stockCode")
        if kod.lower() in gor:
            continue
        gor.add(kod.lower())
        marka_ham = E.alan(i, "brand")
        marka = MARKA.get(marka_ham, marka_ham)
        ad = re.sub(r"\s+", " ", E.alan(i, "label")).replace("Lensgo", "Lensgo ").replace("Lensgo  ", "Lensgo ").strip()
        sku = f"FE-{KISA.get(marka_ham, 'KMR')}-{ILK_NO + len(urunler)}"
        satirlar = [x for x in E.duz_metin(E.alan(i, "details")) if not FIRMA.search(x)]
        ciftler = [(k, v) for k, v in E.ozellik_ciftleri(satirlar) if not FIRMA.search(k + v)]
        tip = tur(E.alan(i, "mainCategory"), ad)
        imgs = [E.alan(i, f"picture{n}Path") for n in range(1, 9)]
        para = {"TRL": "TRY", "TL": "TRY"}.get(E.alan(i, "currencyAbbr"), E.alan(i, "currencyAbbr") or "TRY")
        fiyat = fiyat_yaz(float(E.alan(i, "price1")) * (1 + MARJ / 100))
        bk = E.alan(i, "barcode") or E.barkod(satirlar)
        urunler.append(dict(id="", name=ad, brand=marka, sku=sku, barcode=bk, price=fiyat, currency=para,
                            stock=str(E.STOK_VAR), availability="https://schema.org/InStock", category=GRUP,
                            description=E.aciklama(ad, marka, KAT_AD.get(tip, "Fotoğraf Aksesuarları"), tip, satirlar, ciftler, sku),
                            status="passive", imgs=[x for x in imgs if x]))
        kaynak.append([sku, f"{KAYNAK_KOK}/{kod}", kod, ad])
    if yaz:
        os.makedirs(os.path.dirname(CIKTI), exist_ok=True)
        with open(CIKTI, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<products>\n')
            for u in urunler:
                f.write(" <product>\n")
                for a in E.ALANLAR:
                    f.write(f"  <{a}>{E.cdata(u[a])}</{a}>\n" if u[a] != "" else f"  <{a}/>\n")
                for k, g in enumerate(u["imgs"][:8], 1):
                    f.write(f"  <image{k}>{E.cdata(g)}</image{k}>\n")
                f.write(" </product>\n")
            f.write("</products>\n")
        with open(KAYNAK, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["sku", "url", "kaynak_kod", "ad"])
            w.writerows(kaynak)
    return urunler


def calistir():
    """sync.py çağırır: data/yeni/kamer.xml yoksa ve ham veri varsa bir kez üretir."""
    if os.path.exists(CIKTI) or not os.path.exists(HAM):
        return
    u = uret()
    print(f"kamer_uret: {len(u)} ürün data/yeni/kamer.xml dosyasına yazıldı")


if __name__ == "__main__":
    calistir()
