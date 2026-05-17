use std::collections::HashMap;

use crate::{geom, proto::*};

#[derive(Debug, PartialEq, Eq, Clone, Copy)]
pub enum GameState {
    Init,
    Play,
    Done,
}

pub struct Galaxy {
    pub users: HashMap<usize, User>,
    pub planets: HashMap<usize, Planet>,
    pub fleets: HashMap<usize, Fleet>,
    pub you: usize,
    pub state: GameState,
    pub speed: f64,
}

impl Galaxy {
    pub fn new() -> Self {
        Self {
            users: HashMap::new(),
            planets: HashMap::new(),
            fleets: HashMap::new(),
            you: 0,
            state: GameState::Init,
            speed: 0.0,
        }
    }

    pub fn reset(self: &mut Galaxy) {
        self.users.clear();
        self.planets.clear();
        self.fleets.clear();
        self.you = 0;
        self.state = GameState::Init;
        self.speed = 0.0;
    }

    fn apply_meta(self: &mut Galaxy, set_meta: SetMeta) {
        match set_meta {
            SetMeta::You(id) => self.you = id,
            SetMeta::State(state) => match state.as_str() {
                "PLAY" => self.state = GameState::Play,
                "DONE" => self.state = GameState::Done,
                _ => eprintln!("warn: unrecognized state {state}"),
            },
            SetMeta::Speed(speed) => self.speed = speed,
        }
    }

    fn apply_syncs(self: &mut Galaxy, syncs: &Vec<SyncEntity>) {
        for sync in syncs {
            if let Some(fleet) = self.fleets.get_mut(&sync.id) {
                fleet.radius = sync.radius.unwrap_or(fleet.radius);
                fleet.ships = sync.ships.unwrap_or(fleet.ships);
                fleet.target = sync.target.unwrap_or(fleet.target);
                fleet.x = sync.x.unwrap_or(fleet.x);
                fleet.y = sync.y.unwrap_or(fleet.y);
            }
            if let Some(planet) = self.planets.get_mut(&sync.id) {
                planet.owner = sync.owner.unwrap_or(planet.owner);
                planet.ships = sync.ships.unwrap_or(planet.ships);
            }
        }
    }

    pub fn update(self: &mut Galaxy, command: ServerMessage) {
        match command {
            ServerMessage::Set(set_meta) => self.apply_meta(set_meta),
            ServerMessage::Reset => self.reset(),
            ServerMessage::User(user) => _ = self.users.insert(user.id, user),
            ServerMessage::Planet(planet) => _ = self.planets.insert(planet.id, planet),
            ServerMessage::Fleet(fleet) => _ = self.fleets.insert(fleet.id, fleet),
            ServerMessage::Sync(items) => self.apply_syncs(&items),
            ServerMessage::Destroy(id) => _ = self.fleets.remove(&id),
            _ => {}
        }
    }

    /// ships if e is aligned to us, otherwise -ships
    pub fn aligned_ships(self: &Galaxy, id: usize) -> f64 {
        if let Some(p) = self.planets.get(&id) {
            if p.owner == self.you {
                p.ships
            } else {
                -p.ships
            }
        } else if let Some(f) = self.fleets.get(&id) {
            if f.owner == self.you {
                f.ships
            } else {
                -f.ships
            }
        } else {
            panic!("requested aligned value for nonexistent id")
        }
    }

    pub fn aligned_production(self: &Galaxy, planet_id: usize, t: f64) -> f64 {
        let p = self
            .planets
            .get(&planet_id)
            .expect("requested production for a nonexistent planet");
        let o = self
            .users
            .get(&p.owner)
            .expect("a planet is owned by a nonexistent owner");

        if p.owner == self.you {
            return t * geom::PRODUCTION_RATE * p.production;
        } else if o.team == 0 {
            return 0.0;
        } else {
            return -t * geom::PRODUCTION_RATE * p.production;
        }
    }
}
