# galcon bots

My work on [Galcon Bots](https://www.galcon.com/bots/).

The repo structure is vaguely as such:
- `scripts` (primarily Python) is auxiliary scripts for bot dev, and not actually bot logic. You need dev dependencies for these.
- `python` is auxiliary stuff.
  - `bots` are bots I wrote in Python, mostly legacy or simple heurstics-based bots from when I first started playing several years ago. It contains bluemax which is my first bot that could somewhat beat `classic`.
  - `matchserv` is a matchmaking server that's used to orchestrate bot training.
- `rust` is the home of the main Nebula bot, which at the moment is only _barely_ stronger than bluemax. I'll be improving it over time.
  - `galcon` is bot-agnostic code: server protocol, the core game logic, geometry, and the engine loop.
  - `nebula` is the bot. There will be more bots soon as I mess with more approaches.

I might move things around more later.
