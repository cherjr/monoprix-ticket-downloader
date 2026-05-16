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

MONOPRIX_URL = os.getenv(
    "MONOPRIX_URL",
    "https://client.monoprix.fr/monoprix-shopping/tickets",
)

CDP_HOST = os.getenv("CDP_HOST", "localhost")
CDP_PORT = int(os.getenv("CDP_PORT", "9222"))
CDP_URL = os.getenv("CDP_URL", f"http://{CDP_HOST}:{CDP_PORT}")

OUT_DIR = Path(os.getenv("OUT_DIR", "pdfs"))

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

CHROME_USER_DATA_DIR = os.getenv(
    "CHROME_USER_DATA_DIR",
    str(Path.home() / "monoprix-automation-chrome"),
)

SCROLL_STABLE_ROUNDS = int(os.getenv("SCROLL_STABLE_ROUNDS", "5"))
SCROLL_WAIT_MS = int(os.getenv("SCROLL_WAIT_MS", "1800"))
CLICK_TIMEOUT_MS = int(os.getenv("CLICK_TIMEOUT_MS", "7000"))
PAGE_TIMEOUT_MS = int(os.getenv("PAGE_TIMEOUT_MS", "90000"))
CHROME_START_TIMEOUT_SECONDS = int(os.getenv("CHROME_START_TIMEOUT_SECONDS", "20"))


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

    print("Starting automation Chrome...")
    print(f"Chrome path: {CHROME_PATH}")
    print(f"Chrome profile: {CHROME_USER_DATA_DIR}")
    print(f"Debug port: {CDP_PORT}")

    subprocess.Popen(
        [
            CHROME_PATH,
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={CHROME_USER_DATA_DIR}",
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
        f"Chrome started, but DevTools did not become available at {CDP_URL}."
    )


def safe_filename(name: str) -> str:
    name = unquote(name or "")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)
    name = name.strip().strip(".")
    return name[:180] or "monoprix-ticket.pdf"


def normalize_french_date_text(text: str, index: int) -> str:
    text = " ".join((text or "").split()).lower()

    numeric = re.search(
        r"\b([0-3]?\d)[/.\-]([01]?\d)[/.\-]((?:20)?\d{2})"
        r"(?:\s+([0-2]?\d)[:hH]([0-5]\d))?",
        text,
    )

    if numeric:
        day = numeric.group(1).zfill(2)
        month = numeric.group(2).zfill(2)
        year = numeric.group(3)

        if len(year) == 2:
            year = "20" + year

        hour = numeric.group(4)
        minute = numeric.group(5)

        if hour and minute:
            return f"{year}-{month}-{day}_{hour.zfill(2)}-{minute.zfill(2)}"

        return f"{year}-{month}-{day}"

    written = re.search(
        r"\b(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\s*"
        r"([0-3]?\d)\s+"
        r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)"
        r"\s+((?:20)?\d{2})"
        r"(?:\s+([0-2]?\d)[:hH]([0-5]\d))?",
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
            return f"{year}-{month}-{day}_{hour.zfill(2)}-{minute.zfill(2)}"

        return f"{year}-{month}-{day}"

    return f"unknown-date-item-{index + 1:03}"


def filename_from_headers(headers: dict, fallback: str) -> str:
    disposition = headers.get("content-disposition", "")

    match = re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.I)
    if match:
        return safe_filename(match.group(1))

    match = re.search(r'filename="?([^";]+)"?', disposition, re.I)
    if match:
        return safe_filename(match.group(1))

    return safe_filename(fallback)


def final_pdf_filename(ticket_date_prefix: str, original_filename: str, index: int) -> str:
    original_filename = safe_filename(original_filename)

    if original_filename.lower().endswith(".pdf"):
        stem = original_filename[:-4]
    else:
        stem = original_filename

    return safe_filename(f"{ticket_date_prefix}-item-{index + 1:03}-{stem}.pdf")


def target_path_or_none(filename: str) -> Path | None:
    path = OUT_DIR / filename

    if path.exists():
        print(f"Already exists, skipping: {path}")
        return None

    return path


async def find_voir_buttons(page):
    locator = page.get_by_text("Voir", exact=True)
    count = await locator.count()

    if count > 0:
        return locator, count

    locator = page.locator("a:has-text('Voir'), button:has-text('Voir')")
    count = await locator.count()

    return locator, count


