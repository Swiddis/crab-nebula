"""
Simple small heuristic network learned with bayesian optimization

Only using information that's readily available from individual planet pairs
(i.e. not doing any collision math)
"""

import heapq
import math
import sys
from collections import defaultdict
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

    if player == 0:
        return

    duration, winner = float(result_line[2]), int(result_line[4])

    our_score, their_score, neutral_score = 0, 0, 0
    for p in galaxy.planets.values():
        if p.owner == galaxy.you:
            our_score += p.production
        elif galaxy.users[p.owner].team == 0:
            neutral_score += p.production
        else:
            their_score += p.production

    total = our_score + their_score + neutral_score
    our_score, their_score = (
        (1.0, 0.0)
        if their_score == 0 and our_score > 0
        else (0.0, 1.0)
        if our_score == 0 and their_score > 0
        else (
            (our_score + 0.5 * neutral_score) / total,
            (their_score + 0.5 * neutral_score) / total,
        )
    )
    if winner == galaxy.you:
        win_score, loss_score = our_score, their_score
    else:
        win_score, loss_score = their_score, our_score
    opponent = [
        user
        for user in galaxy.users.values()
        if user.team != 0 and user.n != galaxy.you
    ][0]
    result = {
        "duration": duration,
        "winner": player if winner == galaxy.you else 3 - player,
        "win_score": win_score,
        "loss_score": loss_score,
        "opponent": opponent.name,
    }

    save = requests.post(
        f"http://localhost:8000/match/{state_hash}/complete", json=result
    ).json()
    if save is None:
        print("received no response from server", file=sys.stderr)
    elif not save.get("acknowledged", False):
        print(f"failed to save result: {save}", file=sys.stderr)
    else:
        print(
            f"result saved (Δscore={round(our_score - their_score, 3)})",
            file=sys.stderr,
        )


def init_weights(galaxy: ge.Galaxy, opponent: str):
    global player
    global weights
    global state_hash

    h = sha256()
    state = sorted(galaxy.planets.values(), key=lambda p: p.n)
    for p in state:
        h.update(bytes(str(p), encoding="utf-8"))
    state_hash = h.hexdigest()

    # res = requests.post(
    #     f"http://localhost:8000/match/{state_hash}?model_version=1&opponent={opponent}"
    # ).json()
    res = requests.get("http://localhost:8000/top?model_version=1").json()
    # player = res["player"]
    player = 0
    weights = res["model"]["weights"]
    print(f"starting round as player {player}", file=sys.stderr)


def bot(galaxy: ge.Galaxy, **kwargs):
    global player
    global weights

    if kwargs.get("result", None):
        save_result(kwargs["result"], galaxy)
        return
    if galaxy.frame == 0:
        opponent = [
            user
            for user in galaxy.users.values()
            if user.team != 0 and user.n != galaxy.you
        ][0]
        init_weights(galaxy, opponent.name)

    # our beloved bot alg
    ships_left: dict[int, float] = {}
    send_queue: list[tuple[tuple, int, int, float, float]] = []
    flow: dict[tuple[int, int], float] = defaultdict(lambda: 0.0)
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
                # cancel out direct cycles to reduce noise
                flow[(source.n, target.n)] += send * source.ships
                flow[(target.n, source.n)] -= send * source.ships

    heapq.heapify(send_queue)
    while len(send_queue) > 0:
        _, source, target, send, init_ships = heapq.heappop(send_queue)
        if (
            ships_left[source] >= send * init_ships
            and send > 0.0
            and flow[(source, target)] > 0.0
        ):
            to_send = flow[(source, target)] / init_ships
            print(f"/SEND\t{round(100 * to_send)}\t{source}\t{target}")
            ships_left[source] -= send * init_ships

    print("/TOCK")


if __name__ == "__main__":
    gbl.run(bot)
