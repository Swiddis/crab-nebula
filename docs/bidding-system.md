# Goal-oriented bidding system

Here's one approach for how a decent(?) global planner could work:

Suppose we have a good model that lets us know how long it'd take to move ships between locations,
or how long until certain attacks land. i.e. simulating future states well.

Based on that, we can create a bidding system where we prioritize goals and have all planets bid on these goals.

The bidding system might try to optimize for gains in an interval (e.g. 60 seconds).
"If we can capture this planet in 20 seconds, we make back its cost. To get this bounty we need 40 ships."

All planets are able to participate in this bidding based on how capable they are of getting ships there. Planet 1 may commit "20 ships in 10 seconds," planet 2 may commit "10 ships in 15 seconds," done. Not _exactly_ sure how to make planets cooperatively bid, but loosely I'm thinking that faster planets take priority over slower ones and each one can participate in bidding up to its commitments and defensive resources.

So if a planet has no attackers and 20 ships to spare, it can always participate in bidding for time ranges saying "I can get 20 ships there in T." if another planet or group of planets beats it out with a faster bid, fine. If a faster planet takes half, it just joins with 10 and has resources for other bids. Once a planet's committed ships, it can't bid them again. A planet can remove its bids if it comes under attack, but not if committed.

Defense would look similar: "to defend this attack we need N ships in this amount of time, the defense is worth this much over the next 60 seconds." This goes in the global bid queue and planets start bidding.

## ok, pseudocode it, loser

```
let horizon = [interval]

for each planet:
  // for enemy planets we need to account for the production within T as part of the cost
  cost = planet's ships + enemy ingress, etc
  value will be P * (H-T) // see "selecting the value horizon"
  work out a maximum value of T where the value outweighs the cost
  bidding starts at "we need C ships by T,"
  for each planet:
    if we have ships to spare and are close enough,
      place a bid for N ships by Tb <= T
      potentially multiple bids, e.g. "I can get you 5 ships now or 20 ships in 5 seconds when reinforcements arrive"
  take the best bidders, commit those ships
```

The math is very similar for defense, except the cost is just based on ingress attacks and planets can bid on themselves.

## Selecting the value horizon

The game has a timeout, 60 seconds for small bot battles, longer for larger maps.
The server annoyingly doesn't expose the exact timeout time to the bot.
In a perfect world we directly plan against maximizing production within the timeout, but barring that:

We can choose a specific value horizon (H).
The value of a goal is based on the cost to capture it (C),
and the value produced within the horizon which is based on production rate (P) and capture time (T):

Value = V - C, where V = P * (H - T)

In the early game it's important to prioritize quick wins, in later game it's ok to invest more in a larger horizon.
A natural way to do this is to have bidding set up in growing horizons:
Start with 10s horizon, if there's no viable goals here then go to 20s, 30s, etc.

Alternatively, use a horizon based on the game duration so far.
Something like H = Game_T + 10?

## Fleet redirection?

Redirection is annoying, loosely it models a planet that can bid but has committed 100% of its resources to another goal.
If commitments are pure, this means fleets can never redirect, but sometimes redirection is useful.

A high level approach to redirection is: keep track of the value of the current commitment.
Redirect if:
- There is a new goal that is worth more than the current commitment
- The goal is within the time horizon of the fleet's goal
  - i.e. if we're 3 seconds away from landing, don't switch suddenly to a 30 second goal
- The goal can't be accomplished with just planet bids

Alternatively, maybe the current goal was invalidated (e.g. due to enemy defenses being rerouted).
I'm not sure on instinct how valuable redirecting here is (since those defenses then aren't doing other things),
but in principle it means we're throwing away ships that could maybe actually get us some value.
If we don't capture then the planet will probably just get caught by the bidding system again later.
Maybe we just put up new bids where we say "to win the battle we now need this many additional resources"
and only redirect if there's no bidders?

If we have a robust system for this, we can probably use it to overwrite other pending planet commitments too.
The tricky thing about uncommitting in general is it can cause cascading changes:
If A and B both commit to a goal and A cancels for a better goal, now B cancels, which means B
has resources for other nearby goals and may be able to take a medium-priority target working with C,
which has already committed to a lower-priority goal...
