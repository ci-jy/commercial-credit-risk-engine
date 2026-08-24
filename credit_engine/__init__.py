"""Commercial credit risk engine: spreading, ratios, covenant stress, PD models and memos."""

from pathlib import Path

__version__ = "0.1.0"

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
MODELS_DIR = REPO_ROOT / "models"
