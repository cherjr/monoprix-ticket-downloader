import asyncio
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import unquote

from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def resolve_local_path(value: str) -> str:
    path = Path(value)

    if path.is_absolute():
        return str(path)

    return str((BASE_DIR / path).resolve())


MONOPRIX_URL = os.getenv(
    "MONOPRIX_URL",
    "https://client.monoprix.fr/monoprix-shopping/tickets",
)

CDP_HOST = os.getenv("CDP_HOST", "localhost")
CDP_PORT = int(os.getenv("CDP_PORT", "9222"))
CDP_URL = os.getenv("CDP_URL", f"http://{CDP_HOST}:{CDP_PORT}")

OUT_DIR = Path(resolve_local_path(os.getenv("OUT_DIR", "pdfs")))

AUTO_START_CHROME = os.getenv("AUTO_START_CHROME", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

CHROME_PATH = os.getenv(
    "CHROME_PATH",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
)

CHROME_USER_DATA_DIR = resolve_local_path(
    os.getenv("CHROME_USER_DATA_DIR", ".chrome-profile")
)

SCROLL_STABLE_ROUNDS = int(os.getenv("SCROLL_STABLE_ROUNDS", "5"))
SCROLL_WAIT_MS = int(os.getenv("SCROLL_WAIT_MS", "1800"))
CLICK_TIMEOUT_MS = int(os.getenv("CLICK_TIMEOUT_MS", "7000"))
PAGE_TIMEOUT_MS = int(os.getenv("PAGE_TIMEOUT_MS", "90000"))
CHROME_START_TIMEOUT_SECONDS = int(os.getenv("CHROME_START_TIMEOUT_SECONDS", "30"))


FRENCH_MONTHS = {
    "janvier": "01",
    "février": "02",
    "fevrier": "02",
    "mars": "03",
    "avril": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07",
    "août": "08",
    "aout": "08",
    "septembre": "09",
    "octobre": "10",
    "novembre": "11",
    "décembre": "12",
    "decembre": "12",
}


def is_cdp_available() -> bool:
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def start_chrome_if_needed() -> None:
    if is_cdp_available():
        print(f"Chrome DevTools already available at {CDP_URL}")
        return

    if not AUTO_START_CHROME:
        raise RuntimeError(
            f"Chrome DevTools is not available at {CDP_URL}. "
            "Start Chrome manually or set AUTO_START_CHROME=true in .env."
        )

    chrome_exe = Path(CHROME_PATH)

    if not chrome_exe.exists():
        raise RuntimeError(
            f"Chrome was not found at: {CHROME_PATH}\n"
            "Edit CHROME_PATH in .env."
        )

    Path(CHROME_USER_DATA_DIR).mkdir(parents=True, exist_ok=True)

    print("Starting automation Chrome...")
    print(f"Chrome path: {CHROME_PATH}")
    print(f"Chrome profile: {CHROME_USER_DATA_DIR}")
    print(f"Debug port: {CDP_PORT}")

    subprocess.Popen(
        [
            CHROME_PATH,
            f"--remote-debugging-port={CDP_PORT}",
            "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={CHROME_USER_DATA_DIR}",
            "--no-first-run",
            "--new-window",
            MONOPRIX_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + CHROME_START_TIMEOUT_SECONDS

    while time.time() < deadline:
        if is_cdp_available():
            print(f"Chrome DevTools is available at {CDP_URL}")
            return

        time.sleep(0.5)

    raise RuntimeError(
        f"Chrome started, but DevTools did not become available at {CDP_URL}.\n"
        f"Expected URL: {CDP_URL}/json/version\n"
        f"Chrome profile used: {CHROME_USER_DATA_DIR}"
    )


def safe_filename(name: str) -> str:
    name = unquote(name or "")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)
    name = name.strip().strip(".")
    return name[:180] or "monoprix-ticket.pdf"


def normalize_store_name(store: str) -> str:
    store = " ".join((store or "").split())
    store = store or "Monoprix"
    store = safe_filename(store)
    store = store.replace(" ", "_")
    return store or "Monoprix"


def normalize_amount_for_filename(amount: str) -> str:
    amount = " ".join((amount or "").split())
    amount = amount.replace("€", "")
    amount = amount.replace("EUR", "")
    amount = amount.replace("eur", "")
    amount = amount.strip()
    amount = amount.replace(",", "-")
    amount = amount.replace(".", "-")
    amount = re.sub(r"[^0-9\-]", "", amount)
    return amount or "unknown-amount"


def extract_ticket_data_from_text(row_text: str, index: int) -> dict:
    """
    Extracts:
      - amount: 14,84€
      - store: Monoprix
      - timestamp: 15/05/2026 à 10h52

    Returns filename like:
      2026-05-15_10-52_Monoprix_14-84_EUR.pdf
    """
    text = " ".join((row_text or "").split())

    amount_match = re.search(r"\b(\d+[,.]\d{2})\s*€", text)
    amount_raw = amount_match.group(1) if amount_match else "unknown-amount"
    amount_for_file = normalize_amount_for_filename(amount_raw)

    numeric_datetime = re.search(
        r"\b([0-3]?\d)[/.\-]([01]?\d)[/.\-]((?:20)?\d{2})"
        r"(?:\s*(?:à|a|@)?\s*([0-2]?\d)\s*[hH:]\s*([0-5]\d))?",
        text,
        re.I,
    )

    date_prefix = None

    if numeric_datetime:
        day = numeric_datetime.group(1).zfill(2)
        month = numeric_datetime.group(2).zfill(2)
        year = numeric_datetime.group(3)

        if len(year) == 2:
            year = "20" + year

        hour = numeric_datetime.group(4)
        minute = numeric_datetime.group(5)

        if hour and minute:
            date_prefix = f"{year}-{month}-{day}_{hour.zfill(2)}-{minute.zfill(2)}"
        else:
            date_prefix = f"{year}-{month}-{day}"

    if date_prefix is None:
        written = re.search(
            r"\b(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\s*"
            r"([0-3]?\d)\s+"
            r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)"
            r"\s+((?:20)?\d{2})"
            r"(?:\s*(?:à|a|@)?\s*([0-2]?\d)\s*[hH:]\s*([0-5]\d))?",
            text,
            re.I,
        )

        if written:
            day = written.group(1).zfill(2)
            month = FRENCH_MONTHS[written.group(2).lower()]
            year = written.group(3)

            if len(year) == 2:
                year = "20" + year

            hour = written.group(4)
            minute = written.group(5)

            if hour and minute:
                date_prefix = f"{year}-{month}-{day}_{hour.zfill(2)}-{minute.zfill(2)}"
            else:
                date_prefix = f"{year}-{month}-{day}"

    if date_prefix is None:
        date_prefix = f"unknown-date-item-{index + 1:03}"

    # Store extraction:
    # Prefer a line containing Monoprix. If there are variants like "Monoprix Montparnasse",
    # this keeps the visible store text.
    lines = [line.strip() for line in (row_text or "").splitlines() if line.strip()]
    store_raw = "Monoprix"

    for line in lines:
        if "monoprix" in line.lower():
            store_raw = line
            break

    store_for_file = normalize_store_name(store_raw)

    filename = safe_filename(f"{date_prefix}_{store_for_file}_{amount_for_file}_EUR.pdf")

    return {
        "row_text": row_text,
        "date_prefix": date_prefix,
        "store": store_raw,
        "amount": amount_raw,
        "filename": filename,
    }


async def find_voir_buttons(page):
    locator = page.get_by_text("Voir", exact=True)
    count = await locator.count()

    if count > 0:
        return locator, count

    locator = page.locator("a:has-text('Voir'), button:has-text('Voir')")
    count = await locator.count()

    return locator, count


async def accept_cookies_if_present(page) -> None:
    """
    Best-effort cookie popup handling.
    It tries common French/English accept button texts.
    If nothing is present, it does nothing.
    """
    texts = [
        "Tout accepter",
        "Accepter tout",
        "J'accepte",
        "J’accepte",
        "Accepter",
        "OK",
        "Accept all",
        "Accept",
    ]

    for text in texts:
        try:
            locator = page.get_by_text(text, exact=True)
            if await locator.count() > 0:
                first = locator.first
                if await first.is_visible(timeout=1000):
                    print(f"Cookie popup: clicking '{text}'")
                    await first.click(timeout=3000)
                    await page.wait_for_timeout(1000)
                    return
        except Exception:
            pass

    # Fallback for common OneTrust-style buttons.
    selectors = [
        "#onetrust-accept-btn-handler",
        "button[id*='accept']",
        "button[class*='accept']",
        "button:has-text('Tout accepter')",
        "button:has-text('Accepter')",
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector)
            if await locator.count() > 0:
                first = locator.first
                if await first.is_visible(timeout=1000):
                    print(f"Cookie popup: clicking selector {selector}")
                    await first.click(timeout=3000)
                    await page.wait_for_timeout(1000)
                    return
        except Exception:
            pass


async def get_ticket_row_text(button, index: int) -> str:
    """
    Finds text visually aligned with this specific Voir button.
    The Monoprix row usually has:
      amount
      store
      date/time
      Voir
    """
    result = await button.evaluate(
        """
        (btn) => {
            const btnRect = btn.getBoundingClientRect();

            const dateRegex =
                /\\b\\d{1,2}[/.\\-]\\d{1,2}[/.\\-](?:20)?\\d{2}\\s*(?:à|a|@)?\\s*\\d{1,2}\\s*[hH:]\\s*\\d{2}\\b|(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\\s*\\b\\d{1,2}\\s+(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\\s+20\\d{2}\\b/i;

            const amountRegex = /\\b\\d+[,.]\\d{2}\\s*€/;

            const elements = Array.from(document.querySelectorAll("body *"));
            const candidates = [];

            for (const el of elements) {
                if (el === btn) continue;

                const style = window.getComputedStyle(el);
                if (style.visibility === "hidden" || style.display === "none") continue;

                const text = (el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim();
                if (!text) continue;

                const hasDate = dateRegex.test(text);
                const hasAmount = amountRegex.test(text);
                const hasStore = /monoprix/i.test(text);

                if (!hasDate && !hasAmount && !hasStore) continue;

                // Avoid giant containers containing the whole ticket list.
                if (text.length > 300) continue;

                const rect = el.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;

                const centerY = rect.top + rect.height / 2;
                const btnCenterY = btnRect.top + btnRect.height / 2;

                const yDistance = Math.abs(centerY - btnCenterY);
                const sameRow = yDistance < 90;

                if (!sameRow) continue;

                const isLeft = rect.right <= btnRect.left + 80;
                const xDistance = isLeft
                    ? Math.abs(btnRect.left - rect.right)
                    : Math.abs(rect.left - btnRect.left) + 500;

                let bonus = 0;
                if (hasDate) bonus -= 1000;
                if (hasAmount) bonus -= 300;
                if (hasStore) bonus -= 300;

                const score = yDistance * 10 + xDistance + text.length * 0.2 + bonus;

                candidates.push({
                    text,
                    score,
                    hasDate,
                    hasAmount,
                    hasStore,
                    yDistance,
                    xDistance
                });
            }

            candidates.sort((a, b) => a.score - b.score);

            // Try to find a compact container that has date + amount + Monoprix.
            const full = candidates.find(c => c.hasDate && c.hasAmount && c.hasStore);
            if (full) return full;

            // Otherwise combine same-row candidates.
            const sameRowTexts = candidates
                .slice(0, 10)
                .map(c => c.text)
                .filter(Boolean);

            if (sameRowTexts.length > 0) {
                return {
                    text: [...new Set(sameRowTexts)].join("\\n"),
                    score: 99998,
                    combined: true
                };
            }

            // Ancestor fallback.
            let node = btn;
            for (let depth = 0; depth < 8 && node; depth++) {
                node = node.parentElement;
                if (!node) break;

                const text = (node.innerText || node.textContent || "").trim();
                const normalized = text.replace(/\\s+/g, " ").trim();

                if (!normalized || normalized.length > 500) continue;

                if (dateRegex.test(normalized) || amountRegex.test(normalized)) {
                    return {
                        text,
                        score: 999999,
                        fallback: true
                    };
                }
            }

            return {
                text: "",
                score: null,
                fallback: true
            };
        }
        """
    )

    raw_text = result.get("text", "") if result else ""

    print("Ticket row text:")
    print(raw_text[:500].replace("\n", " | ") if raw_text else "(none found)")

    return raw_text


async def get_ticket_data(button, index: int) -> dict:
    row_text = await get_ticket_row_text(button, index)
    data = extract_ticket_data_from_text(row_text, index)

    print(f"Extracted filename: {data['filename']}")
    return data


async def scroll_to_bottom(page):
    stable_rounds = 0
    last_height = -1
    last_voir_count = -1

    while stable_rounds < SCROLL_STABLE_ROUNDS:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(SCROLL_WAIT_MS)

        await accept_cookies_if_present(page)

        height = await page.evaluate("document.body.scrollHeight")
        _, voir_count = await find_voir_buttons(page)

        print(f"Scrolling... found {voir_count} Voir links, page height {height}")

        if height == last_height and voir_count == last_voir_count:
            stable_rounds += 1
        else:
            stable_rounds = 0

        last_height = height
        last_voir_count = voir_count

    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(700)


async def close_extra_pages(context, keep_page):
    for p in context.pages:
        if p != keep_page:
            try:
                await p.close()
            except Exception:
                pass


async def save_pdf_response(response, target_path: Path) -> bool:
    headers = response.headers
    content_type = headers.get("content-type", "").lower()

    if "pdf" not in content_type:
        return False

    body = await response.body()
    target_path.write_bytes(body)

    print(f"Saved PDF response: {target_path}")
    return True


async def click_and_capture_pdf(page, context, button, target_path: Path) -> bool:
    await button.scroll_into_view_if_needed()
    await page.wait_for_timeout(700)

    # Case 1: normal browser download.
    try:
        async with page.expect_download(timeout=CLICK_TIMEOUT_MS) as download_info:
            await button.click()

        download = await download_info.value
        await download.save_as(target_path)

        print(f"Saved download: {target_path}")
        return True

    except PlaywrightTimeoutError:
        pass

    # Case 2: direct PDF network response.
    try:
        async with page.expect_response(
            lambda r: "pdf" in r.headers.get("content-type", "").lower(),
            timeout=CLICK_TIMEOUT_MS,
        ) as response_info:
            await button.click()

        response = await response_info.value
        if await save_pdf_response(response, target_path):
            return True

    except PlaywrightTimeoutError:
        pass

    # Case 3: PDF opens in popup/new tab.
    try:
        async with page.expect_popup(timeout=CLICK_TIMEOUT_MS) as popup_info:
            await button.click()

        popup = await popup_info.value
        await popup.wait_for_load_state("domcontentloaded", timeout=10000)

        popup_url = popup.url

        if popup_url and popup_url != "about:blank":
            response = await context.request.get(popup_url)
            content_type = response.headers.get("content-type", "").lower()

            if "pdf" in content_type:
                target_path.write_bytes(await response.body())

                print(f"Saved popup PDF: {target_path}")
                await popup.close()
                return True

            print(f"Popup was not a PDF: {popup_url}")

        await popup.close()

    except PlaywrightTimeoutError:
        pass

    return False


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    start_chrome_if_needed()

    async with async_playwright() as p:
        print(f"Connecting to Chrome at {CDP_URL}...")
        browser = await p.chromium.connect_over_cdp(CDP_URL)

        if not browser.contexts:
            raise RuntimeError("Connected to Chrome, but no browser context was found.")

        context = browser.contexts[0]

        page = None
        for candidate in context.pages:
            if "monoprix.fr" in candidate.url:
                page = candidate
                break

        if page is None:
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(MONOPRIX_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)

        await accept_cookies_if_present(page)

        print()
        print("Use the opened Chrome window to log in to Monoprix if needed.")
        print("Make sure the tickets page is visible.")
        input("When ready, press Enter here...")

        current_url = page.url
        if "monoprix.fr" not in current_url:
            await page.goto(MONOPRIX_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
            await page.wait_for_timeout(5000)
        else:
            await page.wait_for_timeout(3000)

        await accept_cookies_if_present(page)
        await scroll_to_bottom(page)

        locator, count = await find_voir_buttons(page)
        print()
        print(f'Found {count} "Voir" links/buttons.')

        if count == 0:
            print("No Voir links found. Make sure you are logged in and on the tickets page.")
            await browser.close()
            return

        saved = 0
        skipped = 0
        failed = 0

        for i in range(count):
            print(f"\nProcessing {i + 1}/{count}...")

            locator, fresh_count = await find_voir_buttons(page)

            if i >= fresh_count:
                print(f"Item {i + 1} no longer exists.")
                failed += 1
                continue

            button = locator.nth(i)
            await button.scroll_into_view_if_needed()
            await page.wait_for_timeout(500)

            ticket_data = await get_ticket_data(button, i)
            target_path = OUT_DIR / ticket_data["filename"]

            if target_path.exists():
                print(f"Already exists, skipping without clicking: {target_path}")
                skipped += 1
                continue

            ok = await click_and_capture_pdf(page, context, button, target_path)

            if ok:
                saved += 1
            else:
                failed += 1
                print(f"Could not capture PDF for item {i + 1}.")

            await close_extra_pages(context, page)
            await page.wait_for_timeout(1000)

        print()
        print(f"Done. Saved: {saved}. Skipped: {skipped}. Failed: {failed}.")
        print(f"PDF folder: {OUT_DIR.resolve()}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())