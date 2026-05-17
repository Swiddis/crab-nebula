use std::{
    collections::{HashMap, HashSet, VecDeque},
    io::{self, BufWriter, Write},
};

use ordered_float::OrderedFloat;

use crate::{
    geom::{self, PRODUCTION_RATE},
    model::{self, Galaxy},
    proto::*,
};

/// How much to pad fleets for bidding math.
/// If we send N ships, we assume only the prop*N ships will get there in time.
const FUZZ_PROP: f64 = 0.95;

// represents an instance of a goal that might be accomplished
#[derive(Clone, Debug)]
struct Auction<'a> {
    expires: OrderedFloat<f64>,
    value: OrderedFloat<f64>,
    requires: f64,
    target: &'a Planet,
}

#[derive(Clone, Debug)]
struct Bid {
    source: usize,
    target: usize,
    quantity: f64,
    time: f64,
}

pub struct Engine {
    pending_actions: VecDeque<ClientMessage>,
    g: Galaxy,
    t: f64,
}

impl Engine {
    pub fn new() -> Self {
        Self {
            pending_actions: VecDeque::new(),
            g: Galaxy::new(),
            t: 0.0,
        }
    }

    fn tock(self: &mut Engine) -> io::Result<()> {
        self.pending_actions.push_back(ClientMessage::Tock);
        let stdout = io::stdout();
        let mut out = BufWriter::new(stdout.lock());

        while let Some(action) = self.pending_actions.pop_front() {
            writeln!(out, "{}", action.to_string())?;
        }
        out.flush()?;

        Ok(())
    }

    pub fn handle(self: &mut Engine, command: ServerMessage) -> io::Result<()> {
        match command {
            ServerMessage::Tick(t) => {
                if self.g.state != model::GameState::Play {
                    return Ok(());
                }

                self.go();
                self.t += t;
                self.tock()?;
            }
            ServerMessage::Reset => {
                self.pending_actions.clear();
                self.t = 0.0;
                self.g.reset();
            }
            msg => {
                self.g.update(msg);
            }
        }
        Ok(())
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

    fn make_auction_from<'a>(
        self: &'a Engine,
        planet: &'a Planet,
        ingress: f64,
        expiry: i32,
    ) -> Auction<'a> {
        const HORIZON: f64 = 30.0; // TODO: this shouldn't be static, but i'm not sure what it _should_ be

        let base_ships = planet.ships + ingress;
        let ships_at_expiry = base_ships + self.g.aligned_production(planet.id, expiry as f64);
        let base_value = ships_at_expiry + HORIZON * PRODUCTION_RATE * planet.production;
        let worst_case_requires = if base_ships < ships_at_expiry {
            ships_at_expiry
        } else {
            base_ships
        };

        Auction {
            expires: OrderedFloat(expiry as f64),
            value: OrderedFloat(base_value),
            requires: worst_case_requires,
            target: planet,
        }
    }

    fn create_auctions<'a>(self: &'a Engine) -> Vec<Auction<'a>> {
        let ingress_map = self.ingress_map();
        let mut auctions = Vec::new();

        for planet in self.g.planets.values() {
            let ingress = match ingress_map.get(&planet.id) {
                Some(fleets) => fleets.iter().map(|f| self.g.aligned_ships(f.id)).sum(),
                None => 0.0,
            };

            for expiry in (5..60).step_by(5) {
                let auction = self.make_auction_from(planet, ingress, expiry);
                if auction.value > OrderedFloat(0.0) && auction.requires > 0.0 {
                    auctions.push(self.make_auction_from(planet, ingress, expiry))
                }
            }
        }

        auctions.sort_unstable_by_key(|a| (a.expires, -a.value));
        auctions
    }

    fn place_bids(self: &Engine, planet: &Planet, auctions: &Vec<Auction>) -> Vec<Bid> {
        let mut bids: Vec<Bid> = Vec::new();

        for auction in auctions {
            let mut prop = 0.8;
            for _ in 0..4 {
                let arrived = geom::estimate_arrived(
                    auction.expires.0,
                    prop * planet.ships,
                    planet,
                    auction.target,
                );
                if arrived < auction.requires * 0.35 {
                    break;
                }
                let fleet_size = prop * planet.ships / FUZZ_PROP;
                let eta = geom::eta(FUZZ_PROP, fleet_size, planet, auction.target);
                bids.push(Bid {
                    source: planet.id,
                    target: auction.target.id,
                    quantity: prop * planet.ships,
                    time: eta,
                });

                prop *= 0.5;
            }
        }

        bids
    }

    /// Find the fastest set of bids that win the auction.
    /// Returns the bids if they exist, otherwise returns empty vec
    fn take_bids(
        self: &Engine,
        auction: &Auction,
        bids: &mut Vec<Bid>,
        seen: &HashSet<usize>,
    ) -> Vec<Bid> {
        let mut source_contribs: HashMap<usize, f64> = HashMap::new();
        let mut take_idxs: HashMap<usize, usize> = HashMap::new();
        bids.sort_by_key(|b| OrderedFloat(b.time));

        for (i, bid) in bids.iter().enumerate() {
            if seen.contains(&bid.source) {
                continue;
            }

            match source_contribs.get(&bid.source) {
                Some(contrib) => {
                    if bid.quantity > *contrib {
                        _ = source_contribs.insert(bid.source, bid.quantity);
                        _ = take_idxs.insert(bid.source, i);
                    }
                }
                None => {
                    _ = source_contribs.insert(bid.source, bid.quantity);
                    _ = take_idxs.insert(bid.source, i);
                }
            }

            if source_contribs.values().sum::<f64>() >= auction.value.0 {
                let mut result = Vec::new();
                for v in take_idxs.values() {
                    result.push(bids[*v].clone());
                }
                return result;
            }
        }

        vec![]
    }

    fn go(self: &mut Engine) {
        let auctions = self.create_auctions();
        let stat_auctions = auctions.len();

        let mut bids: HashMap<usize, Vec<Bid>> = HashMap::new();
        for planet in self.g.planets.values() {
            if planet.owner != self.g.you {
                continue;
            }

            let pbids = self.place_bids(planet, &auctions);
            for pbid in pbids {
                match bids.get_mut(&pbid.target) {
                    Some(vec) => vec.push(pbid),
                    None => _ = bids.insert(pbid.target, vec![pbid]),
                }
            }
        }
        let stat_active_auctions = bids.len();
        let stat_bids: usize = bids.values().map(|b| b.len()).sum();

        let mut actions: Vec<Bid> = Vec::new();
        let mut seen: HashSet<usize> = HashSet::new();
        for auction in auctions {
            if let Some(bvec) = bids.get_mut(&auction.target.id) {
                let mut go_bids = self.take_bids(&auction, bvec, &seen);
                for gbid in go_bids.iter() {
                    seen.insert(gbid.source);
                }
                actions.append(&mut go_bids);
            }
        }
        let stat_actions = actions.len();

        for action in actions {
            let source = self
                .g
                .planets
                .get(&action.source)
                .expect("bid should be for a planet that exists");
            self.pending_actions.push_back(ClientMessage::Send {
                proportion: action.quantity / (FUZZ_PROP * source.ships),
                source: action.source,
                target: action.target,
            });
        }
        let stat_go = self.pending_actions.len();

        eprintln!(
            "stats: {stat_auctions}auction, {stat_active_auctions}act, {stat_bids}bid, {stat_actions}actions, {stat_go}go"
        );
    }
}
