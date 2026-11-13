#!/usr/bin/env python3
"""GDX ürünlerini data/ham/gdx.com.tr.json dosyasından Foto Ekspres formatına çevirir.

Çıktı: data/yeni/gdx.xml (yeni ürünler) ve data/yeni/gdx_kaynak.csv (stok kodu -> kaynak link).
data/yeni/gdx.xml zaten varsa hiçbir şey yapmaz (stok kodları bir kez verilir, sonra değişmez).
"""
import csv
import html
import json
import os
import hashlib
import re
from html.parser import HTMLParser

KOK = os.path.dirname(os.path.abspath(__file__))
HAM = os.path.join(KOK, "data", "ham", "gdx.com.tr.json")
CIKTI = os.path.join(KOK, "data", "yeni", "gdx.xml")
KAYNAK = os.path.join(KOK, "data", "yeni", "gdx_kaynak.csv")
ILK_NO = 14296
MARJ = 6.0
GRUP = "GDX"
STOK_VAR = 5

STYLE = "text-align:center;color:#000000;font-family:helvetica, arial, sans-serif;font-size:14pt;"
BOS = "<div>&nbsp;</div>"
NEDEN = ["Resmi Türkiye Garantili ürün", "14 gün içinde ücretsiz iade ve değişim",
         "İstanbul içi kurye ile aynı gün teslimat imkânı", "Sirkeci mağazamızda uzman destek",
         "Havale/EFT ile ödeme seçeneği"]
# Bize ait olmayan satış/kampanya cümleleri açıklamaya alınmaz
YASAK = re.compile(r"gdx\.com|can ?foto|canfoto|taksit|kargo|whatsapp|garanti|kampanya|indirim|stoklarla|"
                   r"sipariş|mağaza|distribüt|teslimat|ücretsiz|iade|fiyat|sepete|satın al|https?://|www\.", re.I)
ALANLAR = ["id", "name", "brand", "sku", "barcode", "price", "currency", "stock", "availability",
           "category", "description", "status"]


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bosluk(s):
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()


def baslik_duzelt(t):
    """BÜYÜK HARF başlığı Türkçe kurallarıyla 'Başlık Biçimi'ne çevirir."""
    t = bosluk(t).rstrip(":").strip()
    if t != t.upper():
        return t
    kelimeler = []
    for k in t.split(" "):
        if re.fullmatch(r"[A-Z0-9\-./]{2,}\d[A-Z0-9\-./]*|[A-Z]{2,4}|\d.*", k) and not re.fullmatch(r"VE|İLE|VEYA|İÇİN", k):
            kelimeler.append(k)  # model kodu, kısaltma, sayı
            continue
        k2 = k.replace("I", "ı").replace("İ", "i").lower()
        kelimeler.append(k2[:1].replace("i", "İ").replace("ı", "I").upper() + k2[1:] if k2 not in ("ve", "ile", "veya", "için") else k2)
    return " ".join(kelimeler)


