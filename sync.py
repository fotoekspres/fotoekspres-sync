#!/usr/bin/env python3
"""Foto Ekspres - günlük fiyat/stok senkronizasyonu.

- data/urunler.xml : sitedeki tüm FE- ürünlerinin ana listesi (yoksa git geçmişinden kurulur)
- gruplar.csv      : grup adı, kaynak liste sayfası, site tipi, minimum fiyat, marj, filtre (ürün adı için regex, boşsa hepsi)
- data/yeni/*.xml  : elle hazırlanan yeni ürünler; ana listede olmayan stok kodları bir kez eklenir
- feed/fotoekspres.xml : İdeaSoft'un çektiği güncel dosya (tüm ürünler, güncel fiyat/stok)
- rapor/ozet.txt, rapor/yeni-urunler.csv : günlük rapor
"""
import csv
import html
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

KOK = os.path.dirname(os.path.abspath(__file__))
FEED = os.path.join(KOK, "feed", "fotoekspres.xml")
ANA = os.path.join(KOK, "data", "urunler.xml")
GRUP = os.path.join(KOK, "gruplar.csv")
ESLESME = os.path.join(KOK, "eslesme.csv")
KAYNAK = os.path.join(KOK, "data", "kaynak.csv")
HARIC = os.path.join(KOK, "haric.csv")
RAPOR = os.path.join(KOK, "rapor")
YENI = os.path.join(KOK, "data", "yeni")
TASIMA = os.path.join(KOK, "data", "tasima.csv")  # sku,grup: grubu değiştirir; grup SİLİNDİ ise feed'e yazılmaz (id sırası korunur)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
STOK_VAR = 5
ALANLAR = ["id", "name", "brand", "sku", "barcode", "price", "currency", "stock", "availability",
           "category", "description", "status"]


def satis_fiyati(kaynak, marj=2.0):
    """Kaynak (indirimli) fiyat + grup marjı (%), tam TL'ye yuvarlanır. Marj gruplar.csv'deki 'marj' sütunundan gelir."""
    return int(math.floor(kaynak * (1 + marj / 100) + 0.5))


