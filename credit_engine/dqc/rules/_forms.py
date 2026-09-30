"""Document types each rule applies to (``resources/rule-form-lookup/rule-form-lookup.csv``)."""

PERIODIC = {"10-K", "10-K/A", "10-KT", "10-KT/A", "20-F", "20-F/A", "40-F", "40-F/A",
            "10-Q", "10-Q/A", "10-QT", "10-QT/A"}
REGISTRATION = {"S-1", "S-1/A", "S-3", "S-3/A", "S-4", "S-4/A", "S-11", "S-11/A", "F-1", "F-1/A",
                "F-3", "F-3/A", "F-4", "F-4/A", "POS AM", "11-K", "11-K/A"}


def applicable(num, forms: set[str]):
    """Rows of ``num`` whose filing's form is in ``forms``."""
    return num[num.form.isin(forms)]
