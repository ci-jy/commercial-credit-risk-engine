"""End-to-end CLI runs on recorded fixtures (offline)."""

import pandas as pd

from credit_engine.cli import main
from credit_engine.memo import analyze
from credit_engine.edgar import load_fixture
from credit_engine.prices import load_prices
from credit_engine.spreading import spread_companyfacts


def test_memo_sample_borrower(tmp_path):
    assert main(["memo", "--fixture", "sample_borrower", "--out", str(tmp_path), "--no-recalc"]) == 0
    text = (tmp_path / "sample_borrower_memo.md").read_text()
    for section in ("## 1. Summary", "## 2. Financial spread", "## 3. Credit ratios", "## 4. Covenant compliance",
                    "## 5. Stress tests", "## 6. Probability of default", "Risk grade"):
        assert section in text
    assert "| Debt / EBITDA (x) | " in text and "3.00x" in text
    assert "breaks at -14.3%" in text  # leverage under EBITDA shock, 1/7
    assert (tmp_path / "sample_borrower_spread.xlsx").exists()


def test_memo_public_company_has_merton(tmp_path):
    s = spread_companyfacts(load_fixture("mattel"))
    a = analyze("mattel", s, prices=load_prices("MAT"), floating_share=0.1)
    assert a.merton is not None and a.merton.converged
    assert a.merton_inputs["E"] > 0 and 0 < a.merton_inputs["sigma_E"] < 2
    assert 0 <= a.final_pd <= 1 and 1 <= a.grade[0] <= 10


def test_benchmark_offline_quick(tmp_path, capsys):
    assert main(["benchmark", "--offline-fixtures", "--quick", "--out", str(tmp_path)]) == 0
    m = pd.read_csv(tmp_path / "benchmark_metrics.csv")
    for model in ("scorecard", "altman_z", "gbm", "gbm_spread"):
        sub = m[m.model == model].set_index("metric")
        assert set(sub.index) == {"auc", "ks", "brier", "ece"}
        assert (sub.ci_low <= sub.estimate + 1e-12).all() and (sub.estimate <= sub.ci_high + 1e-12).all()
    auc = m[m.metric == "auc"].set_index("model").estimate
    assert auc["scorecard"] > 0.7 and auc["altman_z"] > 0.6
    assert (tmp_path / "benchmark.md").read_text().count("Decile") == 4
    assert "WoE scorecard" in capsys.readouterr().out
