"""
Adaptasi scraper.py yang diberikan pengguna.
Mengumpulkan hasil Google Maps ke CSV/XLSX dan mengirimnya ke antrean review backend.
Data TIDAK otomatis diterbitkan sebagai resort.
"""
import asyncio
import os
import sys
import urllib.parse
import requests
import pandas as pd
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

KATEGORI = os.getenv("SCRAPER_QUERY", "Pantai resort penginapan hotel homestay")
LOKASI = os.getenv("SCRAPER_LOCATION", "Kecamatan Bantur, Malang Selatan, Jawa Timur, Indonesia")
MAX_RESULTS = int(os.getenv("SCRAPER_MAX_RESULTS", "30"))
SCROLL_DEPTH = int(os.getenv("SCRAPER_SCROLL_DEPTH", "10"))
BACKEND = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
API_KEY = os.getenv("API_KEY", "")


async def main():
    query = f"{KATEGORI} di {LOKASI}"
    url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
    user_agent = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    print(f"[*] Memulai scraper: {query}")
    collected = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(user_agent=user_agent, viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_selector('div[role="feed"]', timeout=20000)
            await asyncio.sleep(3)
            feed = page.locator('div[role="feed"]')
            for _ in range(SCROLL_DEPTH):
                await feed.evaluate("(el) => el.scrollTo(0, el.scrollHeight)")
                await asyncio.sleep(1.5)

            cards = page.locator("a[href*='/maps/place/']")
            hrefs, seen = [], set()
            for i in range(await cards.count()):
                href = await cards.nth(i).get_attribute("href")
                if href and href not in seen:
                    seen.add(href)
                    hrefs.append(href)

            targets = hrefs[:MAX_RESULTS]
            print(f"[*] Terdeteksi {len(hrefs)} tempat; diproses {len(targets)}.")
            for i, place_url in enumerate(targets, start=1):
                try:
                    await page.goto(place_url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(1.2)
                    async def text_or(selector, fallback):
                        try:
                            return (await page.locator(selector).first.inner_text(timeout=2500)).replace("\n", " ").strip()
                        except Exception:
                            return fallback
                    name = await text_or("h1.DUwDvf", "tidak ada nama")
                    address = await text_or('button[data-item-id="address"]', "")
                    phone = await text_or('button[data-item-id^="phone:tel:"]', "")
                    hours = await text_or('div[data-item-id="oh"]', "")
                    rating_text = await text_or("div.F7nice span", "")
                    try:
                        rating = float(rating_text.replace(",", ".").split()[0])
                        if not 0 <= rating <= 5:
                            rating = None
                    except Exception:
                        rating = None
                    try:
                        photo = await page.locator("div.ZKCDEc img, div.Appis1 img").first.get_attribute("src", timeout=2500)
                    except Exception:
                        photo = ""
                    collected.append({
                        "no": i, "nama_tempat": name, "rating": rating, "alamat": address,
                        "telepon": phone, "jam_operasional": hours, "foto_url": photo or "",
                        "sumber_url": place_url
                    })
                    print(f"[+] [{i}/{len(targets)}] {name}")
                except Exception as exc:
                    print(f"[!] Item {i} dilewati: {exc}")
        finally:
            await browser.close()

    if not collected:
        print("[!] Tidak ada data yang terkumpul.")
        return

    os.makedirs("output", exist_ok=True)
    df = pd.DataFrame(collected)
    df.to_csv("output/Hasil_Scraping_Maps.csv", index=False, encoding="utf-8-sig")
    df.to_excel("output/Hasil_Scraping_Maps.xlsx", index=False, sheet_name="DataMaps", engine="xlsxwriter")
    print("[+] CSV dan XLSX tersimpan di folder output/.")

    if not API_KEY or len(API_KEY) < 32:
        print("[!] API_KEY belum diatur dengan benar; data hanya disimpan ke CSV/XLSX.")
        return
    try:
        response = requests.post(
            f"{BACKEND}/api/scraper/import",
            headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
            json=collected, timeout=45
        )
        response.raise_for_status()
        print(f"[+] Hasil dikirim ke antrean review backend: {response.json()}")
    except requests.RequestException as exc:
        print(f"[!] Pengiriman ke backend gagal: {exc}. CSV/XLSX tetap tersimpan.")


if __name__ == "__main__":
    asyncio.run(main())