class Bloklar(HTMLParser):
    """Kaynak HTML'i düz bloklara ayırır: h (başlık), p (paragraf), li (madde), tr (tablo satırı)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bloklar, self.yigin, self.metin, self.hucreler, self.hucre = [], [], [], None, None
        self.strong, self.strong_metin, self.atla = 0, [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "iframe"):
            self.atla += 1
        if tag in ("h1", "h2", "h3", "h4", "h5", "p", "li"):
            self._bitir()
            self.yigin.append(tag)
            self.metin, self.strong_metin = [], []
        elif tag == "tr":
            self._bitir()
            self.hucreler = []
        elif tag in ("td", "th") and self.hucreler is not None:
            self.hucre = []
        elif tag in ("strong", "b"):
            self.strong += 1
        elif tag == "br":
            self.metin.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "iframe"):
            self.atla = max(0, self.atla - 1)
        if tag in ("h1", "h2", "h3", "h4", "h5", "p", "li"):
            self._bitir()
        elif tag in ("td", "th") and self.hucre is not None:
            self.hucreler.append(bosluk("".join(self.hucre)))
            self.hucre = None
        elif tag == "tr" and self.hucreler is not None:
            h = [x for x in self.hucreler if x]
            if h:
                self.bloklar.append(("tr", h))
            self.hucreler = None
        elif tag in ("strong", "b"):
            self.strong = max(0, self.strong - 1)

    def handle_data(self, data):
        if self.atla:
            return
        if self.hucre is not None:
            self.hucre.append(data)
            return
        if self.yigin:
            self.metin.append(data)
            if self.strong:
                self.strong_metin.append(data)
        elif data.strip():
            self.bloklar.append(("p", bosluk(data)))

    def _bitir(self):
        if not self.yigin:
            return
        tag = self.yigin.pop()
        t = "".join(self.metin)
        s = bosluk("".join(self.strong_metin))
        self.metin, self.strong_metin = [], []
        if tag.startswith("h"):
            if bosluk(t):
                self.bloklar.append(("h", bosluk(t)))
        elif tag == "li":
            t = bosluk(t)
            if t:
                if s and t.startswith(s) and len(s) < len(t):
                    self.bloklar.append(("li", (s.rstrip(":").strip(), t[len(s):].lstrip(" :").strip())))
                else:
                    self.bloklar.append(("li", ("", t)))
        else:
            for parca in t.split("\n"):
                parca = bosluk(parca)
                if parca:
                    self.bloklar.append(("p", parca))


def tur(baslik):
    b = baslik.upper().translate(str.maketrans("İÇĞÖŞÜ", "ICGOSU"))
    if re.search(r"TEKNIK|PARAMETRE|SPESIFIK", b):
        return "teknik"
    if re.search(r"ICERI|KUTUDA|PAKETTE", b):
        return "kutu"
    if re.search(r"UYUMLU|UYUMLULUK", b):
        return "uyum"
    if re.search(r"KULLANIM ALAN|SENARYO|KULLANIM YELPAZE|KIMLER", b):
        return "kullanim"
    if re.search(r"SAKLAMA|BAKIM|BILGILENDIRME|ONEMLI BILGI|UYARI|NOT\b", b):
        return "bakim"
    if re.search(r"OZELLIK|AVANTAJ|ONE CIKAN|AYRICALIK", b):
        return "ozellik"
    return "diger"


SLOGAN = re.compile(r"ENGINEERED FOR|^GDX\s*[|™]", re.I)


def temiz_cumle(t):
    """Yasaklı (satış/kampanya) ifadeleri içeren cümleleri çıkarır."""
    t = re.sub(r"^\s*[-–•▪·]\s*", "", t or "")
    if SLOGAN.search(t):
        return ""
    cumleler = re.split(r"(?<=[.!?])\s+", t)
    return " ".join(c for c in cumleler if c and not YASAK.search(c)).strip()


def ayristir(urun):
    p = Bloklar()
    p.feed(urun.get("body_html") or "")
    p._bitir()
    ad = bosluk(urun["title"])
    bolumler, aktif = [], {"tur": "giris", "baslik": "", "p": [], "li": [], "tr": []}
    for tip, v in p.bloklar:
        if tip == "h":
            if bosluk(v).lower() == ad.lower() or (v == v.upper() and len(v) < 70 and v.startswith("GDX") and not aktif["p"]):
                continue
            if aktif["tur"] == "giris" and not aktif["p"] and not aktif["li"] and not bolumler and len(v) > 40:
                aktif["p"].append(v)  # ürün alt başlığı -> giriş cümlesi
                continue
            bolumler.append(aktif)
            aktif = {"tur": tur(v), "baslik": baslik_duzelt(v), "p": [], "li": [], "tr": []}
        elif tip == "p":
            if re.match(r"^(Ürün Kodu|SKU|Stok Kodu)\s*:", v, re.I):
                v = re.sub(r"^(Ürün Kodu|SKU|Stok Kodu)\s*:\s*\S+\s*", "", v, flags=re.I)
            v = temiz_cumle(v)
            if v and v == v.upper() and len(v) < 70 and v.startswith("GDX"):
                continue  # "GDX PROFESYONEL ... SETLERİ" gibi rozet yazıları
            if v:
                aktif["p"].append(v)
        elif tip == "li":
            b, t = v
            b = re.sub(r"^\s*[-–•▪·]\s*", "", b)
            t = temiz_cumle(t) if t else ""
            if (b or t) and not YASAK.search(b):
                aktif["li"].append((b, t))
        elif tip == "tr":
            aktif["tr"].append(v)
    bolumler.append(aktif)
    return [b for b in bolumler if b["p"] or b["li"] or b["tr"]]


def satir_li(b, t):
    if b and t:
        return f"<div><strong>{esc(b)}:</strong> {esc(t)}</div>"
    return f"<div>{esc(b or t)}</div>"


def teknik_satirlar(bol):
    """Tablo satırlarını 'Özellik: Değer' satırlarına çevirir (mobilde tema bunları tabloya dönüştürür)."""
    cikti, ciftler = [], []
    for h in bol["tr"]:
        if len(h) == 1:
            if not re.search(r"(?i)^(özellik|parametre|değer|açıklama)$", h[0]):
                cikti.append(("b", h[0]))
        elif len(h) >= 2:
            if re.fullmatch(r"(?i)(özellik|parametre|teknik özellik)", h[0]) and re.fullmatch(r"(?i)(değer|detay|açıklama|özellik)", h[1]):
                continue
            k, d = h[0].rstrip(":"), " / ".join(h[1:])
            if YASAK.search(k + " " + d) or re.search(r"(?i)ürün kodu|stok kodu|sku|barkod", k):
                continue
            cikti.append(("kv", k, d))
            ciftler.append((k, d))
    for b, t in bol["li"]:
        if b and t:
            cikti.append(("kv", b, t))
            ciftler.append((b, t))
        elif t and ":" in t[:40]:
            k, d = t.split(":", 1)
            cikti.append(("kv", k.strip(), d.strip()))
            ciftler.append((k.strip(), d.strip()))
    return cikti, ciftler


SSS_KURAL = [
    (r"renk sıcaklı|kelvin|cct", "Renk sıcaklığı aralığı nedir?", "Ürünün renk sıcaklığı değeri: {v}."),
    (r"\bcri\b|tlci|renk doğruluğu|renk geri", "Renk doğruluğu (CRI/TLCI) değerleri nedir?", "Ürünün renk doğruluğu değeri: {v}."),
    (r"^(güç|maksimum güç|nominal güç|çıkış gücü|toplam güç|watt|flaş gücü|enerji)", "Gücü ne kadar?", "Ürünün güç değeri: {v}."),
    (r"güç kaynağı|batarya|pil|adaptör|besleme|şarj", "Nasıl çalışır, güç kaynağı nedir?", "Güç bilgisi: {v}."),
    (r"montaj|bağlantı|bowens|yuva|soket|vida|bağlantı tipi", "Montaj ve bağlantı yapısı nasıl?", "Bağlantı bilgisi: {v}."),
    (r"kontrol|uygulama|app|dmx|kablosuz|bluetooth|kumanda", "Nasıl kontrol edilir?", "Kontrol seçenekleri: {v}."),
    (r"ölçü|boyut|ebat|genişlik|uzunluk|yükseklik|çap", "Ölçüleri nedir?", "Ürünün ölçü bilgisi: {v}."),
    (r"ağırlık", "Ağırlığı ne kadar?", "Ürünün ağırlığı: {v}."),
    (r"malzeme|materyal|kumaş|gövde", "Hangi malzemeden üretilmiştir?", "Malzeme bilgisi: {v}."),
]


def sss_uret(ciftler, kutu):
    sss, kullanilan = [], set()
    for desen, soru, cevap in SSS_KURAL:
        if len(sss) >= 4:
            break
        for k, d in ciftler:
            if re.search(desen, k, re.I) and soru not in kullanilan and d not in kullanilan and len(d) < 160:
                sss.append((soru, cevap.format(v=d.rstrip("."))))
                kullanilan.update((soru, d))
                break
    if kutu:
        parcalar = [(b or t) for b, t in kutu if (b or t)][:10]
        if parcalar:
            sss.append(("Kutudan neler çıkıyor?", "Pakette " + ", ".join(p.rstrip(".") for p in parcalar) + " bulunur."))
    return sss


# Kaynak açıklaması hatalı (başka ürüne ait) ya da boş olan ürünler için açıklama kaynağı
CANFOTO = os.path.join(KOK, "data", "ham", "canfoto.com.json")
BASKA_KAYNAK = {
    # GDX sitesinde açıklama başka ürüne ait (kırmızı kağıt fon); aynı reflektörün RF-90120 açıklaması kullanılır
    "gdx-90x120-cm-5-in-1-tutuculu-reflektor-seti-gumus-altin-beyaz-siyah-difuzor-yansitici-panel":
        ("gdx", "gdx-rf-90120-5-in-1-reflektor-yansitici-seti-90x120-cm",
         "Bu set, reflektörü ışık ayağına veya el tutucusuna sabitlemek için kullanılan reflektör tutucusu ile birlikte sunulur."),
    # GDX sitesinde açıklama boş; Can Foto'daki aynı ürünün açıklaması kullanılır
    "gdx-snoot-pro-i": ("canfoto", "gdx-snoot-pro-i", ""),
    "gdx-110-cm-5-in-1-tutuculu-reflektor-seti-gumus-altin-beyaz-siyah-difuzor-yansitici-panel": ("canfoto", None, ""),
    "gdx-60-cm-5-in-1-reflektor-seti-tutuculu-gumus-altin-beyaz-siyah-difuzor-yansitici-panel": ("canfoto", None, ""),
    "gdx-80-cm-tutuculu-5li-reflektor-seti-katlanabilir-yuvarlak-isik-yansitici-ve-yumusatici": ("canfoto", None, ""),
    # GDX sitesinde açıklamada model FX4 yazıyor; Can Foto'da doğru FX6 açıklaması var
    "gdx-fx6-fon-tutucu-4lu-mandal-clamp-profesyonel-arka-plan-sabitleme-mandali": ("canfoto", None, ""),
}
# Hiçbir kaynakta doğru açıklaması olmayan ürünler: sadece ürün adındaki bilgilerden yazıldı
ELLE = {
    "gdx-gb-05-bowens-mount-odak-ayarli-optik-projeksiyon-snoot-ve-gobo-projektor-basligi": dict(
        giris=["GDX GB-05, Bowens montajlı stüdyo ışıklarının önüne takılarak ışığı dar ve kontrollü bir huzme halinde toplayan, odak ayarlı optik projeksiyon snoot ve gobo projektör başlığıdır.",
               "Optik lens yapısı sayesinde ışığın kenar keskinliği ayarlanabilir; gobo şablonları kullanılarak arka plana, ürüne veya modele desenli ışık yansıtılabilir. Böylece tek bir ışıkla sahneye derinlik, vurgu ve yaratıcı efektler katılır."],
        ozellik=[("Bowens Montaj", "Bowens yuvalı sürekli ışıklara ve paraflaşlara doğrudan takılır."),
                 ("Odak Ayarı", "Optik lens ile ışık huzmesinin kenarları yumuşak veya keskin olacak şekilde ayarlanabilir."),
                 ("Gobo Projeksiyonu", "Gobo şablonlarıyla arka plana desen, logo veya pencere gölgesi gibi efektler yansıtılabilir."),
                 ("Kontrollü Işık", "Işığı sadece istenen bölgeye yönlendirerek sahnenin geri kalanına taşmasını önler.")],
        kullanim=["Ürün ve kozmetik çekimlerinde vurgu ışığı", "Portre ve moda çekimlerinde yaratıcı arka plan efektleri",
                  "Video prodüksiyonlarında desenli ve sinematik aydınlatma", "Etkinlik ve sahnelerde logo veya desen yansıtma"],
        sss=[("Hangi ışıklarla kullanılır?", "Bowens montaj yuvasına sahip sürekli ışıklar ve paraflaşlarla kullanılır."),
             ("Ne işe yarar?", "Işığı dar bir alana toplar, odak ayarıyla kenar keskinliğini belirlemenizi ve gobo şablonlarıyla desen yansıtmanızı sağlar.")]),
    "gdx-temizlik-9-in-1-fotograf-makinesi-ve-lens-temizlik-seti-hava-pompali-full-bakim": dict(
        giris=["GDX 9 in 1 Temizlik Seti, fotoğraf makinesi, lens ve filtrelerin günlük bakımını güvenle yapabilmeniz için hazırlanmış, hava pompalı ve 9 parçalı eksiksiz bir bakım setidir.",
               "Hava pompası ile toz ve kum gibi parçacıklar yüzeye dokunmadan uzaklaştırılır; setteki diğer temizlik aparatlarıyla lens, ekran ve gövde yüzeyleri çizilmeden temizlenir. Çantanızda kolayca taşınabilir ve çekim öncesi hızlı bakım için idealdir."],
        ozellik=[("9 Parçalı Set", "Fotoğraf makinesi ve lens bakımı için gereken temel temizlik aparatları tek pakette."),
                 ("Hava Pompası", "Toz ve parçacıkları lens ve sensör çevresinden temas etmeden uzaklaştırır."),
                 ("Güvenli Temizlik", "Lens, filtre ve ekran yüzeylerinin çizilmeden temizlenmesine yardımcı olur."),
                 ("Taşınabilir", "Kompakt yapısıyla çekim çantasında kolayca taşınır.")],
        kullanim=["Fotoğraf makinesi gövdesi ve ekran temizliği", "Lens ve filtre camlarının temizliği",
                  "Çekim öncesi ve sonrası rutin ekipman bakımı", "Dış mekan çekimlerinde toz ve kirden korunma"],
        sss=[("Hangi ekipmanlarda kullanılabilir?", "Fotoğraf makineleri, lensler, filtreler, aksiyon kameralar ve ekranlı cihazların temizliğinde kullanılabilir."),
             ("Hava pompası ne işe yarar?", "Toz ve parçacıkları yüzeye dokunmadan üfleyerek uzaklaştırır, böylece çizilme riskini azaltır.")]),
    "gdx-tekli-dx-1-duy": dict(
        giris=["GDX Tekli DX-1 Duy, sürekli ışık ampullerini stüdyo ışık ayağı üzerinde kullanmanızı sağlayan tekli duy aparatıdır.",
               "Işık ayağına sabitlenerek ampulün istediğiniz yükseklik ve açıda konumlandırılmasına imkân verir. Basit ve sağlam yapısıyla ürün çekimi, vesikalık ve küçük stüdyo kurulumlarında pratik bir sürekli ışık çözümü oluşturur."],
        ozellik=[("Tekli Duy", "Tek ampul ile kullanılan sade ve pratik yapı."),
                 ("Ayak Montajı", "Stüdyo ışık ayağına takılarak kullanılır."),
                 ("Açı Ayarı", "Işığın yönünü çekim ihtiyacına göre ayarlamaya yardımcı olur."),
                 ("Kolay Kurulum", "Hızlıca kurulup sökülebilir, stüdyo içinde kolayca taşınır.")],
        kullanim=["Küçük stüdyo ve ürün çekimi kurulumları", "Vesikalık ve portre çekimlerinde sürekli ışık",
                  "Video ve canlı yayınlarda ek aydınlatma"],
        sss=[("Ampul dahil mi?", "Ürün adında ampul belirtilmediği için ampul ayrıca temin edilmelidir."),
             ("Nasıl kullanılır?", "Duy ışık ayağına takılır, ampul duya yerleştirilir ve ışığın yönü ayarlanarak kullanılır.")]),
}


def elle_aciklama(ad, a):
    out = [f'<div style="{STYLE}">', f"<div><strong>{esc(ad)}</strong></div>", BOS]
    for p in a["giris"]:
        out += [f"<div>{esc(p)}</div>", BOS]
    out.append("<div><strong>Öne Çıkan Özellikler</strong></div>")
    out += [satir_li(b, t) for b, t in a["ozellik"]] + [BOS]
    out.append("<div><strong>Kullanım Alanları</strong></div>")
    out += [f"<div>{esc(x)}</div>" for x in a["kullanim"]] + [BOS]
    out.append("<div><strong>Sık Sorulan Sorular</strong></div>")
    for i, (q, c) in enumerate(a["sss"]):
        out += [f"<div><strong>{esc(q)}</strong></div>", f"<div>{esc(c)}</div>"]
        if i < len(a["sss"]) - 1:
            out.append(BOS)
    out += [BOS, "<div><strong>Neden Foto Ekspres?</strong></div>"] + [f"<div>{x}</div>" for x in NEDEN] + ["</div>"]
    return "\n".join(out)


_HAM_ON = {}


def ham_bul(site, handle, sku):
    if site not in _HAM_ON:
        yol = HAM if site == "gdx" else CANFOTO
        _HAM_ON[site] = json.load(open(yol, encoding="utf-8")) if os.path.exists(yol) else []
    for u in _HAM_ON[site]:
        if u.get("handle") == handle:
            return u
    return None


# ---------------------------------------------------------------- özgün açıklama yazarı
# Kaynak metnin cümleleri kullanılmaz. Ürün adı ve teknik tablodan alınan bilgilerle
# Foto Ekspres'in kendi cümleleri kurulur. Teknik değerler ve kutu içeriği olduğu gibi kalır.


def _sec(sku, secenekler, tuz=""):
    """Aynı ailedeki ürünlerde farklı cümle seçilmesi için stok koduna göre sabit seçim."""
    h = int(hashlib.md5((sku + tuz).encode()).hexdigest(), 16)
    return secenekler[h % len(secenekler)]


def _ara(ciftler, desen, uzun=90):
    for k, d in ciftler:
        if re.search(desen, k, re.I) and d and len(d) <= uzun:
            return d.strip().rstrip(".")
    return ""


RENKLER = [("beyaz", r"\bbeyaz\b|white"), ("siyah", r"\bsiyah\b|black"), ("gri", r"\bgri\b|grey|gray"),
           ("yeşil", r"\byeşil\b|green|chroma"), ("kırmızı", r"kırmızı|\bred\b|crimson"), ("mavi", r"\bmavi\b|blue"),
           ("pembe", r"pembe|pink|tulip"), ("mor", r"\bmor\b|purple"), ("sarı", r"\bsarı\b|yellow|canary"),
           ("turkuaz", r"turkuaz|turquoise"), ("kahverengi", r"kahve|chestnut"), ("turuncu", r"turuncu|tangelo"),
           ("krem", r"\bkrem\b|egg nog|\bbej\b"), ("mercan", r"mercan|coral")]


def ozellikler_cikar(ad, ciftler, tip):
    a = {}
    t = ad
    m = re.search(r"^GDX\.?\s+((?:[A-Z]{1,6}[\- ]?\d{1,4}[A-Z]{0,4}(?:[\- ][A-Z]{1,5})?|[A-Z]+[\- ]?[A-Z]*\d+)(?:\s+(?:II|III|Pro|PRO|R|C|RGB|Plus))?)\b", t)
    a["model"] = m.group(1).strip() if m else ""
    m = re.search(r"(\d{2,4})\s?W\b", t)
    a["guc"] = (m.group(1) + "W") if m else _ara(ciftler, r"^(güç|maksimum güç|güç çıkışı|güç kapasitesi|model / güç)")
    havuz = t + " | " + " | ".join(d for k, d in ciftler if re.search(r"renk sıcaklı|cct|cri|renk doğru|tlci", k, re.I))
    m = re.search(r"(\d{4})\s?K?\s?[-–~]\s?(\d{4,5})\s?K", havuz)
    a["cct"] = f"{m.group(1)}K – {m.group(2)}K" if m else ""
    m = (re.search(r"(?:CRI|Ra)\s*(?:/\s*Ra\s*)?[≥>]?\s*(\d{2}\+?)", havuz) or re.search(r"[≥>]\s*(9\d\+?)", havuz)
         or re.search(r"\b(9\d\+?)\s*Ra\b", havuz))
    a["cri"] = ("CRI " + m.group(1)) if m else ""
    a["rgb"] = bool(re.search(r"RGB", t, re.I))
    a["bicolor"] = bool(re.search(r"bi-?colou?r", t, re.I))
    a["bowens"] = bool(re.search(r"bowens", t + " " + " ".join(d for _, d in ciftler), re.I))
    a["adet"] = 2 if re.search(r"ikili|2['’]?\s?li|2'li|twin", t, re.I) else 3 if re.search(r"3['’]?\s?lü|üçlü", t, re.I) else 1
    m = re.search(r"(\d{3})\s?cm\s+(?:Kalın\s+|Metal\s+)?(?:Işık\s+)?Aya", t)
    a["ayak"] = m.group(1) + " cm" if m else ""
    m = re.search(r"(\d{2,3}\s?[x×]\s?\d{2,3})\s?(?:cm)?\s*(?:Gridli\s+)?(?:Dikdörtgen\s+)?(?:Softbox|Gridli)", t, re.I)
    m2 = re.search(r"(\d{2,3})\s?cm\s+(?:Gridli\s+)?(?:Octa|Oktagon|Parabolik)", t, re.I)
    a["softbox"] = (m.group(1).replace(" ", "") + " cm") if m else (m2.group(1) + " cm" if m2 else "")
    m = re.search(r"(\d+[.,]?\d*\s?[x×]\s?\d+[.,]?\d*)\s?(m\b|cm|metre)?", t, re.I)
    a["olcu"] = (m.group(1).replace(" ", "") + " " + ((m.group(2) or "").replace("metre", "m"))).strip() if m else _ara(ciftler, r"ölçü|boyut|fon ölçü", 60)
    a["renk"] = next((r for r, d in RENKLER if re.search(d, t, re.I)), "")
    a["malzeme"] = _ara(ciftler, r"^(malzeme|gövde malzemesi|materyal|malzeme yapısı|malzeme tipi)", 70)
    a["batarya"] = _ara(ciftler, r"batarya|güç kaynağı|pil", 80)
    if not a["batarya"]:
        a["batarya"] = "V-Mount" if re.search(r"v-?mount", t, re.I) else ("NP-F" if re.search(r"np-?f", t, re.I) else "")
    metin_k = t + " " + " ".join(f"{a1} {b1}" for a1, b1 in ciftler if not re.search(r"(?i)alan|amaç", a1))
    k = [x for x, d in [("DMX", r"dmx"), ("Bluetooth/uygulama", r"bluetooth|\bapp\b|mobil uygulama"), ("uzaktan kumanda", r"kumanda|remote")]
         if re.search(d, metin_k, re.I)]
    a["kontrol"] = k
    m = re.search(r"(\d{1,3})\s?(?:FX|Efekt)", t, re.I)
    a["efekt"] = m.group(1) if m else ""
    a["lumen"] = _ara(ciftler, r"ışık akısı|lümen", 50)
    m = re.search(r"(\d{1,3})\s?kg", t, re.I)
    a["kapasite"] = (m.group(1) + " kg") if m else _ara(ciftler, r"taşıma kapasitesi|yük kapasitesi", 40)
    a["yukseklik"] = _ara(ciftler, r"maksimum yükseklik|stand yüksekliği|maksimum uzunluk", 40)
    m = re.search(r"(\d{3})\s?g\b", t)
    a["gramaj"] = (m.group(1) + " g/m²") if m else _ara(ciftler, r"kağıt yoğunluğu|gramaj", 40)
    m = re.search(r"\b(\d{2,3})\s?cm\b", t)
    a["boy"] = (m.group(1) + " cm") if m else ""
    a["seyyar"] = bool(re.search(r"seyyar|taşınabilir|standlı|ayaklı", t, re.I))
    a["sabit"] = bool(re.search(r"sabit|duvar|tavan", t, re.I))
    a["mekanizma"] = bool(re.search(r"mekanizma|zincir|makara", t, re.I))
    return a


def tr_ust(s):
    return (s or "").replace("i", "İ").replace("ı", "I").upper()


def kategori(ad, tip):
    t, p = tr_ust(ad), tr_ust(tip)
    if alt_tur(ad):
        return "aksesuar"
    if "KAĞIT" in t and re.search(r"\bFON", t):
        return "kagit"
    if "PVC" in t and "MASA" not in t:
        return "pvc"
    if re.search(r"PARAFLAŞ|BM400", t):
        return "flas"
    if "SOFTBOX" in t and not re.search(r"\d{2,4}\s?W\b", t):
        return "sekil"
    if "ÇEKİM MASASI" in t:
        return "masa"
    if "ÇADIR" in t or "ÇEKİM KUTUSU" in t:
        return "cadir"
    if "DÖNER TABLA" in t:
        return "tabla"
    if re.search(r"\bFON", t) or "ARKA PLAN SET" in t or "GREEN SCREEN" in t:
        return "kumas"
    if "REFLEKTÖR" in t:
        return "reflektor"
    if re.search(r"PARAFLAŞ|BM400", t):
        return "flas"
    if re.search(r"TEPE FLAŞ", t) and "SOFTBOX" not in t:
        return "mobil"
    if re.search(r"TÜP|ÇUBUK|\bTB[- ]?\d|\bST[- ]?\d|LP550", t):
        return "tup"
    if re.search(r"SOFTBOX|OKTA|SNOOT|FRESNEL|GRİD|PETEK|GOBO|ŞEKİLLENDİRİCİ", t + " " + p) and not re.search(r"LED VİDEO IŞI|COB LED (VİDEO|STÜDYO|FOTOĞRAF)? ?IŞI", t):
        if not re.search(r"\d{2,4}\s?W\b", t) or "SOFTBOX" in p or "ŞEKİLLENDİRİCİ" in p:
            return "sekil"
    if re.search(r"POCKET|CEP|VLOG|M\d{1,2}-R|MBL|KAMERA ÜSTÜ|MASAÜSTÜ|SFT-|FENER|P50-R|TELEFON", t) or "MASAÜSTÜ" in p or "VLOG" in p:
        return "mobil"
    if re.search(r"COB|BOWENS|SÜREKLİ IŞIK", t):
        return "cob"
    if re.search(r"LED|PANEL|IŞIK SETİ|SOFT LIGHT", t):
        return "panel"
    return "aksesuar"


ALT = [
    ("kumtorba", r"kum torba"),
    ("vida", r"vida adaptör"),
    ("kiskac", r"\bmandal|kıskaç|clamp|mengene"),
    ("magic", r"magic arm|sihirli kol"),
    ("topkafa", r"top kafa|ball head"),
    ("hotshoe", r"hot ?shoe"),
    ("lbracket", r"l bracket|\bl tipi"),
    ("rig", r"\brig\b|kafes|stabilizer"),
    ("telefon", r"telefon tutucu"),
    ("boom", r"boom|deve boynu"),
    ("teker", r"teker|dolly"),
    ("canta", r"taşıma çantası"),
    ("tprofil", r"t profil|fon barı"),
    ("fonstand", r"fon perde standı"),
    ("montaj", r"askı aparatı|askı sistemi|körüğü|tavan ray|plaka stand|montaj barı"),
    ("mekanizma", r"boru zincir makara seti"),
    ("reftutucu", r"reflektör tutucu"),
    ("isikayak", r"ışık ayağı|ışık standı"),
    ("batarya", r"batarya kolu|çevirici adaptör|güç kaynağı"),
    ("klaket", r"klaket|clapper"),
    ("filtre", r"jelatin"),
    ("minitripod", r"mini tripod|masaüstü .*tripod|tlb holder"),
    ("tripod", r"tripod|monopod"),
    ("temizlik", r"temizlik"),
    ("duy", r"\bduy\b"),
]


def alt_tur(ad):
    t = ad.replace("İ", "i").replace("I", "ı").lower()
    isik = re.search(r"\bled\b|\bcob\b|sürekli ışık|soft light|tüp ışık|panel ışık|\brgb", t) and re.search(r"\d{1,4}\s?w\b|ışığı|ışık seti|ışık set\b|panel|tüp|çubuk|soft light|dolgu", t)
    if isik and not re.search(r"telefon tutucu adaptör|\bkafes|sabitleme kolu|magic arm|hot ?shoe flaş ve aksesuar", t):
        return ""
    if re.search(r"fon (sistemi|seti|perde sistemi)|arka plan seti|green screen seti", t) and re.search(r"\d+\s?[x×]\s?\d+", t):
        return ""
    if re.search(r"tutuculu tripod", t):
        return "tripod"
    for ad_, d in ALT:
        if re.search(d, t):
            return ad_
    return ""


AKS = {
    "kiskac": (["Ekipmanları, fon kenarlarını veya kabloları hızlıca sabitlemek için kullanılan yaylı kıskaç tipi bir tutucudur.",
                "Çekim sırasında kayan fonları, reflektörleri veya hafif aksesuarları yerinde tutarak kurulumu düzenli ve güvenli hale getirir."],
               [("Hızlı Sabitleme", "Tek elle açılıp kapanan yaylı yapısı ile saniyeler içinde takılır."), ("Güçlü Tutuş", "Fon, kumaş ve ince profilleri kaymadan sabit tutar."), ("Çok Amaçlı", "Stüdyoda ve sahada farklı ekipmanlarla kullanılabilir.")],
               ["Fon perdeleri sabitleme", "Reflektör ve difüzör tutturma", "Kablo ve aksesuar düzenleme"]),
    "magic": (["Monitör, LED ışık, mikrofon veya küçük ekipmanları kamera, ışık ayağı ya da masaya istenen açıda bağlamak için kullanılan eklemli bir bağlantı koludur.",
               "Ortadaki kilit mekanizması ile tüm eklemler tek hamlede sabitlenir; ekipmanınız hareket etmeden istediğiniz konumda kalır."],
              [("Eklemli Yapı", "Birden fazla eksende hareket ederek ekipmanı istenen açıya getirir."), ("Tek Noktadan Kilit", "Kilit düğmesi ile kol tek hamlede sabitlenir."), ("Standart Bağlantı", "1/4\" vida bağlantısı ile pek çok aksesuarla uyumludur.")],
              ["Kamera üstü monitör bağlantısı", "LED ışık ve mikrofon konumlandırma", "Masa ve ayak üstü ekipman montajı"]),
    "topkafa": (["Tripod, ışık ayağı veya kamera rigine takılan; kamerayı, ışığı ya da monitörü her yöne çevirip istenen açıda sabitlemeye yarayan top kafa bağlantısıdır.",
                 "Küresel eklemi sayesinde yatay, dikey ve eğik açılara hızlıca geçilir; kilit düğmesiyle ekipman yerinde sabit kalır."],
                [("360° Hareket", "Küresel yapı ile her yöne serbestçe döner."), ("Kilit Mekanizması", "Ayar düğmesi ile istenen açıda güvenle sabitlenir."), ("Metal Gövde", "Kompakt ve dayanıklı yapısıyla uzun süre kullanılır.")],
                ["Tripod üzerinde kamera ve telefon kullanımı", "LED ışık ve monitör konumlandırma", "Vlog ve canlı yayın kurulumları"]),
    "hotshoe": (["Kamera üzerindeki flaş kızağını çoğaltarak mikrofon, LED ışık veya küçük monitör gibi birden fazla aksesuarı aynı anda takmanızı sağlayan bağlantı aparatıdır.",
                 "Hafif yapısıyla kameranın dengesini bozmaz, vlog ve röportaj kurulumlarını tek gövdede toplar."],
                [("Çoklu Bağlantı", "Birden fazla aksesuar aynı anda kameraya takılır."), ("Hot Shoe Uyumu", "Standart flaş kızağı olan kameralarla kullanılır."), ("Hafif Yapı", "Kameraya ek ağırlık bindirmez.")],
                ["Vlog kurulumları", "Kamera üstü mikrofon ve ışık kullanımı", "Röportaj çekimleri"]),
    "lbracket": (["Kamerayı yatay konumdan dikey konuma hızlıca geçirmek için kullanılan L tipi bağlantı plakasıdır; Arca-Swiss uyumlu tripod kafalarına doğrudan oturur.",
                  "Dikey çekimlerde kameranın ağırlık merkezi tripodun üzerinde kalır; böylece hem denge korunur hem de kadraj kaymaz."],
                 [("Hızlı Dikey Geçiş", "Kamera sökülmeden yatay ve dikey arasında geçiş yapılır."), ("Arca-Swiss Uyumu", "Arca-Swiss tip kafalarla doğrudan kullanılır."), ("Dengeli Kullanım", "Dikey çekimde ağırlık merkezi korunur.")],
                 ["Dikey sosyal medya içerikleri", "Portre ve mimari fotoğraf", "Tripodla ürün çekimleri"]),
    "rig": (["Kamera veya telefonu iki elle dengeli tutmak ve üzerine mikrofon, ışık gibi aksesuarlar eklemek için kullanılan tutacaklı bir rig düzeneğidir.",
             "Elde çekimlerde titremeyi azaltır, aksesuar bağlantı noktalarıyla tek parça ve kullanışlı bir çekim seti oluşturur."],
            [("Çift Tutacak", "İki elle kavrama sayesinde daha stabil çekim sağlar."), ("Aksesuar Noktaları", "Mikrofon, ışık ve monitör takmak için bağlantı noktaları sunar."), ("Sağlam Gövde", "Günlük çekim kullanımına dayanıklıdır.")],
            ["Vlog ve sokak röportajları", "Elde video çekimleri", "Etkinlik ve belgesel çekimleri"]),
    "telefon": (["Akıllı telefonu tripoda, ışık ayağına veya selfie çubuğuna bağlamak için kullanılan telefon tutucu adaptördür.",
                 "Yaylı tutucusu farklı telefon genişliklerine uyum sağlar; yatay ve dikey çekimler için telefonu sağlam biçimde sabitler."],
                [("Evrensel Tutuş", "Farklı boyutlardaki telefonlara uyum sağlar."), ("Standart Vida", "1/4\" bağlantı ile tripod ve ayaklara takılır."), ("Yatay/Dikey", "Telefon iki yönde de kullanılabilir.")],
                ["Canlı yayın ve vlog", "Telefonla ürün çekimi", "Görüntülü görüşme ve ders kaydı"]),
    "vida": (["Farklı vida ölçülerine sahip ekipmanları birbirine bağlamak için kullanılan dönüştürücü vida adaptörüdür.",
              "Küçük ama stüdyoda sık ihtiyaç duyulan bu parça; kamera, ışık, top kafa ve ayak arasında uyumsuzluk sorununu çözer."],
             [("Dönüştürücü", "1/4\" ve 3/8\" gibi yaygın ölçüler arasında bağlantı sağlar."), ("Metal Yapı", "Dayanıklı ve uzun ömürlüdür."), ("Kompakt", "Çantada az yer kaplar.")],
             ["Tripod ve ışık ayağı bağlantıları", "Top kafa ve monitör montajı", "Rig ve aksesuar kurulumları"]),
    "boom": (["Işığı veya mikrofonu konunun üzerine ya da ayağın ulaşamadığı noktalara uzatmak için kullanılan boom (deve boynu) sistemidir.",
              "Uzun kolu ve dengeleme yapısıyla tepe ışığı, saç ışığı ve üstten aydınlatma gibi kurulumları güvenle yapmanızı sağlar."],
             [("Uzayan Kol", "Işığı konunun üzerine uzatarak tepe ışığı kurulumuna imkân verir."), ("Dengeleme", "Karşı ağırlık ile ekipman güvenle taşınır."), ("Sağlam Gövde", "Profesyonel stüdyo kullanımına uygun yapıdadır.")],
             ["Tepe ve saç ışığı kurulumu", "Mikrofon boom kullanımı", "Üstten ürün çekimleri"]),
    "teker": (["Işık ayağı veya tripodu stüdyo içinde kaldırmadan, rahatça hareket ettirmek için kullanılan tekerlekli taban setidir.",
               "Kilitlenebilir tekerlekleri sayesinde istenen noktada sabit durur; sessiz yapısı çekim sırasında ses kaydını etkilemez."],
              [("Kolay Taşıma", "Ekipman sökülmeden stüdyo içinde yer değiştirir."), ("Fren/Kilit", "Tekerlekler kilitlenerek ayak sabitlenir."), ("Sessiz Tekerlek", "Kauçuk yapı ile zemine zarar vermeden ve sessiz hareket eder.")],
              ["Stüdyo içi ışık konumlandırma", "Tripod ile kayan kamera hareketleri", "Sık değişen çekim kurulumları"]),
    "kumtorba": (["Işık ayakları, boom kollar ve C-stand gibi ekipmanların devrilmesini önlemek için tabana konulan dengeleme ağırlığıdır.",
                  "Özellikle uzun kollu kurulumlarda ve dış mekanda rüzgarlı havalarda ekipmanın güvenliğini artırır."],
                 [("Denge", "Ayak tabanına ağırlık ekleyerek devrilme riskini azaltır."), ("Dayanıklı Kumaş", "Sık kullanıma uygun sağlam dikişli yapıdadır."), ("Kolay Yerleşim", "Çift kanatlı yapısıyla ayak bacaklarına kolayca oturur.")],
                 ["Boom stand dengeleme", "Dış mekan ışık kurulumları", "Yüksek ve ağır ışık setleri"]),
    "canta": (["Işık ayakları, tripodlar ve uzun stüdyo ekipmanlarını taşımak ve saklamak için kullanılan bölmeli taşıma çantasıdır.",
               "Ekipmanları darbelere ve toza karşı korur; saha çekimlerine düzenli ve pratik şekilde gitmenizi sağlar."],
              [("Bölmeli İç Yapı", "Birden fazla ayak ve aksesuar ayrı bölmelerde taşınır."), ("Koruma", "Ekipmanı çizilme ve tozdan korur."), ("Kolay Taşıma", "Taşıma sapı ile rahatça taşınır.")],
              ["Saha çekimleri", "Ekipman saklama", "Stüdyolar arası taşıma"]),
    "tprofil": (["Kumaş veya kağıt fonları tek bir ışık ayağı üzerinde taşımak için kullanılan T profil fon barıdır.",
                 "Küçük alanlarda, vesikalık ve ürün çekimlerinde hızlıca fon kurmak isteyenler için pratik bir çözümdür."],
                [("Tek Ayakla Kurulum", "Standart ışık ayağına takılarak fon taşır."), ("Taşınabilir", "Hafif yapısıyla kolayca taşınır ve sökülür."), ("Hızlı Kurulum", "Fon birkaç dakikada çekime hazır hale gelir.")],
                ["Vesikalık çekimleri", "Küçük ürün çekimleri", "Video ve canlı yayın arka planı"]),
    "fonstand": (["Kumaş ve kağıt fonları asmak için kullanılan taşınabilir fon perde standıdır.",
                  "İki ayak ve üst bardan oluşan yapısıyla fonu stüdyoda veya dış mekanda dakikalar içinde kurmanızı sağlar."],
                 [("Taşınabilir Yapı", "Sökülüp taşınarak farklı mekanlarda kurulabilir."), ("Ayarlanabilir", "Yükseklik ve genişlik çekime göre ayarlanır."), ("Hafif Gövde", "Kolayca taşınır ve saklanır.")],
                 ["Portre ve vesikalık stüdyoları", "Etkinlik ve okul çekimleri", "Video ve yayın arka planı"]),
    "montaj": (["Stüdyo ekipmanlarını veya fonları duvar ve tavana sabit olarak monte etmek için kullanılan montaj aparatıdır.",
                "Zemini boş bırakır, kalıcı stüdyo kurulumlarında düzenli ve güvenli bir çalışma alanı oluşturur."],
               [("Sabit Montaj", "Duvar veya tavana sabitlenerek kalıcı kurulum sağlar."), ("Alan Kazancı", "Zeminde ayak kalabalığını azaltır."), ("Sağlam Yapı", "Uzun süreli kullanım için dayanıklıdır.")],
               ["Kalıcı stüdyo kurulumları", "Fon askı sistemleri", "Tavan ve duvardan ışık montajı"]),
    "mekanizma": (["Fon perdeyi rulo halinde sarıp istenen uzunlukta indirip kaldırmak için kullanılan boru, zincir ve makara mekanizma setidir.",
                   "Fonu her çekimde elle açıp kapatma zahmetini ortadan kaldırır; fonun düzgün ve kırışıksız kalmasına yardımcı olur."],
                  [("Zincir Kontrol", "Zincir çekilerek fon kolayca indirilir ve sarılır."), ("Rulo Sistemi", "Fon boru üzerinde düzenli sarılarak saklanır."), ("Kolay Montaj", "Duvar, tavan veya fon standına kurulabilir.")],
                  ["Vesikalık ve portre stüdyoları", "Video ve yayın stüdyoları", "Çok renkli fon kullanan stüdyolar"]),
    "reftutucu": (["Reflektörü ışık ayağına takarak istenen açı ve yükseklikte sabit tutmak için kullanılan teleskopik tutucu koldur.",
                   "Çekimde reflektörü tutacak bir asistana ihtiyaç duymadan ışığı doldurmanızı sağlar."],
                  [("Teleskopik Kol", "Uzunluğu reflektör boyutuna göre ayarlanır."), ("Açı Ayarı", "Reflektör istenen açıda sabitlenir."), ("Ayak Uyumlu", "Standart ışık ayaklarına takılır.")],
                  ["Portre çekimleri", "Ürün çekimlerinde gölge doldurma", "Tek kişilik stüdyo çekimleri"]),
    "isikayak": (["Stüdyo ışıklarını, softboxları ve aksesuarları güvenle taşımak için kullanılan ışık ayağıdır.",
                  "Kademeli uzayan gövdesi ile ışığı istenen yüksekliğe konumlandırır; katlandığında küçük yer kaplar."],
                 [("Ayarlanabilir Yükseklik", "Kademeli olarak uzayıp kısalır."), ("Dengeli Taban", "Geniş açılan bacaklar ekipmanı sağlam taşır."), ("Standart Bağlantı", "Işık ve aksesuarlarla uyumlu bağlantı başlığına sahiptir.")],
                 ["Softbox ve LED ışık kurulumu", "Reflektör ve fon taşıma", "Saha ve stüdyo çekimleri"]),
    "batarya": (["Kamera, ışık ve monitör gibi ekipmanlara prizden bağımsız güç sağlamak için kullanılan taşınabilir güç çözümüdür.",
                 "Saha çekimlerinde ve elektrik erişimi olmayan mekanlarda ekipmanlarınızı daha uzun süre çalıştırmanıza yardımcı olur."],
                [("Taşınabilir Güç", "Prize bağlı kalmadan ekipman çalıştırır."), ("Çoklu Çıkış", "Farklı cihazlara güç verebilecek çıkışlara sahiptir."), ("Saha Kullanımı", "Dış mekan ve hareketli çekimler için uygundur.")],
                ["Saha ve dış mekan çekimleri", "LED ışık ve monitör besleme", "Uzun süreli kayıtlar"]),
    "klaket": (["Film ve video setlerinde sahne, plan ve çekim numarasını kayda geçirmek, görüntü ile sesi senkronlamak için kullanılan klakettir.",
                "Montaj aşamasında çekimlerin kolayca bulunmasını ve ses-görüntü eşlemesinin hızla yapılmasını sağlar."],
               [("Senkronizasyon", "Klaket sesi ile görüntü ve ses kolayca eşleştirilir."), ("Not Alanı", "Sahne ve plan bilgileri üzerine yazılabilir."), ("Kurgu Kolaylığı", "Çekimlerin kurguda düzenli takibini sağlar.")],
               ["Film ve kısa film setleri", "Reklam ve klip çekimleri", "Okul ve atölye prodüksiyonları"]),
    "filtre": (["Işık kaynaklarının önüne yerleştirilerek ışığa renk katan veya rengini düzelten jelatin filtre setidir.",
                "Arka plan renklendirme, sinematik atmosfer oluşturma ve farklı ışık kaynaklarının rengini eşitleme için kullanılır."],
               [("Çoklu Renk", "Farklı renklerle yaratıcı ışık efektleri oluşturulur."), ("Geniş Yüzey", "Kesilerek farklı ışık boyutlarına uyarlanabilir."), ("Kolay Kullanım", "Işığın önüne tutturularak hemen kullanılır.")],
               ["Arka plan renklendirme", "Sinematik video çekimleri", "Sahne ve etkinlik aydınlatması"]),
    "minitripod": (["Telefon, kompakt kamera veya küçük LED ışıkları masa üzerinde sabitlemek için kullanılan kompakt bir masaüstü tripodudur.",
                    "Küçük boyutu sayesinde çantada kolayca taşınır; vlog, canlı yayın ve masaüstü ürün çekimlerinde pratik bir destek sunar."],
                   [("Kompakt Boyut", "Çantada az yer kaplar."), ("Stabil Duruş", "Geniş açılan ayakları ile masa üzerinde sabit durur."), ("Çok Amaçlı", "Telefon, kamera ve küçük ışıklarla kullanılır.")],
                   ["Masaüstü vlog ve canlı yayın", "Görüntülü görüşme", "Küçük ürün çekimleri"]),
    "tripod": (["Fotoğraf makinesi, video kamera veya telefonu sabit tutarak titreşimsiz ve net çekimler yapmanızı sağlayan tripoddur.",
                "Ayarlanabilir bacakları ve başlığı ile farklı yükseklik ve açılarda kurulum yapılabilir; katlandığında kolayca taşınır."],
               [("Ayarlanabilir Yükseklik", "Bacaklar ve orta kolon ile yükseklik çekime göre ayarlanır."), ("Başlık", "Kamera istenen açıya çevrilip sabitlenir."), ("Taşınabilir", "Katlanarak kolayca taşınır.")],
               ["Fotoğraf ve video çekimleri", "Ürün ve üstten (flat-lay) çekimler", "Seyahat ve dış mekan çekimleri"]),
    "temizlik": None, "duy": None,
}
TANIM = {
    "cob": ["Bowens yuvalı COB LED sürekli ışık", "stüdyo ve video çekimleri için COB LED sürekli ışık", "güçlü COB LED video ve fotoğraf ışığı"],
    "panel": ["LED panel video ve fotoğraf ışığı", "geniş yüzeyli LED panel ışık", "yumuşak ve homojen ışık veren LED panel"],
    "tup": ["RGB LED tüp ışık", "renkli efekt ve dolgu ışığı olarak kullanılan LED çubuk ışık"],
    "mobil": ["kompakt ve taşınabilir LED ışık", "mobil çekimler için hafif LED ışık"],
    "flas": ["stüdyo flaş çözümü", "fotoğraf stüdyoları için flaş ekipmanı"],
    "sekil": ["ışık şekillendirici", "ışığın yönünü ve karakterini belirleyen stüdyo aksesuarı"],
    "reflektor": ["çok yüzeyli reflektör seti", "katlanabilir ışık yansıtıcı ve yumuşatıcı set"],
    "kagit": ["kağıt sonsuz stüdyo fonu", "dikişsiz kağıt stüdyo arka planı"],
    "kumas": ["kumaş stüdyo fonu", "kumaş sonsuz fon sistemi"],
    "pvc": ["PVC stüdyo fonu", "silinebilir PVC arka plan"],
    "masa": ["ürün çekim masası"], "cadir": ["ürün çekim çadırı"], "tabla": ["döner ürün çekim tablası"],
    "tripod": ["kamera ve ekipman tripodu", "fotoğraf ve video tripodu"],
    "stand": ["stüdyo ışık ayağı ve taşıma ekipmanı", "stüdyo standı"],
    "aksesuar": ["stüdyo ve çekim aksesuarı", "prodüksiyon aksesuarı"],
}

KULLANIM = {
    "cob": ["YouTube ve sosyal medya video çekimleri", "Röportaj ve kurumsal video prodüksiyonu", "Portre, moda ve ürün fotoğrafçılığı", "Canlı yayın ve podcast stüdyoları"],
    "panel": ["Canlı yayın, YouTube ve podcast kurulumları", "Röportaj ve kurumsal videolar", "Ürün ve e-ticaret fotoğrafçılığı", "Makyaj, güzellik ve portre çekimleri"],
    "tup": ["Arka plan renk efektleri", "Müzik klibi ve sinematik çekimler", "Oyun ve yayın odası aydınlatması", "Ürün çekimlerinde kenar ve vurgu ışığı"],
    "mobil": ["Vlog ve telefonla video çekimi", "Görüntülü görüşme ve canlı yayın", "Kamera üstü dolgu ışığı", "Yakın plan ürün ve yemek çekimleri"],
    "flas": ["Ürün ve katalog çekimleri", "Portre ve vesikalık stüdyoları", "Moda ve reklam fotoğrafçılığı", "E-ticaret stüdyo kurulumları"],
    "sekil": ["Portre ve moda çekimlerinde ışık kontrolü", "Ürün fotoğrafçılığında yumuşak veya noktasal ışık", "Video prodüksiyonlarında ışık yönlendirme", "Stüdyo flaşları ve COB LED ışıklarla kullanım"],
    "reflektor": ["Dış mekan portre çekimleri", "Ürün fotoğrafçılığında gölge doldurma", "Video çekimlerinde doğal dolgu ışığı", "Düğün ve etkinlik fotoğrafçılığı"],
    "kagit": ["Portre ve moda stüdyoları", "Ürün ve katalog çekimleri", "Vesikalık ve kurumsal fotoğraf", "Video ve sosyal medya içerikleri"],
    "kumas": ["Vesikalık ve portre çekimleri", "Video, röportaj ve canlı yayın arka planı", "Ürün çekimleri", "Okul, etkinlik ve kurumsal fotoğraf"],
    "pvc": ["Ürün ve e-ticaret çekimleri", "Yemek ve kozmetik fotoğrafçılığı", "Portre ve vesikalık çekimleri", "Sosyal medya içerik üretimi"],
    "masa": ["E-ticaret ürün fotoğrafçılığı", "Takı, kozmetik ve küçük ürün çekimleri", "Katalog çekimleri"],
    "cadir": ["E-ticaret ürün fotoğrafçılığı", "Takı, saat ve kozmetik çekimleri", "Küçük ürünlerde gölgesiz çekim"],
    "tabla": ["360 derece ürün videoları", "E-ticaret ürün çekimleri", "Sosyal medya ürün tanıtımları"],
    "tripod": ["Fotoğraf ve video çekimleri", "Vlog ve canlı yayın", "Ürün ve üstten (flat-lay) çekimler", "Seyahat ve dış mekan çekimleri"],
    "stand": ["Stüdyo ışıklarının konumlandırılması", "Softbox ve şekillendirici kullanımı", "Video ve fotoğraf prodüksiyonları"],
    "aksesuar": ["Fotoğraf ve video stüdyoları", "Saha ve set çalışmaları", "Ekipman kurulumu ve sabitleme"],
}


def ozgun_metin(sku, ad, kat, a, kutu):
    """Giriş paragrafları ve özellik maddeleri — Foto Ekspres'in kendi cümleleriyle."""
    model = a["model"] if a["model"] and re.search(r"[A-Za-z]", a["model"]) else ""
    tanim = _sec(sku, TANIM[kat], "t")
    giris, oz = [], []
    set_ifade = {1: "", 2: "iki ışıklı set halinde ", 3: "üç ışıklı set halinde "}[a["adet"]] if kat in ("cob", "panel", "tup", "flas") else ""
    alt = alt_tur(ad)
    if kat == "aksesuar" and AKS.get(alt):
        g_, oz_, _k = AKS[alt]
        model = a["model"] if a["model"] and re.search(r"[A-Za-z]", a["model"]) else ""
        bas = f"GDX {model}, " if model else "Bu ürün, "
        giris = [bas + g_[0][0].lower() + g_[0][1:], g_[1]]
        oz = list(oz_)
        if a["kapasite"] and alt in ("tripod", "boom", "isikayak", "teker", "topkafa"):
            oz.append(("Taşıma Kapasitesi", f"{a['kapasite']} taşıma kapasitesine sahiptir."))
        if a["yukseklik"] and alt in ("tripod", "boom", "isikayak"):
            oz.append(("Maksimum Yükseklik", f"{a['yukseklik']} yüksekliğe kadar uzar."))
        if a["malzeme"]:
            oz.append(("Malzeme", f"{a['malzeme']}."))
        return giris, oz[:6]
    kisa = {"kagit": "kağıt fon", "kumas": "kumaş fon", "pvc": "PVC fon", "reflektor": "reflektör seti", "tripod": "tripod",
            "stand": "stüdyo ekipmanı", "masa": "ürün çekim masası", "cadir": "ürün çekim çadırı", "tabla": "döner tabla",
            "aksesuar": "aksesuar", "flas": "flaş seti", "mobil": "LED ışık", "tup": "LED tüp ışık", "panel": "LED panel", "cob": "COB LED ışık"}.get(kat, "ürün")
    if kat == "sekil":
        kisa = next((n for d, n in [(r"softbox", "softbox"), (r"snoot", "snoot"), (r"fresnel", "fresnel lens"), (r"jelatin|filtre", "filtre seti"),
                                     (r"grid|petek", "grid"), (r"reflektör tas|tas", "reflektör tas")] if re.search(d, ad, re.I)), "ışık şekillendirici")
    if kat == "sekil":
        tanim = kisa
    ozne = f"GDX {model}" if model else f"Bu GDX {kisa}"
    if model:
        acilis = _sec(sku, [
            (f"{ozne}, {set_ifade}sunulan bir {tanim} modelidir." if set_ifade else f"{ozne}, stüdyo ve saha çekimleri için geliştirilmiş bir {tanim} modelidir."),
            f"{ozne}; {set_ifade}profesyonel çekimler için geliştirilmiş bir {tanim} modelidir.",
            f"{ozne}, {set_ifade}fotoğraf ve video üretiminde kullanılmak üzere tasarlanmış bir {tanim} modelidir.",
        ], "a")
    else:
        acilis = _sec(sku, [
            f"{ozne}, stüdyo ve saha çekimlerinde düzenli ve profesyonel bir sonuç almak isteyenler için hazırlanmıştır.",
            f"{ozne}, fotoğraf ve video çekimlerinde pratik ve güvenilir bir kullanım sunmak üzere tasarlanmıştır.",
        ], "a")
    giris.append(acilis)

    if kat in ("cob", "panel", "tup", "mobil"):
        p = []
        if a["guc"]:
            p.append(f"{a['guc']} güç değeri")
        if a["cct"]:
            p.append(f"{a['cct']} aralığında ayarlanabilen renk sıcaklığı")
        if a["rgb"]:
            p.append("tam renk RGB modu")
        if a["cri"]:
            p.append(f"{a['cri']} renk doğruluğu")
        if p:
            giris.append(_sec(sku, [
                "Ürün; " + ", ".join(p) + " ile çekim ortamına göre hassas biçimde ayarlanabilen bir ışık sunar.",
                "Sahip olduğu " + ", ".join(p) + " sayesinde ten tonlarını ve ürün renklerini doğal gösterir, farklı sahnelere hızlıca uyum sağlar.",
            ], "p"))
        giris.append(_sec(sku, [
            "Gün ışığı ile karışık ortamlarda, stüdyo içinde ya da sahada aynı kalitede ışık elde etmek isteyen içerik üreticileri ve prodüksiyon ekipleri için güvenilir bir seçenektir.",
            "Kurulumu hızlı, kontrolleri anlaşılırdır; ister ana ışık ister dolgu ya da arka plan ışığı olarak kullanılsın, çekimde tutarlı bir sonuç verir.",
            "Yayın odasından ürün çekimine kadar farklı senaryolarda, ışığı ihtiyaca göre şekillendirmek isteyenler için dengeli bir fiyat-performans sunar.",
        ], "k"))
    elif kat in ("kagit", "kumas", "pvc"):
        malz = {"kagit": "kağıt", "kumas": "kumaş", "pvc": "PVC"}[kat]
        p = f"{a['renk'].capitalize()} renkli" if a["renk"] else "Mat yüzeyli"
        giris.append(_sec(sku, [
            f"{p} {malz} yüzeyi{(' ve ' + a['olcu'] + ' ölçüsü') if a['olcu'] else ''} ile konunun arkasında temiz ve dikkat dağıtmayan bir zemin oluşturur.",
            (f"{a['olcu']} ölçüsündeki {malz} yüzeyi" if a["olcu"] else f"{malz.capitalize()} yüzeyi") + f", {a['renk'] or 'nötr'} tonuyla çekimlerde arka planın sade ve tutarlı görünmesini sağlar.",
        ], "f"))
        if kat == "kagit":
            giris.append("Kağıt fonlar ışığı yansıtmayan mat yapıları sayesinde stüdyo flaşları ve sürekli ışıklarla parlama yapmadan çalışır; kirlenen bölüm kesilerek rulo kolayca yenilenir.")
        elif kat == "kumas":
            giris.append("Kumaş yapısı katlanarak taşınabilir, yıkanabilir ve uzun süre kullanılabilir; kırışıklıklar buhar veya ütüyle kolayca giderilir.")
        else:
            giris.append("PVC yüzey su ve lekeye karşı dayanıklıdır; nemli bir bezle silinerek temizlenir, kırışmadığı için her çekimde düzgün görünür.")
        if a["sabit"] or a["seyyar"] or a["mekanizma"]:
            giris.append(_sec(sku, [
                ("Set, " + ("duvar veya tavana sabitlenen" if a["sabit"] else "taşınabilir ayaklı") + (" ve zincir mekanizmalı" if a["mekanizma"] else "") + " yapısıyla fonu istediğiniz uzunlukta indirip kaldırmanıza imkân verir."),
                ("Fon sistemi " + ("sabit montajlı" if a["sabit"] else "seyyar") + (", makara-zincir mekanizmalı" if a["mekanizma"] else "") + " yapıdadır; stüdyo kurulumu ve toplanması pratikçe yapılır."),
            ], "m"))
    elif kat == "reflektor":
        giris.append(_sec(sku, [
            f"{(a['olcu'] or a['boy'] or '').strip()} {'boyutundaki ' if (a['olcu'] or a['boy']) else ''}reflektör; gümüş, altın, beyaz, siyah ve difüzör yüzeyleriyle ışığı yansıtmak, yumuşatmak veya kesmek için tek bir set içinde beş farklı seçenek sunar.".strip(),
            "Gümüş yüzey güçlü ve parlak, altın yüzey sıcak tonlu, beyaz yüzey yumuşak bir yansıma verir; siyah yüzey ışığı keser, difüzör ise sert güneşi yumuşatır.",
        ], "r"))
        giris.append("Katlanabilir yapısı sayesinde küçük bir çantaya sığar; dış çekimlerde ve stüdyoda gölgeleri doldurmanın en pratik yollarından biridir.")
    elif kat == "flas":
        giris.append("Set; ışık kaynakları, şekillendiriciler ve gerekli bağlantı ekipmanlarıyla stüdyo kurulumunu tek pakette tamamlamak isteyenler için hazırlanmıştır.")
        giris.append("Ürün, katalog ve portre çekimlerinde ışığı kontrollü ve tekrarlanabilir biçimde kullanmanızı sağlar; yeni kurulan stüdyolar için iyi bir başlangıç noktasıdır.")
    elif kat == "sekil":
        giris.append(_sec(sku, [
            "Işık kaynağının önüne takılarak ışığı yumuşatır, yönlendirir veya dar bir alana toplar; böylece aynı ışıkla çok farklı görünümler elde edilir.",
            "Doğru şekillendirici, sert ve yayılan ışığı kontrollü bir aydınlatmaya dönüştürür; portre, ürün ve video çekimlerinde sonucu doğrudan etkiler.",
        ], "s") + (" Bowens bağlantısı sayesinde Bowens yuvalı flaş ve LED ışıklarla kullanılır." if a["bowens"] else ""))
    elif kat in ("masa", "cadir", "tabla"):
        giris.append("Ürün çekimlerinde arka planı ve ışığı kontrol altına alarak, e-ticaret sitelerine uygun temiz ve tutarlı görseller hazırlamanıza yardımcı olur.")
        giris.append("Kurulumu ve kullanımı kolaydır; profesyonel stüdyo olmadan da düzenli ve kaliteli ürün fotoğrafları çekmeyi mümkün kılar.")
    elif kat in ("tripod", "stand"):
        p = []
        if a["yukseklik"]:
            p.append(f"{a['yukseklik']} çalışma yüksekliği")
        if a["kapasite"]:
            p.append(f"{a['kapasite']} taşıma kapasitesi")
        giris.append(("Ürün; " + " ve ".join(p) + " ile ekipmanınızı güvenle taşır." if p else
                      "Ekipmanınızı istediğiniz yükseklik ve açıda sabit tutarak çekim sırasında güvenli ve dengeli bir kurulum sağlar."))
        giris.append("Sağlam bağlantı noktaları ve ayarlanabilir yapısıyla stüdyoda ve sahada sık sık kurulup toplanan ekipmanlar için uygundur.")
    else:
        giris.append("Çekim sırasında ekipmanlarınızı düzenli, güvenli ve kullanışlı tutmak için tasarlanmış pratik bir yardımcı aksesuardır.")
        giris.append("Stüdyo ve saha kurulumlarında zaman kazandırır; mevcut ekipmanlarınızla birlikte kolayca kullanılır.")

    # Öne çıkan özellikler (kendi ifadelerimizle, ürün bilgisinden)
    if a["guc"] and kat in ("cob", "panel", "tup", "mobil", "flas"):
        oz.append(("Güç", f"{a['guc']} değeriyle sahnenin büyüklüğüne uygun ışık miktarı sağlar."))
    if a["cct"]:
        oz.append(("Renk Sıcaklığı", f"{a['cct']} arasında ayarlanarak sıcak ve soğuk ışık ortamlarına uyum sağlar."))
    if a["rgb"] and kat in ("cob", "panel", "tup", "mobil"):
        oz.append(("RGB Renk", "Tam renk modu ile arka plan ve efekt aydınlatmasında yaratıcı renkler kullanılabilir."))
    if a["cri"]:
        oz.append(("Renk Doğruluğu", f"{a['cri']} değeriyle ten tonları ve ürün renkleri doğal görünür."))
    if a["efekt"]:
        oz.append(("Hazır Efektler", f"{a['efekt']} hazır ışık efekti ile şimşek, polis, parti gibi sahneler kolayca oluşturulur."))
    if a["kontrol"] and kat in ("cob", "panel", "tup", "mobil", "flas"):
        k_ = " ve ".join(a["kontrol"])
        oz.append(("Kontrol", k_[:1].upper() + k_[1:] + " desteği ile ışık ayarları uzaktan yapılabilir."))
    if a["bowens"] and kat in ("cob", "flas"):
        oz.append(("Bowens Bağlantı", "Softbox, reflektör ve snoot gibi Bowens uyumlu şekillendiricilerle doğrudan kullanılır."))
    elif a["bowens"] and kat == "sekil":
        oz.append(("Bowens Bağlantı", "Bowens yuvalı paraflaş ve COB LED ışıklara doğrudan takılır."))
    if a["batarya"] and kat in ("cob", "panel", "tup", "mobil") and re.search(r"(?i)batarya|np-?f|v-?mount|mah|pil|şarj", a["batarya"]):
        oz.append(("Güç Seçeneği", f"{a['batarya']} — uygun batarya ile prize bağlı kalmadan da kullanılabilir."))
    if a["softbox"] and kat == "sekil":
        oz.append(("Ölçü", f"{a['softbox']} ışık yüzeyi ile geniş ve yumuşak bir aydınlatma oluşturur."))
    elif a["softbox"]:
        oz.append(("Softbox", f"Sete dahil {a['softbox']} softbox ışığı genişletip yumuşatarak gölgeleri azaltır."))
    if a["ayak"]:
        oz.append(("Işık Ayağı", f"{a['ayak']} ışık ayağı ile ışık istenen yüksekliğe kolayca konumlandırılır."))
    if a["adet"] > 1 and kat in ("cob", "panel", "tup", "flas"):
        oz.append(("Set Avantajı", f"{a['adet']} ışıkla ana ışık, dolgu ve arka plan aydınlatması aynı anda kurulabilir."))
    if kat in ("kagit", "kumas", "pvc"):
        if a["olcu"]:
            oz.append(("Ölçü", f"{a['olcu']} ölçüsü ile {'tam boy portre ve grup çekimleri' if re.search(r'2[.,]7|3x|5[.,]8|11', a['olcu']) else 'portre, vesikalık ve ürün çekimleri'} için yeterli alan sağlar."))
        if a["renk"]:
            oz.append(("Renk", f"{a['renk'].capitalize()} tonu çekim boyunca tutarlı bir arka plan rengi verir."))
        if a["gramaj"] and kat == "kagit":
            oz.append(("Kağıt Kalitesi", f"{a['gramaj']} yoğunluk ile ışık geçirmeyen, dalgalanmayan bir yüzey sunar."))
        oz.append(("Mat Yüzey", "Işığı yansıtmayan yapısı sayesinde fotoğraflarda parlama ve sıcak nokta oluşmaz."))
        if a["mekanizma"]:
            oz.append(("Mekanizma", "Makara ve zincir sistemi ile fon istenen uzunlukta indirilip sarılabilir."))
    if kat == "reflektor":
        oz += [("5 Yüzey", "Gümüş, altın, beyaz, siyah ve difüzör yüzeyleri tek sette."), ("Katlanabilir", "Küçük boyuta katlanarak taşıma çantasında saklanır."),
               ("Hafif Yapı", "Elde tutularak veya tutucu ile ayağa takılarak kullanılabilir.")]
    T = ad.replace("İ", "i").replace("I", "ı").lower()
    if kat == "sekil":
        for d, b_, t_ in [(r"grid|ızgara|petek", "Grid", "Petek ızgara ile ışık daha kontrollü yönlendirilir, etrafa yayılması azalır."),
                          (r"çift difüzör", "Çift Difüzör", "İki kat difüzör ışığı daha homojen ve yumuşak hale getirir."),
                          (r"parabolik", "Parabolik Form", "Derin parabolik yapı ışığı daha yoğun ve odaklı yansıtır."),
                          (r"octagon|okta", "Octagon Form", "Sekizgen yapı gözlerde doğal ve yuvarlak ışık yansıması oluşturur."),
                          (r"one tick|hızlı kurulum", "Hızlı Kurulum", "Şemsiye mekanizmasıyla saniyeler içinde açılıp kapanır."),
                          (r"balon|lantern|360 derece", "360° Yayılım", "Işığı her yöne yayarak ortamı yumuşak biçimde aydınlatır."),
                          (r"fresnel", "Fresnel Lens", "Işık huzmesi daraltılıp genişletilerek sert veya yumuşak ışık elde edilir."),
                          (r"gobo", "Gobo Projeksiyonu", "Desen şablonlarıyla arka plana şekil ve gölge efektleri yansıtılır."),
                          (r"duylu", "Duylu Yapı", "Softbox içindeki duylara uygun ampuller takılarak sürekli ışık elde edilir."),
                          (r"lambasız", "Lambasız Set", "Ampuller sete dahil değildir, ayrıca temin edilmelidir.")]:
            if re.search(d, T):
                oz.append((b_, t_))
        m = re.search(r"(\d{2,3})\s?°", ad)
        if m:
            oz.append(("Işık Açısı", f"{m.group(1)}° huzme açısı ile ışık dar bir alana odaklanır."))
        m = re.search(r"(\d{1,3})\s?gobo", T)
        if m:
            oz.append(("Gobo Sayısı", f"Sette {m.group(1)} farklı gobo şablonu bulunur."))
    if kat == "cadir":
        if a["olcu"]:
            oz.append(("Ölçü", f"{a['olcu']} iç hacim ile {'büyük boy ürünler' if re.search(r'8\d|1[0-9]\d', a['olcu']) else 'takı, kozmetik ve küçük ürünler'} için uygundur."))
        if re.search(r"4 renk", T):
            oz.append(("4 Renk Fon", "Farklı renkte fonlarla ürüne uygun arka plan seçilir."))
        if re.search(r"led|ışıklı", T):
            oz.append(("Dahili LED", "Çadıra entegre LED ışıklar ek ışık kaynağına gerek bırakmaz."))
        oz.append(("Yumuşak Işık", "Difüzör yüzeyler ışığı dağıtarak gölgesiz ürün görüntüsü sağlar."))
        if re.search(r"çanta|katlan|taşınabilir", T):
            oz.append(("Taşınabilir", "Katlanarak çantasında taşınır ve saklanır."))
    if kat == "tabla":
        m = re.search(r"çap (\d{2,3}) ?cm", T)
        if m:
            oz.append(("Çap", f"{m.group(1)} cm tabla yüzeyi ürünü rahatça taşır."))
        oz.append(("360° Dönüş", "Ürünü her açıdan göstermek için sürekli ve dengeli döner."))
        if re.search(r"kumanda", T):
            oz.append(("Uzaktan Kumanda", "Dönüş hızı ve yönü kumanda ile kontrol edilir."))
        if re.search(r"ayna", T):
            oz.append(("Ayna Yüzey", "Aynalı yüzey ürünün yansımasıyla şık görüntüler oluşturur."))
    if kat == "masa":
        if re.search(r"çift taraflı", T):
            oz.append(("Çift Taraflı Panel", "Mat ve parlak yüzey seçeneğiyle farklı ürün görünümleri elde edilir."))
        if re.search(r"eğim|ayarlanabilir", T):
            oz.append(("Ayarlanabilir Eğim", "Panel eğimi ürüne ve çekim açısına göre ayarlanır."))
        if a["olcu"]:
            oz.append(("Ölçü", f"{a['olcu']} çalışma yüzeyi sunar."))
        oz.append(("Sonsuz Fon Etkisi", "Kavisli yüzey sayesinde ürünün arkasında köşe çizgisi oluşmaz."))
    if a["malzeme"] and len(oz) < 7:
        oz.append(("Malzeme", f"{a['malzeme']} yapısı ile uzun ömürlü kullanım sunar."))
    if a["kapasite"] and kat in ("tripod", "stand", "tabla") and len(oz) < 7:
        oz.append(("Taşıma Kapasitesi", f"{a['kapasite']} kapasite ile ekipmanı güvenle taşır."))
    if a["yukseklik"] and kat in ("tripod", "stand") and len(oz) < 7:
        oz.append(("Yükseklik", f"{a['yukseklik']} yüksekliğe kadar ayarlanabilir."))
    if len(oz) < 3:
        oz += [("Pratik Kullanım", "Hızlı kurulum ve sökme imkânı ile çekime ayrılan zamanı artırır."),
               ("Sağlam Yapı", "Sık kullanıma dayanıklı malzemelerle üretilmiştir."),
               ("Uyumlu Kullanım", "Stüdyodaki mevcut ışık ayakları, tripodlar ve aksesuarlarla birlikte kullanılabilir.")][: 4 - len(oz)]
    return giris, oz[:6]


