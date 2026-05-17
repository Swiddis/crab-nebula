use crate::proto;
mod model;

const SHIP_SPEED: f64 = 40.;
/// ships / sec
const PRODUCTION_RATE: f64 = 1. / 50.;

pub fn hypot(a: &proto::Planet, b: &proto::Planet) -> f64 {
    let dx = a.x - b.x;
    let dy = a.y - b.y;
    return (dx * dx + dy * dy).sqrt();
}

/// Laziest form of travel time estimation: assume ships fly directly from the center of planet A to planet B,
/// ignoring any navigation or flow dynamics.
pub fn direct_travel_time(a: &proto::Planet, b: &proto::Planet) -> f64 {
    return hypot(a, b) / SHIP_SPEED;
}

/// Estimate how much of a fleet of given size will travel from source to target after t seconds.
/// Current implementation is based on a logistic regression of ~336k fleets from historic game logs.
pub fn estimate_arrived(
    t: f64,
    fleet_size: f64,
    source: &proto::Planet,
    target: &proto::Planet,
) -> f64 {
    let dist = hypot(source, target);
    let prop = model::logistic(t, dist, source.radius, target.radius, fleet_size);
    return fleet_size * prop;
}
