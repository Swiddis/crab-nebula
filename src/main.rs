mod engine;
mod geom;
mod model;
mod proto;

use std::io::{self, BufRead, BufWriter, Write};
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread::{self, JoinHandle};

use crate::engine::Engine;
use crate::proto::{ClientMessage, ServerMessage, parse_server_message};

fn start_input_thread(server_tx: Sender<ServerMessage>) -> JoinHandle<()> {
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

fn start_output_thread(client_rx: Receiver<ClientMessage>) -> JoinHandle<()> {
    thread::spawn(move || {
        let stdout = io::stdout();
        let mut out = BufWriter::new(stdout.lock());

        while let Ok(action) = client_rx.recv() {
            if writeln!(out, "{}", action.to_string()).is_err() {
                return;
            }
            if matches!(action, ClientMessage::Tock) && out.flush().is_err() {
                return;
            }
        }
    })
}

fn run_engine_loop(server_rx: Receiver<ServerMessage>, client_tx: Sender<ClientMessage>) {
    let mut engine = Engine::new();
    while let Ok(message) = server_rx.recv() {
        engine.handle(message);
        while let Some(action) = engine.action_queue.pop_front() {
            let Ok(_) = client_tx.send(action) else {
                return;
            };
        }
    }
}

fn main() {
    let (client_tx, client_rx): (Sender<ClientMessage>, Receiver<ClientMessage>) = mpsc::channel();
    let (server_tx, server_rx): (Sender<ServerMessage>, Receiver<ServerMessage>) = mpsc::channel();

    let in_handle = start_input_thread(server_tx);
    let out_handle = start_output_thread(client_rx);
    run_engine_loop(server_rx, client_tx);

    in_handle.join().expect("input thread panicked");
    out_handle.join().expect("output thread panicked");
}
