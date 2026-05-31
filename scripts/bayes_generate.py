import hashlib
import json

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


if __name__ == "__main__":
    pbounds = {f"x_{i}": WEIGHT_BOUNDS for i in range(BAYES_PARAM_COUNT)}
    acq = acquisition.UpperConfidenceBound()
    optimizer = BayesianOptimization(f=None, acquisition_function=acq, pbounds=pbounds)

    for i in range(64):
        point = optimizer.suggest()
        model = {"weights": [point[f"x_{i}"] for i in range(BAYES_PARAM_COUNT)]}
        make_player = {
            "name": f"bayes_{hash_model(model)}",
            "model_version": 1,
            "model": model,
        }
        res = requests.post("http://localhost:8000/player", json=make_player).json()
        assert res["acknowledged"]
