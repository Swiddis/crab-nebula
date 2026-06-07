use galcon::model::Galaxy;
use macroquad::prelude::*;
mod nebula;

use std::sync::mpsc::{self, Receiver, Sender};

use galcon::{engine::*, proto::*};

use crate::nebula::Nebula;

fn hex_to_rgb(hex: &str) -> Result<(u8, u8, u8), std::num::ParseIntError> {
    let r = u8::from_str_radix(&hex[0..2], 16)?;
    let g = u8::from_str_radix(&hex[2..4], 16)?;
    let b = u8::from_str_radix(&hex[4..6], 16)?;
    Ok((r, g, b))
}

fn transform(x: f64, y: f64) -> (f32, f32) {
    (
        2.0 * x as f32 + screen_width() * 0.5,
        -2.0 * y as f32 + screen_height() * 0.5,
    )
}

// intersect the circle (p1, r) with the line (p1, p2)
fn circle_intersect(x1: f32, y1: f32, x2: f32, y2: f32, r: f32) -> (f32, f32) {
    let theta = (y2 - y1).atan2(x2 - x1);
    (x1 + r * theta.cos(), y1 + r * theta.sin())
}

fn draw_galaxy(galaxy: &Galaxy) {
    let imap = galaxy.ingress_map();

    for planet in galaxy.planets.values() {
        let user = galaxy.users.get(&planet.owner).unwrap();
        let (r, g, b) = hex_to_rgb(&user.color).unwrap();
        let (x, y) = transform(planet.x, planet.y);
        let color = Color::from_rgba(r, g, b, 255);
        draw_circle(x, y, 2.0 * planet.radius as f32, color);

        if let Some(inbound) = imap.get(&planet.id) {
            let mut ships = planet.ships;
            let mut opp = 0;
            for fleet in inbound {
                if fleet.owner == planet.owner {
                    ships += fleet.ships;
                } else {
                    opp = fleet.owner;
                    ships -= fleet.ships;
                }
            }
            if ships < 0.0 {
                // TODO: we don't track opponent ID directly in galaxy which makes this referencing hard
                // Should add some sort of tracking in galaxy like how we do for `base`
                let opp_color = galaxy.users.get(&opp).unwrap().color.clone();
                let (r, g, b) = hex_to_rgb(&opp_color).unwrap();
                let color = Color::from_rgba(r, g, b, 255);
                draw_circle_lines(x, y, 2.0 * planet.radius as f32, 3.0, color);
            }
        }
    }

    for fleet in galaxy.fleets.values() {
        let user = galaxy.users.get(&fleet.owner).unwrap();
        let target = galaxy.planets.get(&fleet.target).unwrap();
        let (r, g, b) = hex_to_rgb(&user.color).unwrap();
        let (x, y) = transform(fleet.x, fleet.y);
        let radius = 2.0 * fleet.radius as f32;
        let color = Color::from_rgba(r, g, b, 255);
        draw_circle_lines(x, y, radius, 3.0, color);

        let (target_x, target_y) = transform(target.x, target.y);
        let (ix, iy) = circle_intersect(x, y, target_x, target_y, radius);
        let (ox, oy) = circle_intersect(target_x, target_y, x, y, 2.0 * target.radius as f32);
        draw_line(ix, iy, ox, oy, 3.0, color);
    }
}

async fn run_engine_loop(
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

        if matches!(message, ServerMessage::Tick(_)) {
            clear_background(BLACK);
            draw_galaxy(&galaxy);
            next_frame().await;
        }
    }
}

#[macroquad::main("Nebula")]
async fn main() {
    let engine = Nebula::new();
    let (client_tx, client_rx): (Sender<ClientMessage>, Receiver<ClientMessage>) = mpsc::channel();
    let (server_tx, server_rx): (Sender<ServerMessage>, Receiver<ServerMessage>) = mpsc::channel();

    let in_handle = start_input_thread(server_tx);
    let out_handle = start_output_thread(client_rx);
    run_engine_loop(server_rx, client_tx, engine).await;

    in_handle.join().expect("input thread panicked");
    out_handle.join().expect("output thread panicked");
}
