# PD model benchmark

Data: UCI Polish companies bankruptcy (all 5 horizons): 43,405 firm-years, bad rate 4.82%. Stratified 70/30 split (seed 42): 30,383 train, 13,022 held-out (627 bankruptcies). 95% CIs from 1000 stratified bootstrap resamples of the test set.

Higher is better for AUC and KS; lower is better for Brier and ECE (expected calibration error, 10 equal-count bins).

| Model | AUC | KS | Brier | ECE |
|---|---|---|---|---|
| WoE scorecard | 0.749 [0.730, 0.768] | 0.418 [0.386, 0.459] | 0.044 [0.043, 0.044] | 0.008 [0.006, 0.013] |
| Altman Z'' | 0.690 [0.668, 0.712] | 0.294 [0.264, 0.338] | 0.045 [0.045, 0.045] | 0.016 [0.013, 0.019] |
| Gradient boosting (64 ratios) | 0.971 [0.966, 0.976] | 0.817 [0.801, 0.844] | 0.019 [0.018, 0.021] | 0.009 [0.008, 0.011] |
| Gradient boosting (17 spread ratios) | 0.838 [0.824, 0.853] | 0.536 [0.509, 0.571] | 0.041 [0.040, 0.042] | 0.007 [0.005, 0.010] |

## Paired AUC differences

| Comparison | ΔAUC [95% CI] |
|---|---|
| WoE scorecard − Altman Z'' | 0.059 [0.045, 0.073] |
| Gradient boosting (17 spread ratios) − WoE scorecard | 0.089 [0.076, 0.102] |
| Gradient boosting (64 ratios) − WoE scorecard | 0.222 [0.203, 0.240] |

## Calibration (held-out deciles of predicted PD)

**WoE scorecard**

| Decile | n | Mean PD | Observed rate |
|---|---|---|---|
| 1 | 1303 | 0.827% | 0.614% |
| 2 | 1303 | 1.335% | 2.302% |
| 3 | 1302 | 1.570% | 1.075% |
| 4 | 1302 | 1.837% | 1.920% |
| 5 | 1302 | 2.382% | 2.304% |
| 6 | 1302 | 3.235% | 2.381% |
| 7 | 1302 | 4.456% | 4.685% |
| 8 | 1302 | 6.001% | 8.679% |
| 9 | 1302 | 8.544% | 9.140% |
| 10 | 1302 | 17.266% | 15.054% |

**Altman Z''**

| Decile | n | Mean PD | Observed rate |
|---|---|---|---|
| 1 | 1303 | 1.573% | 2.609% |
| 2 | 1303 | 3.095% | 1.305% |
| 3 | 1302 | 3.729% | 2.535% |
| 4 | 1302 | 4.160% | 2.151% |
| 5 | 1302 | 4.548% | 3.149% |
| 6 | 1302 | 4.869% | 4.224% |
| 7 | 1302 | 5.178% | 4.455% |
| 8 | 1302 | 5.510% | 5.684% |
| 9 | 1302 | 5.965% | 8.756% |
| 10 | 1302 | 9.316% | 13.287% |

**Gradient boosting (64 ratios)**

| Decile | n | Mean PD | Observed rate |
|---|---|---|---|
| 1 | 1303 | 0.032% | 0.000% |
| 2 | 1303 | 0.054% | 0.000% |
| 3 | 1302 | 0.088% | 0.000% |
| 4 | 1302 | 0.151% | 0.000% |
| 5 | 1302 | 0.256% | 0.077% |
| 6 | 1302 | 0.437% | 0.461% |
| 7 | 1302 | 0.766% | 0.768% |
| 8 | 1302 | 1.418% | 0.998% |
| 9 | 1302 | 3.294% | 3.917% |
| 10 | 1302 | 34.597% | 41.935% |

**Gradient boosting (17 spread ratios)**

| Decile | n | Mean PD | Observed rate |
|---|---|---|---|
| 1 | 1303 | 0.184% | 0.000% |
| 2 | 1303 | 0.409% | 0.230% |
| 3 | 1302 | 0.824% | 0.307% |
| 4 | 1302 | 1.248% | 1.075% |
| 5 | 1302 | 1.694% | 2.458% |
| 6 | 1302 | 2.385% | 2.074% |
| 7 | 1302 | 3.530% | 3.072% |
| 8 | 1302 | 5.277% | 6.682% |
| 9 | 1302 | 8.709% | 11.137% |
| 10 | 1302 | 21.556% | 21.121% |

## Scorecard features (information value on the training split)

| Feature | Definition | IV | Bins | Selected |
|---|---|---|---|---|
| Attr26 | (net profit + depreciation) / total liabilities | 0.684 | 8 | yes |
| Attr16 | (pretax profit + depreciation) / total liabilities | 0.675 | 8 | no |
| Attr46 | (current assets - inventory) / short-term liabilities | 0.562 | 7 | yes |
| Attr23 | net profit / sales | 0.506 | 8 | no |
| Attr1 | net profit / total assets | 0.480 | 7 | no |
| Attr18 | pretax profit / total assets | 0.472 | 7 | no |
| Attr7 | EBIT / total assets | 0.472 | 7 | no |
| Attr6 | retained earnings / total assets | 0.457 | 6 | yes |
| Attr42 | operating profit / sales | 0.404 | 5 | yes |
| Attr8 | book value of equity / total liabilities | 0.385 | 8 | no |
| Attr10 | equity / total assets | 0.380 | 8 | no |
| Attr2 | total liabilities / total assets | 0.372 | 8 | no |
| Attr4 | current assets / short-term liabilities | 0.366 | 8 | no |
| Attr51 | short-term liabilities / total assets | 0.347 | 7 | yes |
| Attr3 | working capital / total assets | 0.331 | 7 | no |
| Attr50 | current assets / total liabilities | 0.285 | 8 | no |
| Attr9 | sales / total assets | 0.090 | 4 | yes |

Models: the scorecard uses only the 17 ratios that can also be computed from a US GAAP spread; Altman Z'' uses its four published ratios and fixed weights, with a logistic map from Z'' to PD fitted on the training split; gradient boosting (scikit-learn HistGradientBoostingClassifier) is fitted twice, on all 64 ratios and on the scorecard's 17, to separate the effect of the model from the effect of the feature set.
