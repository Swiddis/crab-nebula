import os
import pathlib

from tqdm import tqdm

from galcon import Galaxy, parse

GAMES = pathlib.Path("data/games")


def main():
    g = Galaxy()
    for gamefile in tqdm(os.listdir(GAMES)):
        with open(GAMES / gamefile, "r") as fp:
            for line in fp:
                parse(g, line)
                # todo the rest of the extraction


if __name__ == "__main__":
    main()
