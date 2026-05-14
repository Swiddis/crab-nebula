import hashlib
import os
import pathlib

LOGS = pathlib.Path("data/logs")
GAMES = pathlib.Path("data/games")


def hashname(content):
    cbytes = bytes(content, encoding="utf-8")
    h = hashlib.sha256(cbytes)
    return f"{h.hexdigest()[:16]}.log"


def flush_game(lines):
    content = "\n".join(lines)
    fname = GAMES / hashname(content)
    if os.path.exists(fname):
        return
    with open(fname, "w") as fp:
        fp.write(content)


def extract_from(path: pathlib.Path):
    lines = []
    ct = 0

    with open(path, "r") as fp:
        for line in fp:
            if line.startswith("/RESET"):
                lines = []
            lines.append(line.strip())
            if line.startswith("/RESULTS"):
                flush_game(lines)
                ct += 1
    return ct


if __name__ == "__main__":
    ct = 0
    for fname in os.listdir(LOGS):
        ct += extract_from(LOGS / fname)
    print(f"{ct} games found")
