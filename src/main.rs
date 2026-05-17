mod engine;
// mod geom;
mod model;
mod proto;

use std::io::{self, BufRead};

use crate::engine::Engine;

fn main() -> io::Result<()> {
    let stdin = io::stdin();
    let mut engine = Engine::new();

    for line in stdin.lock().lines() {
        match proto::parse_server_message(&line?) {
            Ok(msg) => engine.handle(msg)?,
            Err(e) => eprintln!("parse error: {}", e),
        }
    }

    Ok(())
}
