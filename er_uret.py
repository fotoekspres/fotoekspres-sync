#!/usr/bin/env python3
"""Erdijital XML'inden iki dosya üretir (sync.py her gece çağırır):

feed/er_hafif.xml : tüm ürünler, açıklamalar (<details>) çıkarılmış. Erdijital
                    entegrasyonunda SADECE Stok adımı ile kullanılır.
feed/er_yeni.xml  : sadece sitede olmayan ürünler (data/er_mevcut.txt'de olmayan
                    stok kodları). Açıklamalar temizlenir, erdijital izleri silinir,
                    "Neden Foto Ekspres?" eklenir; erdijital adlı görseller
                    feed/er_img/ altına temiz adla kopyalanır.
data/er_yeni_kodlar.txt : er_yeni.xml içindeki kodlar.
feed/er_duzelt.xml : data/er_duzelt_kodlar.txt'deki ürünler, temizlenmiş açıklamayla (sadece Detay adımı).

`python er_uret.py --eklendi` : er_yeni_kodlar.txt içindeki kodları er_mevcut.txt'ye
ekler (yeni ürünler siteye yüklendikten sonra "Yeni ürünler eklendi" iş akışı çalıştırır).
"""
import os
import re
import sys
import time
import urllib.request
from urllib.parse import urljoin

KOK = os.path.dirname(os.path.abspath(__file__))
KAYNAK = "https://www.erdijital.com/output/9876542933"
MEVCUT = os.path.join(KOK, "data", "er_mevcut.txt")
YENI_KOD = os.path.join(KOK, "data", "er_yeni_kodlar.txt")
DUZELT_KOD = os.path.join(KOK, "data", "er_duzelt_kodlar.txt")  # açıklaması yeniden yazılacak ürünler
DUZELT = os.path.join(KOK, "feed", "er_duzelt.xml")
HAFIF = os.path.join(KOK, "feed", "er_hafif.xml")
YENI = os.path.join(KOK, "feed", "er_yeni.xml")
IMG = os.path.join(KOK, "feed", "er_img")
RAW = "https://raw.githubusercontent.com/fotoekspres/fotoekspres-sync/main/feed/er_img/"
SARMAL = '<div style="text-align:center;color:#000000;font-family:helvetica, arial, sans-serif;font-size:14pt;">'
STIL_SIL = re.compile(r"(?i)(?<![\w-])(color|background|background-color|font-family|font-size)\s*:[^;\"']*;?")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

NEDEN = ["Resmi Türkiye Garantili ürün", "14 gün içinde ücretsiz iade ve değişim",
         "İstanbul içi kurye ile aynı gün teslimat imkânı", "Sirkeci mağazamızda uzman destek",
         "Havale/EFT ile ödeme seçeneği"]
ER = re.compile(r"\ber[\s\-_.]*dijital\b(\.com(\.tr)?)?", re.I)
TEL = re.compile(r"(?i)((tel|telefon|gsm|cep|whatsapp|iletişim)\s*(no|hattı)?\s*:?\s*)?(\+90[\s\-]?|\b0[\s\-]?)\(?[2-5]\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b")


def getir(url, ikili=False, deneme=3):
    for i in range(deneme):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                v = r.read()
                return v if ikili else v.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print(f"er_uret: {url} alınamadı ({e})")
            time.sleep(3 * (i + 1))
    return None


def alan(item, ad):
    m = re.search(rf"<{ad}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{ad}>", item, re.S)
    return m.group(1).strip() if m else ""


def kod_oku(yol):
    if not os.path.exists(yol):
        return set()
    return {s.strip() for s in open(yol, encoding="utf-8") if s.strip()}


def dosya_adi(metin):
    t = metin.lower()
    for a, b in zip("çğıöşüâî", "cgiosuai"):
        t = t.replace(a, b)
    t = ER.sub("", t)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:70] or "urun"


def gorsel_kopyala(url, ad):
    """Görseli feed/er_img/<ad>.<uzantı> olarak kaydeder, raw adresini döner."""
    uz = (re.search(r"\.(jpe?g|png|webp|gif)(?:[?#]|$)", url, re.I) or [None, "jpg"])[1].lower()
    dosya = f"{ad}.{uz}"
    yol = os.path.join(IMG, dosya)
    if not os.path.exists(yol):
        veri = getir(url, ikili=True, deneme=2)
        if not veri or len(veri) < 500:
            return None
        os.makedirs(IMG, exist_ok=True)
        with open(yol, "wb") as f:
            f.write(veri)
    return RAW + dosya


