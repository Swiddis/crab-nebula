import json

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from sklearn.linear_model import Ridge

dataset = pd.read_json("data/fleet_movements.json", lines=True, chunksize=128000)
df = pd.concat(dataset)

df = df.sort_values(["fleet_id", "t"])
t0 = df.groupby("fleet_id")["t"].transform("first")
t0_ships = df.groupby("fleet_id")["fleet_ships"].transform("first")
df["frac_arrived"] = (1.0 - df["fleet_ships"] / t0_ships).clip(0.0, 1.0)
df["t_norm"] = (df["t"] - t0) / df["source_target_dist"]

print(df["t_norm"])
print(df["frac_arrived"])