def kutu_satir(b, t):
    b = re.sub(r"^\s*[-–•]\s*", "", b or "").strip()
    t = re.sub(r"^\s*[-–•]\s*", "", t or "").strip()
    if b and t:
        return (b + " " + t) if re.fullmatch(r"\d+\s?(x|adet)?", b, re.I) else (b + ": " + t)
    return b or t


def ozgun_sss(sku, kat, a, kutu):
    s = []
    if a["cct"]:
        s.append(("Renk sıcaklığı ayarlanabiliyor mu?", f"Evet, {a['cct']} aralığında ayarlanabilir."))
    if a["rgb"] and kat in ("cob", "panel", "tup", "mobil"):
        s.append(("Renkli ışık verebilir mi?", "Evet, RGB modu ile farklı renklerde ışık ve efekt üretebilir."))
    if a["bowens"] and kat in ("cob", "flas", "sekil"):
        s.append(("Softbox takılabilir mi?", "Evet, Bowens bağlantısı sayesinde Bowens uyumlu softbox ve şekillendiriciler takılabilir."))
    if a["batarya"] and kat in ("cob", "panel", "tup", "mobil"):
        s.append(("Güç seçenekleri nelerdir?", f"Üreticinin belirttiği güç bilgisi: {a['batarya']}."))
    if kat in ("kagit", "kumas", "pvc"):
        s.append(("Fon nasıl temizlenir?", {"kagit": "Kirlenen veya yıpranan bölüm kesilir, rulo aşağı indirilerek temiz bölüm kullanılır.",
                                             "kumas": "Hafif kirlerde silinebilir, gerektiğinde düşük ısıda yıkanıp ütülenebilir.",
                                             "pvc": "Nemli bir bezle silinerek kolayca temizlenir."}[kat]))
        if a["olcu"]:
            s.append(("Fonun ölçüsü nedir?", f"Ürünün ölçüsü {a['olcu']}."))
    if kat == "reflektor":
        s.append(("Hangi yüzey ne işe yarar?", "Gümüş ve altın ışığı yansıtır, beyaz yumuşak dolgu verir, siyah ışığı keser, difüzör ışığı yumuşatır."))
    if kutu and len(s) < 4:
        parcalar = [kutu_satir(b, t) for b, t in kutu if (b or t)][:6]
        s.append(("Pakette neler var?", ", ".join(p.rstrip(".") for p in parcalar) + "."))
    if not s:
        s.append(("Kurulumu kolay mı?", "Evet, ek alet gerektirmeden kısa sürede kurulup kullanılabilir."))
    return s[:3]


