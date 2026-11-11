# AGENTS.md

## Project boundaries

This is a Windows Python/PowerShell browser workflow. `README.md` is the
operator source of truth.

- Project-scoped Python development and validation commands are allowed.
  Do not replace normal shell inspection or file editing with ad hoc Python.
- Treat the Monoprix account, cookies, browser profile, `.env`, receipts, PDFs,
  page captures, and logs as sensitive. Never commit or expose them.
- The dedicated automation profile is an intentional project exception to the
  normal-profile browser default. Do not substitute the user's everyday Chrome
  profile.
- Run or verify the real download workflow in its documented Windows/PowerShell
  environment. Do not assume a Linux browser session proves Windows behavior.
- Inspect the live tickets page before changing selectors or timing assumptions.
- Preserve filename-based duplicate skipping. Never overwrite or delete
  existing receipt PDFs unless the user explicitly requests that exact action.
- Stop only the dedicated automation Chrome instance started by this project;
  never kill unrelated user browsers.
- The focused test entry point is
  `python -m unittest tests/test_extract_ticket_data.py`.
- Do not commit, push, publish, or perform account/browser mutations outside the
  explicitly requested workflow.

