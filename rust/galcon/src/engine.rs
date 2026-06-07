use std::io::{self, BufRead, BufWriter, Write};
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread::{self, JoinHandle};

use crate::model::Galaxy;
use crate::proto::{ClientMessage, ServerMessage, parse_server_message};

pub trait Engine {
    fn handle(&mut self, message: &ServerMessage, galaxy: &Galaxy);
    fn pop_action(&mut self) -> Option<ClientMessage>;
}

pub fn start_input_thread(server_tx: Sender<ServerMessage>) -> JoinHandle<()> {
    thread::spawn(move || {
        let stdin = io::stdin();

        for line in stdin.lock().lines() {
            let Ok(line) = line else { return };
            let msg = match parse_server_message(&line) {
                Ok(msg) => msg,
                Err(e) => {
                    eprintln!("invalid message received from server: {e}");
                    continue;
                }
            };
            let Ok(_) = server_tx.send(msg) else { return };
        }
    })
}

pub fn start_output_thread(client_rx: Receiver<ClientMessage>) -> JoinHandle<()> {
    thread::spawn(move || {
        let stdout = io::stdout();
        let mut out = BufWriter::new(stdout.lock());

        while let Ok(action) = client_rx.recv() {
            if writeln!(out, "{}", action).is_err() {
                return;
            }
            if matches!(action, ClientMessage::Tock) && out.flush().is_err() {
                return;
            }
        }
    })
}

fn run_engine_loop(
    server_rx: Receiver<ServerMessage>,
    client_tx: Sender<ClientMessage>,
    mut engine: impl Engine,
) {
    let mut galaxy = Galaxy::new();

    while let Ok(message) = server_rx.recv() {
        galaxy.update(&message);
        engine.handle(&message, &galaxy);
        while let Some(action) = engine.pop_action() {
            let Ok(_) = client_tx.send(action) else {
                return;
            };
        }
    }
}

pub fn run_engine(engine: impl Engine) {
    let (client_tx, client_rx): (Sender<ClientMessage>, Receiver<ClientMessage>) = mpsc::channel();
    let (server_tx, server_rx): (Sender<ServerMessage>, Receiver<ServerMessage>) = mpsc::channel();

    let in_handle = start_input_thread(server_tx);
    let out_handle = start_output_thread(client_rx);
    run_engine_loop(server_rx, client_tx, engine);

    in_handle.join().expect("input thread panicked");
    out_handle.join().expect("output thread panicked");
}