def ozgun_aciklama(urun, bolumler):
    ad = bosluk(urun["title"])
    sku = urun.get("_sku", ad)
    tip = urun.get("product_type") or ""
    ciftler, kutu, teknik_satir = [], [], []
    for b in bolumler:
        if b["tur"] == "teknik":
            satirlar, c = teknik_satirlar(b)
            ciftler += c
            teknik_satir += [s for s in satirlar if s[0] == "kv"]
        elif b["tur"] == "kutu":
            kutu += b["li"]
    kat = kategori(ad, tip)
    a = ozellikler_cikar(ad, ciftler, tip)
    giris, oz = ozgun_metin(sku, ad, kat, a, kutu)
    out = [f'<div style="{STYLE}">', f"<div><strong>{esc(ad)}</strong></div>", BOS]
    for p in giris:
        out.append(f"<div>{esc(p)}</div>")
    out.append(BOS)
    out.append("<div><strong>Öne Çıkan Özellikler</strong></div>")
    out += [f"<div><strong>{esc(b)}:</strong> {esc(t)}</div>" for b, t in oz] + [BOS]
    out.append("<div><strong>Kullanım Alanları</strong></div>")
    alt = alt_tur(ad)
    kul = AKS[alt][2] if kat == "aksesuar" and AKS.get(alt) else KULLANIM[kat][:3]
    out += [f"<div>{esc(x)}</div>" for x in kul] + [BOS]
    if kutu:
        out.append("<div><strong>Kutu İçeriği</strong></div>")
        for b, t in kutu[:5]:
            satir = kutu_satir(b, t)
            out.append(f"<div>{esc(satir)}</div>")
        out.append(BOS)
    tek = [s for s in teknik_satir if len(s[2]) <= 70 and not re.search(r"(?i)kullanım|uygulama alanı|profesyonel not|amacı|avantaj|saklama|çevresel|sertifika|marka|model", s[1])][:6]
    if len(tek) >= 2:
        out.append("<div><strong>Teknik Özellikler</strong></div>")
        out += [f"<div>{esc(s[1])}: {esc(s[2])}</div>" for s in tek] + [BOS]
    sss = ozgun_sss(sku, kat, a, kutu)
    out.append("<div><strong>Sık Sorulan Sorular</strong></div>")
    for i, (q, c) in enumerate(sss):
        out += [f"<div><strong>{esc(q)}</strong></div>", f"<div>{esc(c)}</div>"]
        if i < len(sss) - 1:
            out.append(BOS)
    out += [BOS, "<div><strong>Neden Foto Ekspres?</strong></div>"] + [f"<div>{x}</div>" for x in NEDEN] + ["</div>"]
    return "\n".join(out)


