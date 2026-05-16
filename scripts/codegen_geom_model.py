import json


def farr(fs: list[float]):
    dat = ", ".join(map(str, fs))
    return f"[_]f64{{ {dat} }}"


def plist(ps: list[str]):
    return ", ".join([f"{p}: f64" for p in ps])


def dot(model_params, func_params):
    result = []
    for i, param in enumerate(model_params):
        muls = [f"{fp} * LM_C[{i}][{j}]" for j, fp in enumerate(func_params)]
        expr = " + ".join(muls + [f"LM_I[{i}];"])
        result.append(f"    const {param} = {expr}")
    return "\n".join(result)


if __name__ == "__main__":
    with open("scripts/model/params.json", "r") as fp:
        model = json.load(fp)

    coefs = [list(r["coefs"].values()) for r in model]
    intercepts = [r["intercept"] for r in model]
    params = list(model[0]["coefs"].keys())
    model_params = [r["param"] for r in model]
    p_list, mp_list = ", ".join(params), ", ".join(model_params)

    coef_rows = "\n".join([f"    {farr(cr)}," for cr in coefs])

    template = f"""
// Generated file -- modify via scripts/codegen_geom_model.py

const math = @import("std").math;

/// distance units / sec
pub const SHIP_SPEED = 40.0;

/// For each [{mp_list}], regress against [{p_list}] + intercept
const LM_C = [_][]f64{{
{coef_rows}
}};
const LM_I = {farr(intercepts)};

/// Model operates on normalized travel time by speed/distance
fn norm(t: f64, dist: f64) f64 {{
    return SHIP_SPEED * t / dist;
}}

/// Estimate the proportion of the fleet that's traveled from source to target at time t (relative to the fleet leaving)
pub fn logistic(t: f64, {plist(params)}) f64 {{
{dot(model_params, params)}

    return L / (1.0 * math.exp(-k * (norm(t, source_target_dist) - t0))) + b;
}}
    """
    with open("src/geom_model.zig", "w") as fp:
        fp.write(template.strip())
        fp.write("\n")
