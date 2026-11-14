"""Run every page headlessly with Streamlit's AppTest and fail on any exception."""
import pathlib
import sys

import pytest
from streamlit.testing.v1 import AppTest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PAGES = ["views/00_Home.py", "views/01_Mission_Control.py", "views/02_Planetary_Explorer.py", "views/03_Analog_Discovery_Lab.py",
         "views/04_Scientific_Comparison.py", "views/05_Mission_Engineering.py", "views/06_Field_Campaign_Reports.py", "views/07_AI_Research_Assistant.py"]


@pytest.mark.parametrize("page", PAGES)
def test_page_runs(page):
    at = AppTest.from_file(str(ROOT / page), default_timeout=60).run()
    assert not at.exception, [e.message for e in at.exception]