def aciklama(urun):
    ad = bosluk(urun["title"])
    if urun["handle"] in ELLE:
        return elle_aciklama(ad, ELLE[urun["handle"]])
    ek_not = ""
    if urun["handle"] in BASKA_KAYNAK:
        site, h, ek_not = BASKA_KAYNAK[urun["handle"]]
        alt = ham_bul(site, h or urun["handle"], urun["variants"][0].get("sku"))
        if alt is None:
            raise SystemExit(f"Açıklama kaynağı bulunamadı: {urun['handle']}")
        urun = dict(urun, body_html=alt.get("body_html") or "")
    bolumler = ayristir(urun)
    return ozgun_aciklama(urun, bolumler)


def aciklama_eski(urun, bolumler, ad):
    ek_not = ""
    out = [f'<div style="{STYLE}">', f"<div><strong>{esc(ad)}</strong></div>", BOS]
    sira = {"giris": 0, "ozellik": 1, "diger": 2, "kullanim": 3, "uyum": 4, "kutu": 5, "teknik": 6, "bakim": 7}
    varsayilan = {"ozellik": "Öne Çıkan Özellikler", "kullanim": "Kullanım Alanları", "uyum": "Uyumluluk",
                  "kutu": "Kutu İçeriği", "teknik": "Teknik Özellikler", "bakim": "Kullanım ve Bakım Önerileri"}
    ilk_oz = next((i for i, b in enumerate(bolumler) if b["tur"] == "ozellik"), len(bolumler))
    bolumler = [b for _, b in sorted(enumerate(bolumler), key=lambda ib: (
        0.5 if ib[1]["tur"] == "diger" and ib[0] < ilk_oz else sira[ib[1]["tur"]], ib[0]))]
    ciftler, kutu = [], []
    teknik_yazildi = False
    for bol in bolumler:
        if bol["tur"] == "teknik":
            satirlar, c = teknik_satirlar(bol)
            if not satirlar:
                continue
            ciftler += c
            if not teknik_yazildi:
                out += ["<div><strong>Teknik Özellikler</strong></div>"]
                teknik_yazildi = True
            elif bol["baslik"]:
                out.append(f"<div><strong>{esc(bol['baslik'])}</strong></div>")
            for s in satirlar:
                out.append(f"<div><strong>{esc(s[1])}</strong></div>" if s[0] == "b" else f"<div>{esc(s[1])}: {esc(s[2])}</div>")
            for p in bol["p"]:
                out.append(f"<div>{esc(p)}</div>")
            out.append(BOS)
            continue
        if bol["tur"] == "giris":
            for p in bol["p"]:
                out += [f"<div>{esc(p)}</div>", BOS]
            for b, t in bol["li"]:
                out.append(satir_li(b, t))
            if bol["li"]:
                out.append(BOS)
            continue
        baslik = varsayilan.get(bol["tur"]) if bol["tur"] != "diger" else bol["baslik"]
        if bol["tur"] in ("ozellik", "kullanim", "kutu", "uyum", "bakim"):
            baslik = varsayilan[bol["tur"]]
        if bol["tur"] == "kutu":
            kutu += bol["li"]
        out.append(f"<div><strong>{esc(baslik or bol['baslik'])}</strong></div>")
        for p in bol["p"]:
            out.append(f"<div>{esc(p)}</div>")
        for b, t in bol["li"]:
            out.append(satir_li(b, t))
        for h in bol["tr"]:
            out.append(f"<div>{esc(' – '.join(h))}</div>")
        out.append(BOS)
    sss = sss_uret(ciftler, kutu)
    if sss:
        out.append("<div><strong>Sık Sorulan Sorular</strong></div>")
        for i, (q, c) in enumerate(sss):
            out += [f"<div><strong>{esc(q)}</strong></div>", f"<div>{esc(c)}</div>"]
            if i < len(sss) - 1:
                out.append(BOS)
        out.append(BOS)
    out += ["<div><strong>Neden Foto Ekspres?</strong></div>"] + [f"<div>{x}</div>" for x in NEDEN]
    out.append("</div>")
    return "\n".join(out)


