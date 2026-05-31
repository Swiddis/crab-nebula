import hashlib
import json
import time

import requests
from bayes_opt import BayesianOptimization, acquisition

BAYES_PARAM_COUNT = 15
# This lets any individual weight govern the send sigmoid if needed: sigmoid(5.293) ~= 0.995
WEIGHT_BOUNDS = (-5.3, 5.3)


def hash_model(model):
    dat = json.dumps(model)
    h = hashlib.sha256()
    h.update(bytes(dat, encoding="ascii"))
    return h.hexdigest()[:10]


def get_players():
    res = requests.get("http://localhost:8000/player").json()
    return [
        (
            p["rating"],
            p["rd"],
            {f"x_{i}": weight for i, weight in enumerate(p["model"]["weights"])},
        )
        for p in res
    ]


def do_optimize_loop():
    pbounds = {f"x_{i}": WEIGHT_BOUNDS for i in range(BAYES_PARAM_COUNT)}
    acq = acquisition.ProbabilityOfImprovement(xi=0.01)
    optimizer = BayesianOptimization(f=None, acquisition_function=acq, pbounds=pbounds)

    players = get_players()
    rd_ct = 0
    for rating, rd, params in players:
        if rd < 70:
            optimizer.register(params=params, target=rating)
        rd_ct += 1 if rd >= 70 else 0

    for _ in range(16 - rd_ct):
        point = optimizer.suggest()
        model = {"weights": [point[f"x_{i}"] for i in range(BAYES_PARAM_COUNT)]}
        make_player = {
            "name": f"bayes_{hash_model(model)}",
            "model_version": 1,
            "model": model,
        }
        print("registering", make_player)
        res = requests.post("http://localhost:8000/player", json=make_player).json()
        assert res["acknowledged"]


if __name__ == "__main__":
    while True:
        do_optimize_loop()
        time.sleep(120)
