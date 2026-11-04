#!/usr/bin/env python3
"""Foto Ekspres - günlük fiyat/stok senkronizasyonu.

- data/urunler.xml : sitedeki tüm FE- ürünlerinin ana listesi (yoksa git geçmişinden kurulur)
- gruplar.csv      : grup adı, kaynak liste sayfası, site tipi, minimum fiyat
- feed/fotoekspres.xml : İdeaSoft'un çektiği güncel dosya (tüm ürünler, güncel fiyat/stok)
- rapor/ozet.txt, rapor/yeni-urunler.csv : günlük rapor
"""
import csv
import html
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
RAPOR = os.path.join(KOK, "rapor")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
STOK_VAR = 5
ALANLAR = ["id", "name", "brand", "sku", "barcode", "price", "currency", "stock", "availability",
           "category", "description", "status"]


def satis_fiyati(kaynak):
    return int(math.floor(kaynak * 1.02 + 0.5))


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


def getir(url, deneme=3):
    for i in range(deneme):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
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
            sirali = [dosya_adi(x) for x in re.findall(r"/shop/\w+/\d+/myassets/products/\d+/([^\"'\s)]+)", p)]
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


def dosya_adi(u):
    """Görsel dosya adını karşılaştırılabilir hale getirir (küçük harf, ?revision ve _min eki yok)."""
    a = re.sub(r"[?#].*$", "", u).rsplit("/", 1)[-1].lower()
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


def yaz(urunler, yol):
    satir = ['<?xml version="1.0" encoding="UTF-8"?>', '<products source_id="1" source_name="fotoekspres-sync">']
    for i, u in enumerate(urunler, 1):
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
    if os.path.exists(ANA):
        urunler = oku(open(ANA, encoding="utf-8").read())
    else:
        urunler = gecmisten_kur()
    if not urunler:
        print("Ürün listesi boş, çıkılıyor.")
        return 1
    gruplar = list(csv.DictReader(open(GRUP, encoding="utf-8")))
    elle = {}
    if os.path.exists(ESLESME):
        for r in csv.DictReader(open(ESLESME, encoding="utf-8")):
            elle[r["sku"].strip()] = r["url"].strip().rstrip("/").rsplit("/", 1)[-1]
    ozet, yeniler = [], []
    for g in gruplar:
        ad, url, tip, alt = g["grup"], g["url"], g["tip"], float(g.get("min_fiyat") or 0)
        print(f"== {ad}: {url}")
        kartlar = ideasoft_liste(url) if tip == "ideasoft" else ticimax_liste(url)
        bizim = [u for u in urunler if u["category"] == ad]
        if not kartlar:
            ozet.append(f"{ad}: KAYNAK OKUNAMADI, bu grup bugün güncellenmedi ({len(bizim)} ürün)")
            continue
        eslesen = set()
        plan = {}
        for u in bizim:
            k = urun_anahtari(u)
            ilk = dosya_adi(u["imgs"][0]) if u["imgs"] else ""
            eski_kaynak = float(u["price"] or 0) / 1.02
            adaylar = [c for c in kartlar if c["anahtar"] & k]

            def puan(c):
                # Kart ana görseli bizim ana görselimizse en güçlü eşleşme; sonra ortak görsel; en son fiyat yakınlığı
                return (c["ilk"] == ilk, c["ilk"] in k, len(c["anahtar"] & k), -abs(c["fiyat"] - eski_kaynak))
            kart = max(adaylar, key=puan) if adaylar else None
            if u["sku"] in elle:
                kart = next((c for c in kartlar if c["url"].rstrip("/").rsplit("/", 1)[-1] == elle[u["sku"]]), None)
            if kart:
                eslesen.add(id(kart))
            if kart and kart["stok"] and kart["fiyat"] > 0:
                plan[u["sku"]] = (str(satis_fiyati(kart["fiyat"])), str(STOK_VAR))
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
            if id(c) not in eslesen and c["stok"] and c["fiyat"] > 0 and c["fiyat"] >= alt:
                yeniler.append([ad, c["ad"], f"{c['fiyat']:.2f}", c["url"]])
        ozet.append(f"{ad}: kaynakta {len(kartlar)} ürün, bizde {len(bizim)}, eşleşen {len(eslesen)}, "
                    f"değişen {degisen}, stoğu sıfırlanan {sifirlanan}"
                    + (f"\n  stokta olmayan/bulunamayan: {', '.join(bulunamayan)}" if bulunamayan else ""))
    yaz(urunler, ANA)
    yaz(urunler, FEED)
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
