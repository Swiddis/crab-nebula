use std::{
    collections::VecDeque,
    io::{self, BufWriter, Write},
};

use crate::{
    model::{self, Galaxy},
    proto::*,
};

use ordered_float::OrderedFloat;

struct Bid<'a> {
    value: OrderedFloat<f64>,
    requires: f64,
    expires: f64,
    target: &'a Planet,
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

    fn part_planets(self: &Engine) -> (Vec<&Planet>, Vec<&Planet>) {
        let our_planets: Vec<&Planet> = self
            .g
            .planets
            .values()
            .filter(|p| p.owner == self.g.you)
            .collect();
        let target_planets: Vec<&Planet> = self
            .g
            .planets
            .values()
            .filter(|p| p.owner != self.g.you)
            .collect();
        (our_planets, target_planets)
    }

    fn start_bids<'a>(self: &Engine, targets: &Vec<&'a Planet>) -> Vec<&'a Bid> {
        todo!();
    }

    fn go(self: &mut Engine) {
        let (our_planets, target_planets) = self.part_planets();
        let bids = self.start_bids(&target_planets);
    }
}
