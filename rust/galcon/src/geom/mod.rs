use crate::proto;
mod model;

// units / sec
pub const SHIP_SPEED: f64 = 40.;
/// ships / sec
pub const PRODUCTION_RATE: f64 = 1. / 50.;

pub fn hypot(a: &proto::Planet, b: &proto::Planet) -> f64 {
    let dx = a.x - b.x;
    let dy = a.y - b.y;
    (dx * dx + dy * dy).sqrt()
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
    fleet_size * prop
}

/// Estimate time before the given proportion of the fleet reaches the target
pub fn eta(prop: f64, fleet_size: f64, source: &proto::Planet, target: &proto::Planet) -> f64 {
    let dist = hypot(source, target);
    model::inv_logistic(prop, dist, source.radius, target.radius, fleet_size)
}
