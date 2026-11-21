"""Money helpers.

All prices are stored as integer *minor units* (e.g. cents) together with an
ISO-4217 currency code. This avoids floating-point rounding errors and works
identically on SQLite and PostgreSQL. In Python, prices are handled as
``decimal.Decimal``.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# Currencies we accept. All of these have 2 minor-unit digits.
SUPPORTED_CURRENCIES = {"EUR", "BAM", "USD", "GBP", "CHF", "HUF", "RSD", "PLN"}

# Known fixed exchange rates. BAM is pegged to EUR by the Central Bank of
# Bosnia and Herzegovina's currency board (1 EUR = 1.95583 BAM). Any other
# conversion requires a user-supplied rate with a stated source.
FIXED_RATES_TO_EUR: dict[str, tuple[Decimal, str]] = {
    "EUR": (Decimal("1"), "identity"),
    "BAM": (
        Decimal("1") / Decimal("1.95583"),
        "Fixed peg: 1 EUR = 1.95583 BAM (Central Bank of BiH currency board)",
    ),
}

CENT = Decimal("0.01")


class MoneyError(ValueError):
    pass


def to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, float):
        # Go via repr to avoid binary-float artefacts (e.g. 0.1 -> 0.1000000000000000055)
        d = Decimal(repr(value))
    else:
        try:
            d = Decimal(str(value).strip().replace(",", "."))
        except (InvalidOperation, AttributeError) as exc:
            raise MoneyError(f"Not a valid amount: {value!r}") from exc
    if not d.is_finite():
        raise MoneyError(f"Not a finite amount: {value!r}")
    return d


def quantize(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def to_minor(amount: object) -> int:
    return int(quantize(to_decimal(amount)) * 100)


def from_minor(minor: int | None) -> Decimal | None:
    if minor is None:
        return None
    return (Decimal(minor) / 100).quantize(CENT)


def normalize_currency(code: str) -> str:
    c = (code or "").strip().upper()
    if c not in SUPPORTED_CURRENCIES:
        raise MoneyError(
            f"Unsupported currency {code!r}. Supported: {', '.join(sorted(SUPPORTED_CURRENCIES))}"
        )
    return c


def convert(
    amount: Decimal,
    from_currency: str,
    to_currency: str,
    user_rate: Decimal | None = None,
    user_rate_source: str | None = None,
) -> tuple[Decimal, Decimal, str]:
    """Convert ``amount``; return (converted, rate, provenance).

    ``user_rate`` means: 1 unit of ``from_currency`` = ``user_rate`` units of
    ``to_currency``. A user rate always needs a source description.
    """
    from_currency = normalize_currency(from_currency)
    to_currency = normalize_currency(to_currency)
    if from_currency == to_currency:
        return quantize(amount), Decimal("1"), "same currency"
    if user_rate is not None:
        if user_rate <= 0:
            raise MoneyError("Exchange rate must be positive")
        if not user_rate_source or not user_rate_source.strip():
            raise MoneyError("An exchange-rate source is required when supplying a rate")
        return quantize(amount * user_rate), user_rate, user_rate_source.strip()
    if to_currency == "EUR" and from_currency in FIXED_RATES_TO_EUR:
        rate, src = FIXED_RATES_TO_EUR[from_currency]
        return quantize(amount * rate), rate, src
    if from_currency == "EUR" and to_currency in FIXED_RATES_TO_EUR:
        rate, src = FIXED_RATES_TO_EUR[to_currency]
        inv = Decimal("1") / rate
        return quantize(amount * inv), inv, src
    raise MoneyError(
        f"No known exchange rate {from_currency}->{to_currency}; supply a rate and its source"
    )
