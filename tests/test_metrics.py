import numpy as np
import pytest

from credit_engine.altman import z_double_prime, zone
from credit_engine.metrics import bootstrap, calibration_table, ece, ks_stat


def test_ks_and_calibration_hand_values():
    y = np.array([0, 0, 0, 1, 0, 1, 1, 1])
    p = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
    # best threshold 0.6: TPR 3/4, FPR 0/4 ... at 0.4: TPR 4/4, FPR 1/4 -> KS 0.75
    assert ks_stat(y, p) == pytest.approx(0.75)
    t = calibration_table(y, p, n_bins=2)
    assert list(t["observed_rate"]) == [0.25, 0.75]
    assert ece(y, p, n_bins=2) == pytest.approx((abs(0.25 - 0.25) + abs(0.65 - 0.75)) / 2)


def test_bootstrap_ci_contains_estimate():
    rng = np.random.default_rng(0)
    y = (rng.random(2000) < 0.1).astype(int)
    p = np.clip(0.1 + 0.2 * (y - 0.1) + rng.normal(0, 0.05, 2000), 0.001, 0.999)
    res = bootstrap(y, {"a": p, "b": rng.random(2000)}, n_boot=100, paired=[("a", "b")])
    auc = res[(res.model == "a") & (res.metric == "auc")].iloc[0]
    assert auc.ci_low <= auc.estimate <= auc.ci_high and auc.estimate > 0.8
    diff = res[res.metric == "auc_diff"].iloc[0]
    assert diff.ci_low > 0


def test_altman_z_double_prime():
    z = z_double_prime(0.1, 0.2, 0.05, 0.8)
    assert z == pytest.approx(6.56 * 0.1 + 3.26 * 0.2 + 6.72 * 0.05 + 1.05 * 0.8)
    assert zone(3.0) == "safe" and zone(2.0) == "grey" and zone(0.5) == "distress"
