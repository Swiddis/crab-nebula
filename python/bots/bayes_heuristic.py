"""
Simple small heuristic network learned with bayesian optimization

Only using information that's readily available from individual planet pairs
(i.e. not doing any collision math)
"""

import math
import sys
from hashlib import sha256

import galcon_entities as ge
import gbotlib as gbl
import requests

"""
Planet(P) = ReLU(
    ships + prod + alignment + source? + bias
)

Dist(A, B) = ReLU(
    hypot + bias
)

Send = Planet(S) + Planet(T) + Dist(S, T) + bias
Value = Planet(S) + Planet(T) + Dist(S, T) + bias
Outputs: Send (Sigmoid), Value (ReLU)
Params: 15
"""
weights = [0] * 15
player = 0

norms = {
    "ships": {"mean": 21.96559223300971, "stdev": 14.17529706031457},
    "prod": {"mean": 60.947766990291264, "stdev": 26.427569572625103},
    "dist": {"mean": 203.3761469008101, "stdev": 97.27465915087276},
}


def sigmoid(x: float):
    return 1.0 / (1.0 + math.exp(-x))


def relu(x: float):
    return x if x > 0.0 else 0.0


def alignment(p: ge.Planet, g: ge.Galaxy):
    if p.owner == g.you:
        return 1.0
    if g.users[p.owner].team == 0:
        return 0.0
    return -1.0


def planet(p: ge.Planet, g: ge.Galaxy, source: bool) -> float:
    align = alignment(p, g)
    srcval = 1.0 if source else 0.0
    return relu(
        weights[0] * (p.ships - norms["ships"]["mean"]) / norms["ships"]["stdev"]
        + weights[1] * (p.production - norms["ships"]["prod"]) / norms["ships"]["stdev"]
        + weights[2] * align
        + weights[3] * srcval
        + weights[4]
    )


def dist(a: ge.Planet, b: ge.Planet) -> float:
    dist = a.distance(b)
    return relu(
        weights[5] * (dist - norms["dist"]["mean"]) / norms["dist"]["stdev"]
        + weights[6]
    )


def evaluate(source: ge.Planet, target: ge.Planet, g: ge.Galaxy) -> tuple[float, float]:
    send = sigmoid(
        weights[7] * planet(source, g, True)
        + weights[8] * planet(target, g, False)
        + weights[9] * dist(source, target)
        + weights[10]
    )
    value = relu(
        weights[11] * planet(source, g, True)
        + weights[12] * planet(target, g, False)
        + weights[13] * dist(source, target)
        + weights[14]
    )
    return (send, value)


def save_result(result_line, player):
    # TODO: need to have infra in matchserv to save game results
    pass


def init_weights(galaxy: ge.Galaxy):
    global player
    global weights

    h = sha256()
    state = sorted(galaxy.planets.values(), key=lambda p: p.n)
    for p in state:
        h.update(bytes(str(p), encoding="utf-8"))
    h = h.hexdigest()

    # TODO: we need to actually populate the weights table somehow?
    res = requests.get(f"http://localhost:8000/match/{h}?model_version=1").json()
    player = res["player"]
    weights = res["weights"]
    print(f"starting round as player {player}", file=sys.stderr)


def bot(galaxy: ge.Galaxy, **kwargs):
    global player

    if kwargs["result"]:
        save_result(kwargs["result"], player)
    if galaxy.frame == 0:
        init_weights(galaxy)
    pass


if __name__ == "__main__":
    gbl.run(bot)