def cdata(s):
    return "<![CDATA[" + str(s).replace("]]>", "]]]]><![CDATA[>") + "]]>"


def urun_listesi(ham):
    urunler = [u for u in ham if (u.get("vendor") or "").upper() == "GDX" and float((u.get("variants") or [{}])[0].get("price") or 0) > 0]
    urunler.sort(key=lambda u: ((u.get("product_type") or "zzz").lower(), bosluk(u["title"]).lower()))
    return urunler


def uret(ham=None, yaz=True):
    if ham is None:
        ham = json.load(open(HAM, encoding="utf-8"))
    sonuc = []
    for i, u in enumerate(urun_listesi(ham)):
        v = u["variants"][0]
        kaynak = float(v["price"])
        u = dict(u, _sku=f"FE-GDX-{ILK_NO + i}")
        sonuc.append(dict(
            sku=f"FE-GDX-{ILK_NO + i}", name=bosluk(u["title"]), brand="GDX", barcode=(v.get("barcode") or "").strip(),
            price=str(int(kaynak * (1 + MARJ / 100) + 0.5)), kaynak_fiyat=kaynak, currency="TRY",
            stock=str(STOK_VAR if v.get("available") else 0),
            availability="https://schema.org/InStock" if v.get("available") else "https://schema.org/OutOfStock",
            category=GRUP, description=aciklama(u), status="passive",
            imgs=[re.sub(r"\?.*$", "", im["src"]) for im in (u.get("images") or [])][:8],
            url=f"https://gdx.com.tr/products/{u['handle']}", tip=u.get("product_type") or "", kod=v.get("sku") or ""))
    if yaz:
        satir = ['<?xml version="1.0" encoding="UTF-8"?>', '<products source_id="1" source_name="fotoekspres-sync">']
        for i, u in enumerate(sonuc, 1):
            satir.append(" <product>")
            for a in ALANLAR:
                val = str(i) if a == "id" else u.get(a, "")
                satir.append(f"  <{a}>{cdata(val)}</{a}>" if val != "" else f"  <{a}/>")
            for k, g in enumerate(u["imgs"], 1):
                satir.append(f"  <image{k}>{cdata(g)}</image{k}>")
            satir.append(" </product>")
        satir.append("</products>")
        os.makedirs(os.path.dirname(CIKTI), exist_ok=True)
        open(CIKTI, "w", encoding="utf-8").write("\n".join(satir) + "\n")
        with open(KAYNAK, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["sku", "url"])
            for u in sonuc:
                w.writerow([u["sku"], u["url"]])
    return sonuc


def calistir():
    """sync.py çağırır: data/yeni/gdx.xml yoksa ve ham veri varsa bir kez üretir."""
    if os.path.exists(CIKTI) or not os.path.exists(HAM):
        return
    s = uret()
    print(f"gdx_uret: {len(s)} GDX ürünü data/yeni/gdx.xml dosyasına yazıldı")


if __name__ == "__main__":
    calistir()
