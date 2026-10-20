"""Layout regression tests for the responsive desktop shell."""
import json
import unittest
from pathlib import Path

import app


class FakeWidget:
    def __init__(self):
        self.grid_options = {}

    def grid(self, **options):
        self.grid_options = options


class FakeContainer:
    def __init__(self, width):
        self.width = width
        self.configure_callback = None
        self.columns = {}
        self.rows = {}

    def winfo_width(self):
        return self.width

    def bind(self, event_name, callback, add=None):
        self.configure_callback = callback

    def after_idle(self, callback):
        callback()

    def grid_columnconfigure(self, column, **options):
        self.columns[column] = options

    def grid_rowconfigure(self, row, **options):
        self.rows[row] = options

    def resize(self, width):
        self.width = width
        self.configure_callback()


class ResponsiveLayoutTests(unittest.TestCase):
    def test_cards_reflow_from_three_to_two_to_one_column(self):
        container = FakeContainer(900)
        widgets = [FakeWidget() for _ in range(5)]

        app.bind_responsive_grid(container, widgets, min_column_width=250, max_columns=3)
        self.assertEqual([widget.grid_options["column"] for widget in widgets], [0, 1, 2, 0, 1])
        self.assertEqual([widget.grid_options["row"] for widget in widgets], [0, 0, 0, 1, 1])

        container.resize(520)
        self.assertEqual([widget.grid_options["column"] for widget in widgets], [0, 1, 0, 1, 0])
        self.assertEqual([widget.grid_options["row"] for widget in widgets], [0, 0, 1, 1, 2])

        container.resize(210)
        self.assertEqual([widget.grid_options["column"] for widget in widgets], [0, 0, 0, 0, 0])
        self.assertEqual([widget.grid_options["row"] for widget in widgets], [0, 1, 2, 3, 4])

    def test_brand_tokens_use_midnight_navy_and_signal_yellow(self):
        self.assertEqual(app.COLORS["canvas"], "#061327")
        self.assertEqual(app.COLORS["clay"], "#FFC629")
        self.assertEqual(app.COLORS["ink"], "#EDF4FF")
        self.assertEqual(app.APP_BRAND, "Invent-SSH")

        theme = json.loads((Path(__file__).resolve().parents[1] / "brand" / "theme.json").read_text(encoding="utf-8"))
        self.assertIn("CTkFont", theme)
        self.assertEqual(theme["CTkButton"]["fg_color"], "#FFC629")
        self.assertEqual(theme["CTkButton"]["text_color"], "#07172D")

    def test_brand_assets_are_platform_ready(self):
        root = Path(__file__).resolve().parents[1]
        svg = (root / "brand" / "logo-mark.svg").read_text(encoding="utf-8")
        self.assertIn("penguin mark", svg)
        self.assertIn("#FFC629", svg)
        self.assertTrue((root / "brand" / "invent-ssh-mark-64.png").is_file())
        self.assertTrue((root / "brand" / "invent-ssh-mark-128.png").is_file())
        self.assertTrue((root / "app.ico").is_file())


if __name__ == "__main__":
    unittest.main()
