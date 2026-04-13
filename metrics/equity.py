# metrics/equity.py

import pandas as pd


def load_equity_curve(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "balance" not in df.columns:
        raise ValueError("CSV must contain 'balance' column")

    df["equity"] = df["balance"]
    return df
