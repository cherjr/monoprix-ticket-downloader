# Monoprix Ticket Downloader

Downloads receipt PDFs from the Monoprix tickets page:

https://client.monoprix.fr/monoprix-shopping/tickets

The script opens or connects to a separate Chrome automation profile, lets you log in manually, scrolls the page to load all ticket batches, clicks every `Voir` button, and saves the generated PDFs.

PDF filenames are based on the date shown on the Monoprix page.
Existing PDFs are skipped. The script does not overwrite existing files and does not create duplicates.

## Requirements

- Windows
- Python 3
- Google Chrome
- A Monoprix account

## Project setup

Install dependencies:

```powershell
python -m pip install --user -r requirements.txt
```

If you have not created `requirements.txt` yet, install directly:

```powershell
python -m pip install --user playwright python-dotenv
```

You do not need to run:

```powershell
python -m playwright install chromium
```

The script uses your existing Windows Chrome, not Playwright's bundled Chromium.

## Files

Expected project structure:

```text
monoprix-ticket-downloader/
  download_monoprix.py
  requirements.txt
  .env.example
  .env
  .gitignore
  README.md
```

Do not commit `.env` or downloaded PDFs.

## Configuration

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` if needed.

Default `.env` values:

```dotenv
MONOPRIX_URL=https://client.monoprix.fr/monoprix-shopping/tickets

CDP_HOST=localhost
CDP_PORT=9222
CDP_URL=http://localhost:9222

OUT_DIR=pdfs

AUTO_START_CHROME=true
CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
CHROME_USER_DATA_DIR=.chrome-profile
CHROME_START_TIMEOUT_SECONDS=30

SCROLL_STABLE_ROUNDS=5
SCROLL_WAIT_MS=1800

CLICK_TIMEOUT_MS=7000
PAGE_TIMEOUT_MS=90000
```

### Important settings

#### `AUTO_START_CHROME`

```dotenv
AUTO_START_CHROME=true
```

When enabled, the Python script starts Chrome automatically using the configured automation profile.

#### `CHROME_USER_DATA_DIR`

```dotenv
CHROME_USER_DATA_DIR=.chrome-profile
```

This is a separate Chrome profile just for automation. It keeps your normal Chrome profiles untouched.

You only need to log in to Monoprix once in this automation profile. Future runs should reuse the saved login.

#### `OUT_DIR`

```dotenv
OUT_DIR=pdfs
```

PDFs are saved into this folder.

## Running the downloader

Run:

```powershell
python .\download_monoprix.py
```

When Chrome opens:

1. Log in to Monoprix if needed.
2. Make sure the tickets page is visible.
3. Go back to PowerShell.
4. Press Enter.

The script will then:

1. Scroll to the bottom repeatedly to load all ticket batches.
2. Count all `Voir` links/buttons.
3. Click each one.
4. Save each PDF.
5. Skip PDFs that already exist.
6. Close the automation Chrome window before exiting.

## Manual Chrome start option

The script can start Chrome automatically, but you can also start it manually.

Run this in PowerShell:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="$env:USERPROFILE\monoprix-automation-chrome"
```

Then verify Chrome DevTools is reachable:

```powershell
Invoke-WebRequest http://localhost:9222/json/version
```

You should see:

```text
StatusCode : 200
```

Then run:

```powershell
python .\download_monoprix.py
```

If you start Chrome manually, you can set this in `.env`:

```dotenv
AUTO_START_CHROME=false
```

## Output

By default, PDFs are saved into:

```text
pdfs/
```

Example filenames:

```text
2026-05-15_10-52_Monoprix_14-84_EUR.pdf
2026-05-10_19-03_Monoprix_37-20_EUR.pdf
2026-05-02_12-18_Monoprix_8-95_EUR.pdf
```

## How skipping works

Before clicking a `Voir` button, the script reads the ticket row and builds the
target filename from:

- date and time
- store name
- amount

It then checks whether that exact filename already exists in `OUT_DIR`.

If the file exists, the script does not click `Voir` and does not download the
PDF again. It prints:

```text
Already exists, skipping without clicking: pdfs\2026-05-15_10-52_Monoprix_14-84_EUR.pdf
```

The duplicate check is filename-based. It does not compare PDF contents or file
hashes.

## Git setup

Initialize Git:

```powershell
git init
git add download_monoprix.py requirements.txt README.md .gitignore .env.example
git commit -m "Initial Monoprix ticket downloader"
```

The `.gitignore` excludes:

- `.env`
- `pdfs/`
- downloaded PDFs
- Python cache files
- editor settings

## Troubleshooting

### `ModuleNotFoundError: No module named 'playwright'`

Install dependencies:

```powershell
python -m pip install --user -r requirements.txt
```

Or:

```powershell
python -m pip install --user playwright python-dotenv
```

### Chrome does not open

Check `CHROME_PATH` in `.env`.

Default path:

```dotenv
CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
```

If Chrome is installed elsewhere, update that value.

### Chrome opens but the script cannot connect

Check:

```powershell
Invoke-WebRequest http://localhost:9222/json/version
```

If that fails, close the automation Chrome window and run again.

### The script finds zero `Voir` buttons

Make sure:

1. You are logged in.
2. The Monoprix tickets page is visible.
3. The page has fully loaded.
4. You pressed Enter in PowerShell only after the tickets page was ready.

### The script misses older tickets

Increase these values in `.env`:

```dotenv
SCROLL_STABLE_ROUNDS=8
SCROLL_WAIT_MS=2500
```

Then rerun.

### The script downloads some PDFs but fails others

Increase:

```dotenv
CLICK_TIMEOUT_MS=12000
```

Then rerun. Existing downloaded files will be skipped.
