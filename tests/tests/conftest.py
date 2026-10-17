import sys
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def fake_loggers():
    return Mock(name="error_logger"), Mock(name="results_logger")


@pytest.fixture
def minimal_advanced_df():
    return pd.DataFrame(columns=["link"])


@pytest.fixture
def fixed_now_values():
    return [
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T00:00:01+00:00",
        "2026-01-01T00:00:02+00:00",
        "2026-01-01T00:00:03+00:00",
    ]
