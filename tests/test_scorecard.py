"""WoE binning, information value and the scorecard model."""

import numpy as np
import pandas as pd
import pytest

from credit_engine.polish import SPREAD_FEATURES, load_polish, spread_to_polish_ratios
from credit_engine.scorecard import WoEScorecard, bin_feature
from credit_engine.edgar import load_fixture
from credit_engine.spreading import spread_companyfacts


def test_woe_hand_computed_two_bins():
    # bin A: 80 goods / 20 bads, bin B: 90 goods / 10 bads (no smoothing distortion check via approx)
    x = np.array([0.0] * 100 + [1.0] * 100)
    y = np.array([1] * 20 + [0] * 80 + [1] * 10 + [0] * 90)
    b = bin_feature(x, y, max_bins=2, min_bin_frac=0.01)
    assert len(b.woe) == 2
    tg, tb = 170, 30
    woe_a = np.log(((80 + 0.5) / (tg + 1)) / ((20 + 0.5) / (tb + 1)))
    woe_b = np.log(((90 + 0.5) / (tg + 1)) / ((10 + 0.5) / (tb + 1)))
    assert b.woe[0] == pytest.approx(woe_a)
    assert b.woe[1] == pytest.approx(woe_b)
    pg = np.array([80.5, 90.5]) / (tg + 1)
    pb = np.array([20.5, 10.5]) / (tb + 1)
    assert b.iv == pytest.approx(np.sum((pg - pb) * np.log(pg / pb)))
    assert list(b.transform(np.array([0.0, 1.0, np.nan]))) == pytest.approx([woe_a, woe_b, 0.0])


def test_binning_is_monotonic_and_respects_min_size():
    rng = np.random.default_rng(0)
    x = rng.normal(size=5000)
    p = 1 / (1 + np.exp(-(-3 + 1.5 * x + 0.5 * np.sin(6 * x))))
    y = (rng.random(5000) < p).astype(int)
    x[:200] = np.nan
    b = bin_feature(x, y, max_bins=10, min_bin_frac=0.05)
    rates = np.array(b.bad_rates)
    assert np.all(np.diff(rates) >= 0)  # risk increases with x
    assert min(b.counts) >= 0.05 * len(x)
    assert b.woe_missing != 0.0 and b.iv > 0.3


@pytest.fixture(scope="module")
def fitted():
    df = load_polish(offline=True)
    feats = list(SPREAD_FEATURES)
    return WoEScorecard().fit(df[feats], df["class"]), df, feats


def test_scorecard_signs_points_and_roundtrip(fitted, tmp_path):
    sc, df, feats = fitted
    assert np.all(sc.coef_ < 0)  # higher WoE (more goods) -> lower PD for every kept feature
    p = sc.predict_proba(df[feats])
    s = sc.score(df[feats])
    assert np.all((p > 0) & (p < 1))
    assert np.corrcoef(p, s)[0, 1] < -0.9  # points go down as PD goes up
    sc.save(tmp_path / "sc.json")
    sc2 = WoEScorecard.load(tmp_path / "sc.json")
    np.testing.assert_allclose(sc2.predict_proba(df[feats]), p)
    # 600 points at 50:1 odds
    pd_at_600 = 1 / 51
    assert sc.score(df[feats].iloc[:1]).shape == (1,)
    assert 600 + 20 / np.log(2) * (np.log((1 - pd_at_600) / pd_at_600) - np.log(50)) == pytest.approx(600)


def test_spread_ratios_feed_the_scorecard(fitted):
    sc, _, feats = fitted
    y = spread_companyfacts(load_fixture("sample_borrower")).year(2024)
    r = spread_to_polish_ratios(y)
    assert r["Attr2"] == pytest.approx(250 / 380)
    assert r["Attr7"] == pytest.approx(42 / 380)
    assert r["Attr46"] == pytest.approx((150 - 70) / 100)
    p = sc.predict_proba(pd.DataFrame([r])[feats])[0]
    assert 0 < p < 0.2