def para(s):
    s = re.sub(r"[^\d,\.]", "", html.unescape(s or ""))
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1 or re.search(r"\.\d{3}$", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


_ONBELLEK = {}


def getir(url, deneme=3):
    if url in _ONBELLEK:
        return _ONBELLEK[url]
    for i in range(deneme):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9"})
            with urllib.request.urlopen(req, timeout=40) as r:
                _ONBELLEK[url] = r.read().decode("utf-8", "replace")
                return _ONBELLEK[url]
        except Exception as e:  # noqa: BLE001
            print(f"  ! {url} -> {e}")
            time.sleep(3 * (i + 1))
    return None


def temiz(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


# ---------------------------------------------------------------- kaynak siteler
def ideasoft_liste(url):
    """Klasfoto / Novafotograf (İdeaSoft) liste sayfaları. Anahtar: shop kodu + ürün klasörü."""
    kartlar, gorulen = [], set()
    for sayfa in range(1, 60):
        h = getir(url + ("&" if "?" in url else "?") + f"tp={sayfa}")
        if h is None:
            return None
        parcalar = re.split(r'<div[^>]+class="[^"]*\bshowcase\b(?![-_])[^"]*"', h)[1:]
        yeni = 0
        for p in parcalar:
            m = re.search(r'showcase-title.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', p, re.S)
            sirali = [dosya_adi(x) for x in re.findall(r"/shop/\w+/\d+/(myassets/products/\d+/[^\"'\s)]+)", p)]
            dosyalar = set(sirali)
            if not m or not dosyalar:
                continue
            anahtar = dosyalar
            if m.group(1) in gorulen:
                continue
            gorulen.add(m.group(1))
            yeni += 1
            f = re.search(r'showcase-price-new[^>]*>(.*?)</div>', p, re.S)
            stok_yok = bool(re.search(r"stokta yok|tükendi|no-stock", p, re.I))
            kartlar.append(dict(anahtar=anahtar, ilk=sirali[0], ad=temiz(m.group(2)), url=m.group(1),
                                fiyat=para(temiz(f.group(1))) if f else 0.0, stok=not stok_yok))
        if yeni == 0:
            break
        time.sleep(1)
    return kartlar


def ticimax_liste(url):
    """Fotokolik (Ticimax) liste sayfaları. Anahtar: görsel dosya adı."""
    kartlar, gorulen = [], set()
    for sayfa in range(1, 60):
        h = getir(url + ("&" if "?" in url else "?") + f"sayfa={sayfa}")
        if h is None:
            return None
        parcalar = re.split(r'<div[^>]+class="[^"]*\bproductItem\b[^"]*"', h)[1:]
        yeni = 0
        for p in parcalar:
            m = re.search(r'productName.*?<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', p, re.S)
            if not m:
                continue
            u = m.group(1)
            if u in gorulen:
                continue
            gorulen.add(u)
            yeni += 1
            sirali = [dosya_adi(x) for x in re.findall(r"urunresimleri/[a-z]+/([^\"'?\s)]+)", p, re.I)]
            imgs = set(sirali)
            f = re.search(r'discountPriceSpan[^>]*>(.*?)<', p, re.S) or re.search(r'productPrice[^>]*>.*?(₺[\d\.,]+|[\d\.,]+\s*TL)', p, re.S)
            stok_yok = bool(re.search(r"stokta yok|tükendi", temiz(p), re.I))
            kartlar.append(dict(anahtar=imgs, ilk=sirali[0] if sirali else "", ad=temiz(m.group(2)), url=u if u.startswith("http") else "https://www.fotokolik.com" + u,
                                fiyat=para(temiz(f.group(1))) if f else 0.0, stok=not stok_yok))
        if yeni == 0:
            break
        time.sleep(1)
    return kartlar


def tsoft_liste(url):
    """Fotografium (T-Soft) liste sayfaları (?stock=1). Eşleştirme kaynak linkiyle (data/kaynak.csv) yapılır."""
    kartlar, gorulen = [], set()
    kok = re.match(r"https?://[^/]+", url).group(0)
    for sayfa in range(1, 60):
        h = getir(url + ("&" if "?" in url else "?") + f"pg={sayfa}")
        if h is None:
            return None
        parcalar = re.split(r'<div class="fl col-12 kmpContent', h)[1:]
        yeni = 0
        for p in parcalar:
            m = re.search(r'<a href="([^"]+)" title="([^"]*)" class="[^"]*listProductName', p)
            if not m:
                continue
            u = m.group(1)
            if u in gorulen:
                continue
            gorulen.add(u)
            yeni += 1
            f = re.search(r'data-price="([\d\.,]+)"', p)
            stok = "schema.org/InStock" in p
            kartlar.append(dict(anahtar=set(), ilk="", ad=temiz(m.group(2)), url=u if u.startswith("http") else kok + u,
                                fiyat=para(f.group(1)) if f else 0.0, stok=stok))
        if yeni == 0:
            break
        time.sleep(1)
    return kartlar



def fotocarsi_liste(url):
    """Fotoçarşı liste sayfaları (&p=N). Eşleştirme kaynak linkiyle (data/yeni/*.csv) yapılır."""
    kartlar, gorulen = [], set()
    for sayfa in range(1, 60):
        h = getir(url + ("&" if "?" in url else "?") + f"p={sayfa}")
        if h is None:
            return None
        yeni = 0
        for p in re.split(r'<article class="product', h)[1:]:
            m = re.search(r'<h3[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', p, re.S)
            if not m:
                continue
            u = html.unescape(m.group(1))
            if u in gorulen:
                continue
            gorulen.add(u)
            yeni += 1
            f = re.search(r'class="price[^"]*".*?<strong>(.*?)</strong>', p, re.S)
            stok = bool(re.search(r'class="badge[^"]*"[^>]*>\s*Stokta', p))
            kartlar.append(dict(anahtar=set(), ilk="", ad=temiz(m.group(2)), url=u if u.startswith("http") else "https://fotocarsi.com" + u,
                                fiyat=para(temiz(f.group(1))) if f else 0.0, stok=stok))
        if yeni == 0:
            break
        time.sleep(1)
    return kartlar

def shopify_urunler(url):
    """Shopify mağazasındaki tüm ürünler (products.json, sayfa başına 250)."""
    kok = re.match(r"https?://[^/]+", url).group(0)
    hepsi = []
    for sayfa in range(1, 40):
        h = getir(f"{kok}/products.json?limit=250&page={sayfa}")
        if h is None:
            return None
        try:
            p = json.loads(h).get("products") or []
        except ValueError:
            return None
        if not p:
            break
        hepsi += p
        time.sleep(1)
    return hepsi


def shopify_liste(url):
    """GDX / Can Foto (Shopify). Eşleştirme kaynak linkiyle (ürün handle'ı) yapılır."""
    kok = re.match(r"https?://[^/]+", url).group(0)
    urunler = shopify_urunler(url)
    if urunler is None:
        return None
    kartlar = []
    for p in urunler:
        v = (p.get("variants") or [{}])[0]
        imgs = [i.get("src", "") for i in p.get("images") or []]
        kartlar.append(dict(anahtar={dosya_adi(i) for i in imgs}, ilk=dosya_adi(imgs[0]) if imgs else "",
                            ad=temiz(p.get("title", "")), url=f"{kok}/products/{p.get('handle', '')}",
                            fiyat=float(v.get("price") or 0), stok=bool(v.get("available"))))
    return kartlar


def xml_liste(url):
    """İdeaSoft standart XML'i (xmlbankasi / Ekinci): item > stockCode, label, price1, currencyAbbr, stockAmount, pictureNPath.
    Ham dosya data/ham/<dosya adı> olarak saklanır (ilk ürün üretimi için). Eşleştirme stok koduyla (url sonu) yapılır."""
    h = getir(url)
    if not h or "<item>" not in h:
        return None
    os.makedirs(os.path.join(KOK, "data", "ham"), exist_ok=True)
    with open(os.path.join(KOK, "data", "ham", url.rstrip("/").rsplit("/", 1)[-1]), "w", encoding="utf-8") as f:
        f.write(h)
    kok = url.rsplit("/", 1)[0]

    def alan(i, ad):
        m = re.search(rf"<{ad}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{ad}>", i, re.S)
        return m.group(1).strip() if m else ""
    kartlar = []
    for i in re.findall(r"<item>.*?</item>", h, re.S):
        kod = alan(i, "stockCode")
        imgs = [alan(i, f"picture{n}Path") for n in range(1, 9)]
        imgs = [x for x in imgs if x]
        try:
            fiyat, stok = float(alan(i, "price1") or 0), float(alan(i, "stockAmount") or 0) > 0
        except ValueError:
            fiyat, stok = 0.0, False
        kartlar.append(dict(anahtar={dosya_adi(x) for x in imgs}, ilk=dosya_adi(imgs[0]) if imgs else "",
                            ad=temiz(alan(i, "label")), url=f"{kok}/{kod}", fiyat=fiyat, stok=stok, ham_fiyat=True))
    return kartlar


def shopify_ham():
    """data/ham_kaynak.txt içindeki Shopify mağazalarının ham ürün verisini data/ham/<alan>.json olarak kaydeder."""
    yol = os.path.join(KOK, "data", "ham_kaynak.txt")
    if not os.path.exists(yol):
        return
    for satir in open(yol, encoding="utf-8"):
        u = satir.strip()
        if not u or u.startswith("#"):
            continue
        p = shopify_urunler(u)
        alan = re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
        if p is None:
            print(f"ham veri alınamadı: {u}")
            continue
        os.makedirs(os.path.join(KOK, "data", "ham"), exist_ok=True)
        with open(os.path.join(KOK, "data", "ham", alan + ".json"), "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False)
        print(f"ham veri: {alan} {len(p)} ürün")


def slug(u):
    m = re.search(r"[?&]slug=([^&#]+)", u or "")
    if m:
        return m.group(1).lower()
    return re.sub(r"[?#].*$", "", u or "").rstrip("/").rsplit("/", 1)[-1].lower()


def dosya_adi(u):
    """Görsel dosya adını karşılaştırılabilir hale getirir (küçük harf, ?revision ve _min eki yok)."""
    u = re.sub(r"[?#].*$", "", u)
    k = re.search(r"myassets/products/(\d+/[^/]+)$", u)  # İdeaSoft: klasör/dosya
    a = (k.group(1) if k else u.rsplit("/", 1)[-1]).lower()
    return re.sub(r"_min(?=\.[a-z]+$)", "", a)


def urun_anahtari(urun):
    return {dosya_adi(g) for g in urun["imgs"]}


# ---------------------------------------------------------------- ana liste
def oku(xml_metni):
    kok = ET.fromstring(xml_metni.encode("utf-8") if isinstance(xml_metni, str) else xml_metni)
    out = []
    for p in kok.findall("product"):
        d = {a: (p.findtext(a) or "") for a in ALANLAR}
        d["imgs"] = [p.findtext(f"image{i}") for i in range(1, 9) if p.findtext(f"image{i}")]
        out.append(d)
    return out


def gecmisten_kur():
    loglar = subprocess.run(["git", "log", "--reverse", "--format=%H", "--", "feed/fotoekspres.xml"],
                            cwd=KOK, capture_output=True, text=True).stdout.split()
    urunler = {}
    for h in loglar:
        r = subprocess.run(["git", "show", f"{h}:feed/fotoekspres.xml"], cwd=KOK, capture_output=True)
        try:
            for u in oku(r.stdout):
                m = re.match(r"FE-[A-Z]{3}-(\d+)$", u["sku"])
                if m and int(m.group(1)) >= 13478:
                    urunler[u["sku"]] = u
        except ET.ParseError:
            continue
    print(f"Git geçmişinden {len(urunler)} ürün kuruldu.")
    return sorted(urunler.values(), key=lambda u: int(u["sku"].rsplit("-", 1)[1]))


def cdata(s):
    return "<![CDATA[" + str(s).replace("]]>", "]]]]><![CDATA[>") + "]]>"


def tasima_oku():
    if not os.path.exists(TASIMA):
        return {}
    return {r["sku"].strip(): r["grup"].strip() for r in csv.DictReader(open(TASIMA, encoding="utf-8")) if r.get("sku")}


def silinenler():
    return {k for k, v in tasima_oku().items() if v == "SİLİNDİ"}


def yaz(urunler, yol, sadece=None, tumu=False):
    """sadece: verilirse yalnızca bu stok kodlu ürünler yazılır (id'ler tam listedeki sırayla aynı kalır).
    tumu=False iken data/tasima.csv'de grubu SİLİNDİ olan ürünler atlanır; id'ler yine değişmez."""
    sil = set() if tumu else silinenler()
    satir = ['<?xml version="1.0" encoding="UTF-8"?>', '<products source_id="1" source_name="fotoekspres-sync">']
    for i, u in enumerate(urunler, 1):
        if sadece is not None and u["sku"] not in sadece:
            continue
        if u["sku"] in sil:
            continue
        satir.append(" <product>")
        for a in ALANLAR:
            v = str(i) if a == "id" else u.get(a, "")
            satir.append(f"  <{a}>{cdata(v)}</{a}>" if v != "" else f"  <{a}/>")
        for k, g in enumerate(u["imgs"][:8], 1):
            satir.append(f"  <image{k}>{cdata(g)}</image{k}>")
        satir.append(" </product>")
    satir.append("</products>")
    metin = "\n".join(satir) + "\n"
    ET.fromstring(metin.encode("utf-8"))
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        f.write(metin)


# ---------------------------------------------------------------- çalıştır
def main():
    shopify_ham()
    try:
        import gdx_uret  # GDX ürünlerini bir kez data/yeni/gdx.xml olarak üretir
        gdx_uret.calistir()
    except Exception as e:  # noqa: BLE001
        print(f"gdx_uret hata: {e}")
    try:
        import er_uret  # erdijital: hafif (stok) ve yeni ürün dosyaları
        er_uret.calistir()
    except Exception as e:  # noqa: BLE001
        print(f"er_uret hata: {e}")
    try:
        import ekinci_uret  # Ekinci ürünlerini bir kez data/yeni/ekinci.xml olarak üretir
        ekinci_uret.calistir()
    except Exception as e:  # noqa: BLE001
        print(f"ekinci_uret hata: {e}")
    if os.path.exists(ANA):
        urunler = oku(open(ANA, encoding="utf-8").read())
    else:
        urunler = gecmisten_kur()
    if not urunler:
        print("Ürün listesi boş, çıkılıyor.")
        return 1
    if os.path.isdir(YENI):
        mevcut = {u["sku"] for u in urunler}
        for ad_ in sorted(os.listdir(YENI)):
            if not ad_.endswith(".xml"):
                continue
            eklenen = 0
            for u in oku(open(os.path.join(YENI, ad_), encoding="utf-8").read()):
                if u["sku"] and u["sku"] not in mevcut:
                    urunler.append(u)
                    mevcut.add(u["sku"])
                    eklenen += 1
            if eklenen:
                print(f"{ad_}: {eklenen} yeni ürün ana listeye eklendi")
    # data/tasima.csv (sku,grup): ürünün takip edildiği grubu (kaynak siteyi) değiştirir
    tasima = tasima_oku()
    for u in urunler:
        if u["sku"] in tasima:
            u["category"] = tasima[u["sku"]]
    # data/gorsel.csv (sku,gorseller): görsel listesini düzeltir; gorseller '|' ile ayrılır, en fazla 8
    gorsel_yol = os.path.join(KOK, "data", "gorsel.csv")
    if os.path.exists(gorsel_yol):
        gorsel = {r["sku"].strip(): [g.strip() for g in r["gorseller"].split("|") if g.strip()][:8]
                  for r in csv.DictReader(open(gorsel_yol, encoding="utf-8")) if r.get("sku") and r.get("gorseller")}
        for u in urunler:
            if u["sku"] in gorsel:
                u["imgs"] = gorsel[u["sku"]]
    gruplar = list(csv.DictReader(open(GRUP, encoding="utf-8")))
    elle = {}
    if os.path.exists(ESLESME):
        for r in csv.DictReader(open(ESLESME, encoding="utf-8")):
            elle[r["sku"].strip()] = slug(r["url"])
    ogrenilen = {}
    if os.path.exists(KAYNAK):
        for r in csv.DictReader(open(KAYNAK, encoding="utf-8")):
            ogrenilen[r["sku"].strip()] = slug(r["url"])
    if os.path.isdir(YENI):
        for ad_ in sorted(os.listdir(YENI)):
            if ad_.endswith(".csv"):
                for r in csv.DictReader(open(os.path.join(YENI, ad_), encoding="utf-8")):
                    ogrenilen.setdefault(r["sku"].strip(), slug(r["url"]))
    haric = set()
    if os.path.exists(HARIC):
        haric = {slug(r["url"]) for r in csv.DictReader(open(HARIC, encoding="utf-8")) if r.get("url")}
    yeni_kaynak = {}
    ozet, yeniler = [], []
    for g in gruplar:
        ad, url, tip, alt = g["grup"], g["url"], g["tip"], float(g.get("min_fiyat") or 0)
        marj = float(g.get("marj") or 2)
        print(f"== {ad}: {url}")
        kartlar = ideasoft_liste(url) if tip == "ideasoft" else tsoft_liste(url) if tip == "tsoft" else fotocarsi_liste(url) if tip == "fotocarsi" else shopify_liste(url) if tip == "shopify" else xml_liste(url) if tip == "xml" else ticimax_liste(url)
        filtre = (g.get("filtre") or "").strip()
        if kartlar and filtre:
            kartlar = [c for c in kartlar if re.search(filtre, c["ad"], re.I)]
        bizim = [u for u in urunler if u["category"] == ad]
        if not kartlar:
            ozet.append(f"{ad}: KAYNAK OKUNAMADI, bu grup bugün güncellenmedi ({len(bizim)} ürün)")
            continue
        eslesen = set()
        plan = {}
        for u in bizim:
            k = urun_anahtari(u)
            ilk = dosya_adi(u["imgs"][0]) if u["imgs"] else ""
            eski_kaynak = float(u["price"] or 0) / (1 + marj / 100)
            adaylar = [c for c in kartlar if c["anahtar"] & k]

            def puan(c):
                # Kart ana görseli bizim ana görselimizse en güçlü eşleşme; sonra ortak görsel; en son fiyat yakınlığı
                return (c["ilk"] == ilk, c["ilk"] in k, len(c["anahtar"] & k), -abs(c["fiyat"] - eski_kaynak))
            kart = max(adaylar, key=puan) if adaylar else None
            hedef = elle.get(u["sku"]) or ogrenilen.get(u["sku"])
            if hedef:
                kart = next((c for c in kartlar if slug(c["url"]) == hedef), None) or (None if u["sku"] in elle else kart)
            if kart:
                yeni_kaynak[u["sku"]] = kart["url"]
            if kart:
                eslesen.add(id(kart))
            if kart and kart["stok"] and kart["fiyat"] > 0:
                if kart.get("ham_fiyat") and not marj:
                    # XML fiyatı olduğu gibi (para birimi ve KDV ayarı sitede yapılır); kuruş korunur
                    plan[u["sku"]] = (f"{kart['fiyat']:.2f}".rstrip("0").rstrip("."), str(STOK_VAR))
                else:
                    plan[u["sku"]] = (str(satis_fiyati(kart["fiyat"], marj)), str(STOK_VAR))
            else:
                plan[u["sku"]] = (u["price"], "0")
        oran = len(eslesen) / max(1, len(bizim))
        if bizim and oran < 0.5:
            # Kaynak sitenin yapısı değişmiş olabilir: güvenlik için bu grup bugün değiştirilmez
            ozet.append(f"{ad}: UYARI eşleşme oranı düşük (%{oran*100:.0f}, kaynakta {len(kartlar)} kart), grup güncellenmedi")
            print("  örnek kart:", kartlar[0]["ad"], sorted(kartlar[0]["anahtar"])[:3], kartlar[0]["fiyat"])
            print("  örnek ürün:", bizim[0]["name"], sorted(urun_anahtari(bizim[0]))[:3])
            continue
        bulunamayan = [u["sku"] for u in bizim if plan[u["sku"]][1] == "0"]
        degisen = sifirlanan = 0
        for u in bizim:
            yeni = plan[u["sku"]]
            if yeni != (u["price"], u["stock"]):
                degisen += 1
                if yeni[1] == "0" and u["stock"] != "0":
                    sifirlanan += 1
                u["price"], u["stock"] = yeni
        for c in kartlar:
            if id(c) not in eslesen and c["stok"] and c["fiyat"] > 0 and c["fiyat"] >= alt and slug(c["url"]) not in haric:
                yeniler.append([ad, c["ad"], f"{c['fiyat']:.2f}", c["url"]])
        ozet.append(f"{ad}: kaynakta {len(kartlar)} ürün, bizde {len(bizim)}, eşleşen {len(eslesen)}, "
                    f"değişen {degisen}, stoğu sıfırlanan {sifirlanan}"
                    + (f"\n  stokta olmayan/bulunamayan: {', '.join(bulunamayan)}" if bulunamayan else ""))
    eski = {}
    if os.path.exists(KAYNAK):
        eski = {r["sku"]: r["url"] for r in csv.DictReader(open(KAYNAK, encoding="utf-8"))}
    eski.update(yeni_kaynak)
    os.makedirs(os.path.dirname(KAYNAK), exist_ok=True)
    with open(KAYNAK, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sku", "url"])
        for k in sorted(eski):
            w.writerow([k, eski[k]])
    yaz(urunler, ANA, tumu=True)
    yaz(urunler, FEED)
    # İlk yükleme dosyası: data/ilk_yukleme.txt içinde adı yazan data/yeni dosyalarındaki ürünler (İdeaSoft'a güvenli ilk aktarım için)
    ilk = os.path.join(KOK, "data", "ilk_yukleme.txt")
    if os.path.exists(ilk):
        dosyalar = [x.strip() for x in open(ilk, encoding="utf-8") if x.strip() and not x.startswith("#")]
        skular = set()
        for ad_ in dosyalar:
            yol_ = os.path.join(YENI, ad_)
            if not os.path.exists(yol_):
                yol_ = os.path.join(KOK, "data", ad_)
            if os.path.exists(yol_) and ad_.endswith(".csv"):
                skular |= {r["sku"].strip() for r in csv.DictReader(open(yol_, encoding="utf-8")) if r.get("sku")}
            elif os.path.exists(yol_):
                skular |= {u["sku"] for u in oku(open(yol_, encoding="utf-8").read())}
        if skular:
            yaz(urunler, os.path.join(KOK, "feed", "ilk_yukleme.xml"), skular)
            print(f"feed/ilk_yukleme.xml: {len(skular)} ürün")
    os.makedirs(RAPOR, exist_ok=True)
    with open(os.path.join(RAPOR, "ozet.txt"), "w", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M UTC\n", time.gmtime()) + "\n".join(ozet) + "\n")
    with open(os.path.join(RAPOR, "yeni-urunler.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["grup", "urun", "kaynak_fiyat", "url"])
        w.writerows(yeniler)
    print("\n".join(ozet))
    print(f"Yeni ürün adayı: {len(yeniler)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
