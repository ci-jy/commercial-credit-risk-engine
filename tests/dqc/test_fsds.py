import numpy as np
import pandas as pd

from conftest import build_quarter, fact
from credit_engine.dqc.compare import month_end, normalise_dims
from credit_engine.dqc.fsds import infer_decimals, parse_segments


def test_infer_decimals_from_trailing_zeros():
    vals = np.array([1_234_000, 1_200_000, 5, 0.25, 0.0, -3_000_000_000])
    assert infer_decimals(vals).tolist() == [-3, -5, 0, 2, 4, -6]


def test_filing_level_decimals_use_the_most_common_precision():
    q = build_quarter([fact("Assets", 1_000_000), fact("Liabilities", 2_345_000), fact("Cash", 7_891_000),
                       fact("StockholdersEquity", 5_000), fact("Goodwill", 1_234_567)], background=False)
    dec = dict(zip(q.num.tag.astype(str), q.num.decimals))
    # 1,000,000 alone looks like decimals -6, but the filer reports in thousands
    assert dec["Assets"] == -3 and dec["Liabilities"] == -3 and dec["StockholdersEquity"] == -3
    assert dec["Goodwill"] == 0


def test_parse_segments():
    assert parse_segments("ClassOfStock=CommonClassA;EquityComponents=CommonStock;") == {
        "ClassOfStock": "CommonClassA", "EquityComponents": "CommonStock"}
    assert parse_segments(np.nan) == {}


def test_periods_and_dimension_flags():
    q = build_quarter([fact("Revenues", 10, ddate=20251231, qtrs=4),
                       fact("Revenues", 3, ddate=20250930, qtrs=1, segments="ProductOrService=Widgets;")],
                      background=False)
    r = q.num.sort_values("qtrs")
    assert r.start.iloc[0] == pd.Timestamp("2025-06-30") and r.start.iloc[1] == pd.Timestamp("2024-12-31")
    assert r.dimensionless.tolist() == [False, True]
    assert q.num.doc_period.iloc[0] == pd.Timestamp("2025-12-31")


def test_ifrs_filings_are_not_screened():
    q = build_quarter([fact("Revenue", 10, version="ifrs/2024"), fact("Assets", 5)], background=False)
    assert q.num.empty


def test_arelle_contexts_are_normalised_to_data_set_form():
    assert month_end("2026-02-28") == 20260228
    assert month_end("2026-03-01") == 20260228  # 52/53-week year end rounds to the nearest month end
    assert month_end("2025-12-27") == 20251231
    assert normalise_dims({"us-gaap:StatementEquityComponentsAxis": "us-gaap:CommonStockMember",
                           "us-gaap:StatementClassOfStockAxis": "abc:SeriesXMember"}) == \
        "ClassOfStock=SeriesX;EquityComponents=CommonStock;"
    assert normalise_dims({"srt:StatementScenarioAxis": "srt:ScenarioForecastMember"}) == "Scenario=ScenarioForecast;"
