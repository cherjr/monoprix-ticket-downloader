import unittest
import sys
import types


dotenv = types.ModuleType("dotenv")
dotenv.load_dotenv = lambda: None
sys.modules["dotenv"] = dotenv

playwright = types.ModuleType("playwright")
playwright_async_api = types.ModuleType("playwright.async_api")
playwright_async_api.async_playwright = None
playwright_async_api.TimeoutError = TimeoutError
sys.modules["playwright"] = playwright
sys.modules["playwright.async_api"] = playwright_async_api

from download_monoprix import extract_ticket_data_from_text


class ExtractTicketDataTest(unittest.TestCase):
    def test_store_name_stops_before_next_ticket_in_combined_text(self):
        cases = [
            (
                "Avril 2022 Coupe-file 15,09€ MONOPRIX MONTPARNASSE "
                "03/04/2022 à 13h13 Voir Coupe-file 13,30€ MONOP LUXEMBOURG "
                "02/04/2022 à 21h22 Voir Coupe-file 59,99€ MONOPRIX",
                "15,09",
                "2022-04-03_13-13",
                "MONOPRIX MONTPARNASSE",
                "2022-04-03_13-13_MONOPRIX_MONTPARNASSE_15-09_EUR.pdf",
            ),
            (
                "Février 2023 Coupe-file 42,36€ MONOPRIX MONTPARNASSE "
                "21/02/2023 à 16h09 Voir Coupe-file 8,67€ MONOP LUXEMBOURG "
                "19/02/2023 à 15h27 Voir Coupe-file 4,22€ MONOP LUXEMBOURG",
                "42,36",
                "2023-02-21_16-09",
                "MONOPRIX MONTPARNASSE",
                "2023-02-21_16-09_MONOPRIX_MONTPARNASSE_42-36_EUR.pdf",
            ),
            (
                "Septembre 2023 Coupe-file 3,59€ MONOPRIX MONTPARNASSE "
                "20/09/2023 à 19h15 Voir Coupe-file 16,49€ MONOPRIX DRAGON "
                "18/09/2023 à 19h46 Voir Coupe-file 65,03€ MONOPRIX",
                "3,59",
                "2023-09-20_19-15",
                "MONOPRIX MONTPARNASSE",
                "2023-09-20_19-15_MONOPRIX_MONTPARNASSE_3-59_EUR.pdf",
            ),
            (
                "Mars 2024 Coupe-file 6,02€ MONOPRIX RUE DU BAC "
                "25/03/2024 à 15h47 Voir Coupe-file 8,78€ MONOPRIX DRAGON "
                "20/03/2024 à 13h30 Voir Coupe-file 10,12€ MONOP LUXEMBOURG",
                "6,02",
                "2024-03-25_15-47",
                "MONOPRIX RUE DU BAC",
                "2024-03-25_15-47_MONOPRIX_RUE_DU_BAC_6-02_EUR.pdf",
            ),
            (
                "Avril 2024 Coupe-file 13,00€ MONOPRIX DRAGON "
                "26/04/2024 à 12h45 Voir Coupe-file 14,15€ MONOPRIX DRAGON "
                "23/04/2024 à 17h55 Voir Coupe-file 22,54€ MONOPRIX DRAGON",
                "13,00",
                "2024-04-26_12-45",
                "MONOPRIX DRAGON",
                "2024-04-26_12-45_MONOPRIX_DRAGON_13-00_EUR.pdf",
            ),
            (
                "Mai 2024 Coupe-file 15,24€ MONOPRIX DRAGON "
                "24/05/2024 à 10h14 Voir Coupe-file 24,02€ MONOPRIX DRAGON "
                "13/05/2024 à 18h14 Voir Coupe-file 12,57€ MONOPRIX DRAGON",
                "15,24",
                "2024-05-24_10-14",
                "MONOPRIX DRAGON",
                "2024-05-24_10-14_MONOPRIX_DRAGON_15-24_EUR.pdf",
            ),
            (
                "Juin 2026 Caisse 50,42€ Monoprix "
                "13/06/2026 à 11h36 Voir Caisse 59,01€ Monoprix "
                "06/06/2026 à 16h04 Voir Caisse 10,06€ Monoprix",
                "50,42",
                "2026-06-13_11-36",
                "Monoprix",
                "2026-06-13_11-36_Monoprix_50-42_EUR.pdf",
            ),
        ]

        for row_text, amount, date_prefix, store, filename in cases:
            with self.subTest(filename=filename):
                data = extract_ticket_data_from_text(row_text, 0)

                self.assertEqual(data["amount"], amount)
                self.assertEqual(data["date_prefix"], date_prefix)
                self.assertEqual(data["store"], store)
                self.assertEqual(data["filename"], filename)


if __name__ == "__main__":
    unittest.main()