def temizle(html, ad):
    """Açıklamayı kısaltmadan erdijital izlerinden arındırır."""
    h = re.sub(r"<script.*?</script>", "", html, flags=re.S | re.I)
    sayac = [0]

    def img(m):
        tag = m.group(0)
        src = re.search(r"""src\s*=\s*["']([^"']+)["']""", tag, re.I)
        if not src:
            return ""
        s = src.group(1)
        erde = s.startswith("/") and not s.startswith("//") or "erdijital" in s.lower()
        if erde and re.search(r"whatsapp|logo|banner|iletisim|kargo|kampanya", s, re.I):
            return ""  # erdijital'in kendi tanıtım/iletişim görselleri alınmaz
        if erde or re.search(r"dijital", s.rsplit("/", 1)[-1], re.I):
            tam = urljoin("https://www.erdijital.com/", s)
            sayac[0] += 1
            yeni = gorsel_kopyala(tam, f"{ad}-aciklama-{sayac[0]}")
            if not yeni:
                return ""
            tag = tag.replace(s, yeni)
        return ER.sub("Foto Ekspres", tag)

    h = re.sub(r"<img\b[^>]*>", img, h, flags=re.I)
    # erdijital'e giden linkler: link kalkar, yazı kalır
    h = re.sub(r"""<a\b[^>]*href\s*=\s*["'][^"']*erdijital[^"']*["'][^>]*>(.*?)</a>""", r"\1", h, flags=re.S | re.I)
    h = ER.sub("Foto Ekspres", h)
    h = TEL.sub("", h)
    # site standardı: siyah yazı, Helvetica 14pt; kaynağın gri yazı/zemin ve yazı tipi ayarları silinir
    h = re.sub(r"""style\s*=\s*(["'])(.*?)\1""", lambda m: f'style="{STIL_SIL.sub("", m.group(2)).strip()}"', h, flags=re.S | re.I)
    h = re.sub(r'\s*style=""', "", h)
    h = re.sub(r"(?i)<font\b[^>]*>|</font>", "", h)
    h = re.sub(r"(?i)\s(bgcolor|color)\s*=\s*[\"'][^\"']*[\"']", "", h)
    h += ('\n<div>&nbsp;</div>\n<div><strong>Neden Foto Ekspres?</strong></div>\n'
          + "\n".join(f"<div>{x}</div>" for x in NEDEN))
    return SARMAL + "\n" + h + "\n</div>"


def cdata(s):
    return "<![CDATA[" + s.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def degistir(item, ad, deger):
    return re.sub(rf"<{ad}>.*?</{ad}>", lambda _: f"<{ad}>{cdata(deger)}</{ad}>", item, count=1, flags=re.S)


def yeni_urun(item):
    kod = alan(item, "stockCode")
    isim = alan(item, "label")
    ad = dosya_adi(isim or kod)
    for t in ("label", "title", "keywords"):
        v = alan(item, t)
        if v and ER.search(v):
            item = degistir(item, t, re.sub(r"\s{2,}", " ", ER.sub("Foto Ekspres" if t != "label" else "", v)).strip(" -|,"))
    item = degistir(item, "details", temizle(alan(item, "details"), ad))
    for n in range(1, 9):
        t = f"picture{n}Path"
        u = alan(item, t)
        if u and re.search(r"dijital", u.rsplit("/", 1)[-1], re.I):
            yeni = gorsel_kopyala(u, f"{ad}-{n}")
            if yeni:
                item = degistir(item, t, yeni)
    return item


def calistir():
    xml = getir(KAYNAK)
    if not xml or "<item>" not in xml:
        print("er_uret: erdijital XML alınamadı, dosyalar değiştirilmedi")
        return
    bas = xml[: xml.index("<item>")]
    son = xml[xml.rindex("</item>") + len("</item>"):]
    items = re.findall(r"<item>.*?</item>", xml, re.S)
    mevcut = kod_oku(MEVCUT)
    hafif = [re.sub(r"\s*<details>.*?</details>", "", i, flags=re.S) for i in items]
    yeniler, kodlar = [], []
    if mevcut:  # liste yoksa yeni dosya üretilmez (tümü yeni sanılmasın)
        for i in items:
            k = alan(i, "stockCode")
            if k and k not in mevcut:
                yeniler.append(yeni_urun(i))
                kodlar.append(k)
    os.makedirs(os.path.dirname(HAFIF), exist_ok=True)
    with open(HAFIF, "w", encoding="utf-8") as f:
        f.write(bas + "\n".join(hafif) + son)
    with open(YENI, "w", encoding="utf-8") as f:
        f.write(bas + "\n".join(yeniler) + son)
    duz = kod_oku(DUZELT_KOD)
    with open(DUZELT, "w", encoding="utf-8") as f:
        f.write(bas + "\n".join(yeni_urun(i) for i in items if alan(i, "stockCode") in duz) + son)
    with open(YENI_KOD, "w", encoding="utf-8") as f:
        f.write("\n".join(kodlar) + ("\n" if kodlar else ""))
    print(f"er_uret: {len(items)} ürün, hafif {os.path.getsize(HAFIF) / 1e6:.1f} MB, "
          f"yeni {len(yeniler)} ürün {os.path.getsize(YENI) / 1e6:.1f} MB")


def eklendi():
    yeni = kod_oku(YENI_KOD)
    mevcut = kod_oku(MEVCUT)
    with open(MEVCUT, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(mevcut | yeni)) + "\n")
    print(f"er_uret: {len(yeni - mevcut)} kod mevcut listesine eklendi")


if __name__ == "__main__":
    eklendi() if "--eklendi" in sys.argv else calistir()
