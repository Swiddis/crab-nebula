import sys

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.optimize import curve_fit
from sklearn.linear_model import Ridge
from tqdm import tqdm


def logistic(t, t0, k, L, b):
    return L / (1 + np.exp(-k * (t - t0))) + b


def fit_one_fleet(fleet_id, grp):
    grp = grp.dropna(subset=["frac_arrived", "t_norm"])
    t = grp["t_norm"].values
    y = grp["frac_arrived"].values
    try:
        p0 = [t.mean(), 5.0, 1.0, 0.0]
        bounds = ([t.min(), 0.1, 0.5, -0.1], [t.max(), 50.0, 1.05, 0.1])
        popt, _ = curve_fit(logistic, t, y, p0=p0, bounds=bounds, maxfev=2000)
        return {
            **dict(zip(["t0", "k", "L", "b"], popt)),
            "fleet_id": fleet_id,
            "source_target_dist": grp["source_target_dist"].iloc[0],
            "source_r": grp["source_r"].iloc[0],
            "target_r": grp["target_r"].iloc[0],
            "fleet_size": grp["fleet_size"].iloc[0],
        }
    except RuntimeError:
        return None


def fit_fleets(df):
    groups = list(df.groupby("fleet_id"))
    results = Parallel(n_jobs=-1)(
        delayed(fit_one_fleet)(fleet_id, grp)
        for fleet_id, grp in tqdm(groups, desc="Fitting fleets")
    )
    return pd.DataFrame([r for r in results if r is not None])


if __name__ == "__main__":
    print("Loading data...", file=sys.stderr)
    df = pd.read_json("data/fleet_movements.json", lines=True)

    print("Normalizing...", file=sys.stderr)
    df["frac_arrived"] = (1.0 - df["fleet_ships"] / df["fleet_size"]).clip(0.0, 1.0)
    df["t_norm"] = df["t"] / df["source_target_dist"]

    params_df = fit_fleets(df)

    features = ["source_target_dist", "source_r", "target_r", "fleet_size"]
    X = params_df[features].values
    results = []
    for param in ["t0", "k", "L", "b"]:
        reg = Ridge().fit(X, params_df[param].values)
        results.append(f"{param}: coefs={reg.coef_}, intercept={reg.intercept_:.4f}")

    print("\n".join(results))
