# risk/sizing.py

def fixed_fractional_size(
    balance: float,
    risk_pct: float,
    entry_price: float,
    stop_price: float,
    max_position_notional_pct: float = 1.0,
) -> float:
    """
    Classic fixed-fractional position sizing.

    risk_pct = fraction of balance you are willing to lose
    """

    risk_amount = balance * risk_pct
    per_unit_risk = abs(entry_price - stop_price)

    if per_unit_risk <= 0:
        return 0.0

    qty = risk_amount / per_unit_risk

    # Safety caps: avoid sizing above available capital and optional notional cap.
    max_qty_by_balance = balance / entry_price if entry_price > 0 else 0.0
    max_qty_by_notional = (
        (balance * max_position_notional_pct) / entry_price
        if entry_price > 0 and max_position_notional_pct > 0
        else 0.0
    )

    qty = min(qty, max_qty_by_balance, max_qty_by_notional)
    return max(0.0, qty)