async def get_ticket_date_prefix(button, index: int) -> str:
    result = await button.evaluate(
        """
        (btn) => {
            const btnRect = btn.getBoundingClientRect();

            const dateRegex =
                /(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\\s*\\b\\d{1,2}\\s+(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\\s+20\\d{2}\\b|\\b\\d{1,2}[/.\\-]\\d{1,2}[/.\\-](?:20)?\\d{2}\\b/i;

            const elements = Array.from(document.querySelectorAll("body *"));
            const candidates = [];

            for (const el of elements) {
                if (el === btn) continue;

                const style = window.getComputedStyle(el);
                if (style.visibility === "hidden" || style.display === "none") continue;

                const text = (el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim();
                if (!text) continue;
                if (!dateRegex.test(text)) continue;

                // Avoid giant containers containing the whole ticket list.
                if (text.length > 220) continue;

                const rect = el.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;

                const centerY = rect.top + rect.height / 2;
                const btnCenterY = btnRect.top + btnRect.height / 2;

                const yDistance = Math.abs(centerY - btnCenterY);
                const sameRow = yDistance < 80;

                // In the Monoprix layout, the date is usually left of "Voir".
                const isLeft = rect.right <= btnRect.left + 40;
                const xDistance = isLeft
                    ? Math.abs(btnRect.left - rect.right)
                    : Math.abs(rect.left - btnRect.left) + 500;

                if (!sameRow) continue;

                const score = yDistance * 10 + xDistance + text.length * 0.5;

                candidates.push({
                    text,
                    score,
                    yDistance,
                    xDistance
                });
            }

            candidates.sort((a, b) => a.score - b.score);

            if (candidates.length > 0) {
                return candidates[0];
            }

            // Fallback: search nearby ancestors but avoid huge containers.
            let node = btn;
            for (let depth = 0; depth < 8 && node; depth++) {
                node = node.parentElement;
                if (!node) break;

                const text = (node.innerText || node.textContent || "").replace(/\\s+/g, " ").trim();
                if (!text || text.length > 350) continue;

                if (dateRegex.test(text)) {
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
    prefix = normalize_french_date_text(raw_text, index)

    print("Date candidate near this Voir button:")
    print(raw_text[:300] if raw_text else "(none found)")
    print(f"Extracted date prefix: {prefix}")

    return prefix


async def scroll_to_bottom(page):
    stable_rounds = 0
    last_height = -1
    last_voir_count = -1

    while stable_rounds < SCROLL_STABLE_ROUNDS:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(SCROLL_WAIT_MS)

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


async def save_pdf_response(response, index: int, ticket_date_prefix: str) -> bool:
    headers = response.headers
    content_type = headers.get("content-type", "").lower()

    if "pdf" not in content_type:
        return False

    fallback = f"monoprix-ticket-{index + 1:03}.pdf"
    original_filename = filename_from_headers(headers, fallback)
    filename = final_pdf_filename(ticket_date_prefix, original_filename, index)

    path = target_path_or_none(filename)
    if path is None:
        return True

    body = await response.body()
    path.write_bytes(body)

    print(f"Saved PDF response: {path}")
    return True


async def click_and_capture_pdf(page, context, button, index: int) -> bool:
    await button.scroll_into_view_if_needed()
    await page.wait_for_timeout(700)

    ticket_date_prefix = await get_ticket_date_prefix(button, index)

    # Case 1: normal browser download.
    try:
        async with page.expect_download(timeout=CLICK_TIMEOUT_MS) as download_info:
            await button.click()

        download = await download_info.value
        original_filename = download.suggested_filename or f"monoprix-ticket-{index + 1:03}.pdf"
        filename = final_pdf_filename(ticket_date_prefix, original_filename, index)

        path = target_path_or_none(filename)
        if path is None:
            return True

        await download.save_as(path)

        print(f"Saved download: {path}")
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
        if await save_pdf_response(response, index, ticket_date_prefix):
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
                fallback = f"monoprix-ticket-{index + 1:03}.pdf"
                original_filename = filename_from_headers(response.headers, fallback)
                filename = final_pdf_filename(ticket_date_prefix, original_filename, index)

                path = target_path_or_none(filename)
                if path is None:
                    await popup.close()
                    return True

                path.write_bytes(await response.body())

                print(f"Saved popup PDF: {path}")
                await popup.close()
                return True

            print(f"Popup was not a PDF: {popup_url}")

        await popup.close()

    except PlaywrightTimeoutError:
        pass

    return False


async def main():
    OUT_DIR.mkdir(exist_ok=True)

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

        await scroll_to_bottom(page)

        locator, count = await find_voir_buttons(page)
        print()
        print(f'Found {count} "Voir" links/buttons.')

        if count == 0:
            print("No Voir links found. Make sure you are logged in and on the tickets page.")
            await browser.close()
            return

        saved_or_skipped = 0
        failed = 0

        for i in range(count):
            print(f"\nProcessing {i + 1}/{count}...")

            locator, fresh_count = await find_voir_buttons(page)

            if i >= fresh_count:
                print(f"Item {i + 1} no longer exists.")
                failed += 1
                continue

            button = locator.nth(i)
            ok = await click_and_capture_pdf(page, context, button, i)

            if ok:
                saved_or_skipped += 1
            else:
                failed += 1
                print(f"Could not capture PDF for item {i + 1}.")

            await close_extra_pages(context, page)
            await page.wait_for_timeout(1000)

        print()
        print(f"Done. Saved or skipped: {saved_or_skipped}. Failed: {failed}.")
        print(f"PDF folder: {OUT_DIR.resolve()}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())