use std::collections::{HashMap, VecDeque};

use ordered_float::OrderedFloat;

use galcon::{
    engine::Engine,
    geom::{self, PRODUCTION_RATE},
    model::{self, Galaxy},
    proto::*,
};

/// Retain this amount of a planet's production for defense
const RETAIN_PROP: f64 = 0.1;
/// When doing send math, base it on this proportion of ships reaching the destination
const SEND_SURVIVAL_PROP: f64 = 0.95;

struct Bid {
    source: usize,
    target: usize,
    to_send: f64,
    clears_goal: f64,
    time: f64,
}

pub struct Nebula {
    pub action_queue: VecDeque<ClientMessage>,
    g: Galaxy,
    t: f64,
}

impl Engine for Nebula {
    fn handle(&mut self, message: ServerMessage) {
        match message {
            ServerMessage::Tick(t) => self.go(t),
            ServerMessage::Reset => self.reset(),
            msg => self.g.update(msg),
        }
    }

    fn pop_action(&mut self) -> Option<ClientMessage> {
        self.action_queue.pop_front()
    }
}

impl Nebula {
    #[allow(clippy::new_without_default)]
    pub fn new() -> Self {
        Self {
            action_queue: VecDeque::new(),
            g: Galaxy::new(),
            t: 0.0,
        }
    }

    fn reset(self: &mut Nebula) {
        self.t = 0.0;
        self.g.reset();
    }

    fn go(self: &mut Nebula, t: f64) {
        if self.g.state != model::GameState::Play {
            return;
        }

        self.compute_tick();
        self.action_queue.push_back(ClientMessage::Tock);
        self.t += t;
    }

    /// map each planet to all fleets that are approaching the planet
    fn ingress_map(self: &Nebula) -> HashMap<usize, Vec<&Fleet>> {
        let mut map: HashMap<usize, Vec<&Fleet>> = HashMap::new();

        for fleet in self.g.fleets.values() {
            match map.get_mut(&fleet.target) {
                Some(ingress) => ingress.push(fleet),
                None => _ = map.insert(fleet.target, vec![fleet]),
            }
        }

        map
    }

    /// Get a list of potential target planets with ships adjusted to how many ships are necessary to satisfy the target,
    /// accounting for all active fleet ingress and retention.
    /// Doesn't account for production over time for enemy planets.
    fn get_ingress_balanced_targets(self: &Nebula) -> Vec<Planet> {
        let ingress = self.ingress_map();
        let mut ibt: Vec<Planet> = self.g.planets.values().cloned().collect();
        for planet in ibt.iter_mut() {
            planet.ships = -(self.g.aligned_ships(planet.id) - RETAIN_PROP * planet.production);
            if let Some(fleets) = ingress.get(&planet.id) {
                planet.ships += fleets
                    .iter()
                    .map(|f| -self.g.aligned_ships(f.id))
                    .sum::<f64>();
            }
        }
        ibt.retain(|p| p.ships > 0.0);

        ibt.sort_by_key(|p| {
            (
                -OrderedFloat(p.production / p.ships),
                // ties for prod/ships generally only happens in the opening, in this case prioritize our side
                // overall if there's a tie, we _most likely_ have more friends closer to our initial base
                OrderedFloat(geom::hypot(p, self.g.base())),
            )
        });
        ibt
    }

    fn place_attack_bids(self: &mut Nebula, source: &Planet, target: &Planet) -> Vec<Bid> {
        let mut bids: Vec<Bid> = Vec::new();
        let surplus = source.ships - RETAIN_PROP * source.production;

        const TEST_PROPS: [f64; 4] = [1.00, 0.75, 0.50, 0.25];
        for test_prop in TEST_PROPS {
            let to_send = test_prop * surplus;
            let time = geom::eta(SEND_SURVIVAL_PROP, to_send, source, target);
            let mut goal = target.ships;
            if self.g.alignment(target.owner) < 0.0 {
                goal += PRODUCTION_RATE * time;
            }

            if to_send * SEND_SURVIVAL_PROP < goal / 3.0 {
                // don't flood with bids that are unlikely to be taken
                break;
            }
            let clears_goal = geom::estimate_arrived(time, to_send, source, target);
            bids.push(Bid {
                source: source.id,
                target: target.id,
                to_send,
                clears_goal,
                time,
            });
        }

        bids
    }

    /// Select best bids from the given bids to execute, according to the priority implied by the bid's sorting.
    /// Assumes all bids have the same target with a threshold indicated by threshold.
    /// source_limits is updated according to the bids accepted.
    fn take_bids(
        self: &mut Nebula,
        target_threshold: f64,
        bids: &Vec<Bid>,
        source_limits: &mut HashMap<usize, f64>,
    ) {
        let mut take_bids: HashMap<usize, &Bid> = HashMap::new();
        let mut clears_threshold = false;

        for bid in bids {
            if bid.to_send > *source_limits.get(&bid.source).unwrap_or(&0.0) {
                continue;
            }

            match take_bids.get(&bid.source) {
                Some(current_bid) => {
                    if bid.clears_goal > current_bid.clears_goal {
                        _ = take_bids.insert(current_bid.source, bid);
                    }
                }
                None => {
                    _ = take_bids.insert(bid.source, bid);
                }
            }
            if take_bids.values().map(|b| b.clears_goal).sum::<f64>() > target_threshold {
                clears_threshold = true;
                break;
            }
        }

        if !clears_threshold {
            return;
        }

        for bid in take_bids.values() {
            let source = self
                .g
                .planets
                .get(&bid.source)
                .expect("received bid from nonexistent planet");
            self.action_queue.push_back(ClientMessage::Send {
                proportion: bid.to_send / source.ships,
                source: bid.source,
                target: bid.target,
            });
            let prev_lim = *source_limits.get(&bid.source).unwrap_or(&0.0);
            _ = source_limits.insert(bid.source, prev_lim - bid.to_send);
        }
    }

    fn compute_tick(self: &mut Nebula) {
        let targets = self.get_ingress_balanced_targets();
        let target_indices: HashMap<usize, usize> =
            targets.iter().enumerate().map(|(i, p)| (p.id, i)).collect();
        let our_planets: Vec<Planet> = self
            .g
            .planets
            .values()
            .filter(|p| p.owner == self.g.you)
            .cloned()
            .collect();

        let mut bids: HashMap<usize, Vec<Bid>> = HashMap::new();
        let mut source_limits: HashMap<usize, f64> = HashMap::new();
        for source in our_planets.iter() {
            let lim = source.ships - RETAIN_PROP * source.production;
            if lim <= 0.0 || target_indices.contains_key(&source.id) {
                continue;
            }
            _ = source_limits.insert(source.id, lim);
            for target in targets.iter() {
                match bids.get_mut(&target.id) {
                    Some(v) => v.append(&mut self.place_attack_bids(source, target)),
                    None => _ = bids.insert(target.id, self.place_attack_bids(source, target)),
                }
            }
        }

        for target in targets {
            if let Some(bvec) = bids.get_mut(&target.id) {
                bvec.sort_by_key(|b| OrderedFloat(b.time));
                self.take_bids(target.ships, bvec, &mut source_limits);
            }
        }
    }
}

fn main() {
    let nebula = Nebula::new();
    galcon::engine::run_engine(nebula);
}
