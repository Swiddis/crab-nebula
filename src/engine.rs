use std::collections::{HashMap, HashSet, VecDeque};

use ordered_float::OrderedFloat;

use crate::{
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
    ships: f64,
    time: f64,
}

pub struct Engine {
    pub action_queue: VecDeque<ClientMessage>,
    g: Galaxy,
    t: f64,
}

impl Engine {
    pub fn new() -> Self {
        Self {
            action_queue: VecDeque::new(),
            g: Galaxy::new(),
            t: 0.0,
        }
    }

    fn reset(self: &mut Engine) {
        self.t = 0.0;
        self.g.reset();
    }

    fn go(self: &mut Engine, t: f64) {
        if self.g.state != model::GameState::Play {
            return;
        }

        self.compute_tick();
        self.action_queue.push_back(ClientMessage::Tock);
        self.t += t;
    }

    pub fn handle(self: &mut Engine, command: ServerMessage) {
        match command {
            ServerMessage::Tick(t) => self.go(t),
            ServerMessage::Reset => self.reset(),
            msg => self.g.update(msg),
        }
    }

    /// map each planet to all fleets that are approaching the planet
    fn ingress_map(self: &Engine) -> HashMap<usize, Vec<&Fleet>> {
        let mut map: HashMap<usize, Vec<&Fleet>> = HashMap::new();

        for fleet in self.g.fleets.values() {
            match map.get_mut(&fleet.target) {
                Some(ingress) => ingress.push(&fleet),
                None => _ = map.insert(fleet.target, vec![fleet]),
            }
        }

        map
    }

    /// Get a list of potential target planets with ships adjusted to how many ships are necessary to satisfy the target,
    /// accounting for all active fleet ingress and retention.
    /// Doesn't account for production over time for enemy planets.
    fn get_ingress_balanced_targets(self: &Engine) -> Vec<Planet> {
        let ingress = self.ingress_map();
        let mut ibt: Vec<Planet> = self.g.planets.values().cloned().collect();
        for planet in ibt.iter_mut() {
            planet.ships = -(self.g.aligned_ships(planet.id) - RETAIN_PROP * planet.production);
            match ingress.get(&planet.id) {
                Some(fleets) => {
                    planet.ships += fleets
                        .iter()
                        .map(|f| -self.g.aligned_ships(f.id))
                        .sum::<f64>();
                }
                None => {}
            }
        }
        ibt.retain(|p| p.ships > 0.0);
        ibt.sort_by_key(|p| -OrderedFloat(p.production / p.ships));
        ibt
    }

    fn place_attack_bids(self: &mut Engine, source: &Planet, target: &Planet) -> Vec<Bid> {
        let mut bids: Vec<Bid> = Vec::new();
        let surplus = source.ships - RETAIN_PROP * source.production;

        const TEST_PROPS: [f64; 4] = [1.00, 0.75, 0.50, 0.25];
        for test_prop in TEST_PROPS {
            let to_send = test_prop * surplus;
            let t = geom::eta(SEND_SURVIVAL_PROP, to_send, source, target);
            let mut goal = target.ships;
            if self.g.alignment(target.owner) < 0.0 {
                goal += PRODUCTION_RATE * t;
            }

            if to_send * SEND_SURVIVAL_PROP < goal {
                break;
            }
            bids.push(Bid {
                source: source.id,
                target: target.id,
                ships: to_send,
                time: t,
            });
        }

        bids
    }

    /// Select best bids from the given bids to execute, according to the priority implied by the bid's sorting
    fn execute_bids(self: &mut Engine, bids: &Vec<Bid>) {
        let mut alloc_sources: HashMap<usize, f64> = HashMap::new();
        let mut alloc_targets: HashSet<usize> = HashSet::new();
        for bid in bids {
            if alloc_targets.contains(&bid.target) {
                continue;
            }
            let source = self
                .g
                .planets
                .get(&bid.source)
                .expect("received bid for invalid source");
            let remaining = match alloc_sources.get(&source.id) {
                Some(spent) => source.ships - spent - RETAIN_PROP * source.production,
                None => source.ships - RETAIN_PROP * source.production,
            };
            if remaining < bid.ships {
                continue;
            }

            alloc_sources.insert(bid.source, bid.ships);
            alloc_targets.insert(bid.target);
            self.action_queue.push_back(ClientMessage::Send {
                proportion: bid.ships / source.ships,
                source: bid.source,
                target: bid.target,
            });
        }
    }

    fn compute_tick(self: &mut Engine) {
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

        let mut bids = Vec::new();
        for source in our_planets.iter() {
            if source.ships - RETAIN_PROP * source.production <= 0.0
                || target_indices.contains_key(&source.id)
            {
                continue;
            }
            for target in targets.iter() {
                bids.append(&mut self.place_attack_bids(source, target));
            }
        }
        bids.sort_by_key(|b| {
            (
                target_indices
                    .get(&b.target)
                    .expect("received bid for invalid target"),
                OrderedFloat(b.time),
            )
        });
        self.execute_bids(&bids);
    }
}
