// Generated file -- modify via scripts/codegen_geom_model.rs

use crate::geom::SHIP_SPEED;

/// For each [t0, k, L, b], regress against [source_target_dist, source_r, target_r, fleet_size] + intercept
#[rustfmt::skip]
const LM_C: [[f64; 4]; 4] = [
    [ 0.002371689729464756, -0.01175063275814122, -0.004677450433681569, -0.001769238215211349 ],
    [ 0.03072274917592544, -0.16347768857509365, 0.1255044242446921, -0.3384423086503297 ],
    [ -0.00018331717634889556, 0.00019362994587639144, 0.00046145019151840305, 0.00027186889711218665 ],
    [ 0.0001540268677457221, -0.0012762351705975653, 0.0005535754569780775, -0.0006045287971515022 ],
];

#[rustfmt::skip]
const LM_I: [f64; 4] = [ 0.5729724241422721, 17.187043418429347, 1.0405148201323577, -0.026545166796745227 ];

/// Model operates on normalized travel time by speed/distance
fn norm(t: f64, dist: f64) -> f64 {
    return SHIP_SPEED * t / dist;
}

fn unnorm(t: f64, dist: f64) -> f64 {
    return t * dist / SHIP_SPEED;
}

/// Estimate the proportion of the fleet that's traveled from source to target at time t (relative to the fleet leaving)
#[rustfmt::skip]
pub fn logistic(t: f64, source_target_dist: f64, source_r: f64, target_r: f64, fleet_size: f64) -> f64 {
    let t0 = source_target_dist * LM_C[0][0] + source_r * LM_C[0][1] + target_r * LM_C[0][2] + fleet_size * LM_C[0][3] + LM_I[0];
    let k = source_target_dist * LM_C[1][0] + source_r * LM_C[1][1] + target_r * LM_C[1][2] + fleet_size * LM_C[1][3] + LM_I[1];
    let l = source_target_dist * LM_C[2][0] + source_r * LM_C[2][1] + target_r * LM_C[2][2] + fleet_size * LM_C[2][3] + LM_I[2];
    let b = source_target_dist * LM_C[3][0] + source_r * LM_C[3][1] + target_r * LM_C[3][2] + fleet_size * LM_C[3][3] + LM_I[3];

    return l / (1.0 + (-k * (norm(t, source_target_dist) - t0)).exp()) + b;
}

#[rustfmt::skip]
pub fn inv_logistic(p: f64, source_target_dist: f64, source_r: f64, target_r: f64, fleet_size: f64) -> f64 {
    let t0 = source_target_dist * LM_C[0][0] + source_r * LM_C[0][1] + target_r * LM_C[0][2] + fleet_size * LM_C[0][3] + LM_I[0];
    let k = source_target_dist * LM_C[1][0] + source_r * LM_C[1][1] + target_r * LM_C[1][2] + fleet_size * LM_C[1][3] + LM_I[1];
    let l = source_target_dist * LM_C[2][0] + source_r * LM_C[2][1] + target_r * LM_C[2][2] + fleet_size * LM_C[2][3] + LM_I[2];
    let b = source_target_dist * LM_C[3][0] + source_r * LM_C[3][1] + target_r * LM_C[3][2] + fleet_size * LM_C[3][3] + LM_I[3];

    let kt = k * t0 - ((l + b - p) / (p - b)).ln();
    return unnorm(kt / k, source_target_dist);
}
