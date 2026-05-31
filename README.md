# galcon bots

My work on [Galcon Bots](https://www.galcon.com/bots/).

The repo structure is vaguely as such:
- `scripts` (primarily Python) is auxiliary scripts for bot dev, and not actually bot logic. You need dev dependencies for these.
- `python` is auxiliary stuff.
  - `bots` are bots I wrote in Python, mostly legacy or simple heurstics-based bots from when I first started playing several years ago. It contains bluemax which is my first bot that could somewhat beat `classic`.
  - `matchserv` is a matchmaking server that's used to orchestrate bot training.
- `rust` is the home of the main Nebula bot, which at the moment is only _barely_ stronger than bluemax. I'll be improving it over time.
  - `galcon` is bot-agnostic code: server protocol, the core game logic, geometry, and the engine loop.
  - `nebula` is the bot. It's mostly a placeholder for the moment.

I might move things around more later.

## general approach

I have some more notes that I might check in to the repo later, but generally the approach to making a strong Galcon bot is:
1. Build an accurate model of the future -- if we take this action, what will the map look like in T seconds (assuming no other actions taken)? What if this other action happens at T+epsilon?
2. Build a good heuristic model that can find strong candidate actions to try given any particular state.
3. Do a big search on top of our future model and heuristics, assuming the opponent is adversarially doing the same. Pick actions that hold up against enemy action.

All of these branches are work-in-progress. The current best heuristics I have are the legacy `bluemax.py` and the less-legacy `rust/nebula`, I'm working on training a better one via `bayes_heuristic.py` for the case of trivial params. I'm going to later be developing a neural net that can hopefully do better, with more complex heuristics and training.

The future model is very basic and described in `geom/model.rs`, just based on regression. Later I'll account for obstacles and ideally implement my own server, which will be approximate but will give a good testing ground for developing much stronger heuristics, faster.

The search doesn't yet exist in any capacity, but that will be in `rust/nebula` once ready. The current code there is a(nother) heuristic that uses the future model. As the future model gets better I expect it may get stronger, and then I plan to rip out the current code and replace with trained heuristics and MCTS search.

## contributing?

Sure!

## ai used?

There's machine learning involved in the heuristic development, but no, the code and docs here are not generated.

## this is kind-of a mess?

It's like 5 different projects stacked in a trenchcoat, and also some of the code here is from before I knew how to use Git.

Nebula is the ultimate output goal, I just also am tracking a ton of supplementary stuff for developing it. I might try to reorganize things later.
