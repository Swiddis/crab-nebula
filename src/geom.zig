//! Geometry for Galcon: primarily includes utilities for measuring travel time between planets

const proto = @import("proto.zig");
const model = @import("geom_model.zig");

pub const SHIP_SPEED = model.SHIP_SPEED;
/// ships / sec
pub const PRODUCTION_RATE = 1.0 / 50.0;

fn hypot(a: *proto.Planet, b: *proto.Planet) f64 {
    const dx = a.x - b.x;
    const dy = a.y - b.y;
    return @sqrt(dx * dx + dy * dy);
}

/// Laziest form of travel time estimation: assume ships fly directly from the center of planet A to planet B,
/// ignoring any navigation or flow dynamics.
pub fn direct_travel_time(a: *proto.Planet, b: *proto.Planet) f64 {
    return hypot(a, b) / SHIP_SPEED;
}

/// Estimate how much of a fleet of given size will travel from source to target after t seconds.
/// Current implementation is based on a logistic regression of ~336k fleets from historic game logs.
pub fn estimate_arrived(t: f64, fleet_size: f64, source: *proto.Planet, target: *proto.Planet) f64 {
    const dist = hypot(source, target);
    const prop = model.logistic(t, dist, source.r, target.r, fleet_size);
    return fleet_size * prop;
}
