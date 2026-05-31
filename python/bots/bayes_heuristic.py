"""
Simple small heuristic network learned with bayesian optimization

Only using information that's readily available from individual planet pairs
(i.e. not doing any collision math)
"""

import heapq
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

For all outputs with positive value,
sorted by most value first:
    Do the send if enough ships are left

I don't expect this alg to get particularly good but it should make a pretty strong heuristic,
in particular there's no built-in collaboration to allocate the source ships.
Over time I expect it to consistently send >0.5 to avoid leaving planets defenseless,
and develop a decent value system for prioritization.
"""
weights = [0] * 15
player = 0
state_hash = None

norms = {
    "ships": {"mean": 21.96559223300971, "stdev": 14.17529706031457},
    "prod": {"mean": 60.947766990291264, "stdev": 26.427569572625103},
    "dist": {"mean": 203.3761469008101, "stdev": 97.27465915087276},
}


def sigmoid(x: float):
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0


def relu(x: float):
    return max(x, 0.0)


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
        + weights[1] * (p.production - norms["prod"]["mean"]) / norms["prod"]["stdev"]
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


def save_result(result_line: list[str], galaxy: ge.Galaxy):
    global player
    global state_hash

    duration, winner = float(result_line[2]), int(result_line[4])
    if winner != galaxy.you:
        # avoid collisions with loser by only reporting games we won
        print("lost", file=sys.stderr)
        return

    result = {"duration": duration, "winner": player}

    save = requests.post(
        f"http://localhost:8000/match/{state_hash}/complete", json=result
    ).json()
    if not save.get("acknowledged", False):
        print(f"failed to save result: {save}", file=sys.stderr)
    else:
        print("win saved", file=sys.stderr)


def init_weights(galaxy: ge.Galaxy):
    global player
    global weights
    global state_hash

    h = sha256()
    state = sorted(galaxy.planets.values(), key=lambda p: p.n)
    for p in state:
        h.update(bytes(str(p), encoding="utf-8"))
    state_hash = h.hexdigest()

    res = requests.post(
        f"http://localhost:8000/match/{state_hash}?model_version=1"
    ).json()
    player = res["player"]
    weights = res["model"]["weights"]
    print(f"starting round as player {player}", file=sys.stderr)


def bot(galaxy: ge.Galaxy, **kwargs):
    global player
    global weights

    if kwargs.get("result", None):
        save_result(kwargs["result"], galaxy)
        return
    if galaxy.frame == 0:
        init_weights(galaxy)

    # our beloved bot alg
    ships_left: dict[int, float] = {}
    send_queue: list[tuple[tuple, int, int, float, float]] = []
    for source in galaxy.planets.values():
        if source.owner != galaxy.you:
            continue
        for target in galaxy.planets.values():
            if target.n == source.n:
                continue

            send, value = evaluate(source, target, galaxy)
            if value > 0.0:
                # `value` should almost always be tiebreak immune.
                # but just in case, fallback to more value for less cost
                sort_key = (-value, send * source.ships)
                send_queue.append((sort_key, source.n, target.n, send, source.ships))
                ships_left[source.n] = source.ships

    heapq.heapify(send_queue)
    while len(send_queue) > 0:
        _, source, target, send, init_ships = heapq.heappop(send_queue)
        if ships_left[source] >= send * init_ships and send > 0.0:
            print(f"/SEND\t{round(100 * send)}\t{source}\t{target}")
            ships_left[source] -= send * init_ships

    print("/TOCK")


if __name__ == "__main__":
    gbl.run(bot)
