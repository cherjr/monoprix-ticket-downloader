import unittest
import sys
import types
from unittest import mock


dotenv = types.ModuleType("dotenv")
dotenv.load_dotenv = lambda: None
sys.modules["dotenv"] = dotenv

playwright = types.ModuleType("playwright")
playwright_async_api = types.ModuleType("playwright.async_api")
playwright_async_api.async_playwright = None
playwright_async_api.TimeoutError = TimeoutError
playwright_async_api.Error = Exception
sys.modules["playwright"] = playwright
sys.modules["playwright.async_api"] = playwright_async_api

import download_monoprix


class StartChromeIfNeededTest(unittest.TestCase):
    def test_non_windows_browser_on_cdp_port_raises_without_launching(self):
        user_agent = "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0 Safari/537.36"

        with mock.patch.object(download_monoprix, "is_cdp_available", return_value=True), \
                mock.patch.object(download_monoprix, "get_cdp_user_agent", return_value=user_agent), \
                mock.patch.object(download_monoprix.subprocess, "Popen") as popen:
            with self.assertRaises(RuntimeError) as context:
                download_monoprix.start_chrome_if_needed()

        self.assertIn("non-Windows browser", str(context.exception))
        self.assertIn(user_agent, str(context.exception))
        popen.assert_not_called()

    def test_windows_browser_on_cdp_port_is_reused(self):
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"

        with mock.patch.object(download_monoprix, "is_cdp_available", return_value=True), \
                mock.patch.object(download_monoprix, "get_cdp_user_agent", return_value=user_agent), \
                mock.patch.object(download_monoprix.subprocess, "Popen") as popen:
            self.assertIsNone(download_monoprix.start_chrome_if_needed())

        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
