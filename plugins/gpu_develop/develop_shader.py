"""The WGSL compute shader that runs the basic develop stages on the GPU.

One invocation per pixel, pixels packed as ``u32`` (R in the low byte, alpha
kept). The per-channel stages are table lookups (``params.py`` builds the
tables with the CPU code); highlights/shadows, vibrance and saturation repeat
``Imervue.image.recipe_adjustments`` and Pillow's ``ImageEnhance.Color`` in
single precision and end, like the CPU, by clamping and truncating to a byte.
Divisions go through ``div``, which corrects the GPU's approximate quotient
to the one NumPy computes. Which stages run is the ``flags`` word (the bits of
``params.py``); with ``LUMA_SUMS`` each invocation also adds Pillow's integer
luminance of its result to its workgroup's entry of ``sums``, which the host
clears before the dispatch. The workgroup's linear index comes from the
``groups_x`` the host passes, not from ``num_workgroups``, and the shader uses no
workgroup memory or barrier: with them, one D3D12 driver skipped every pixel.
"""
from __future__ import annotations

WORKGROUP_SIZE = 256

SHADER = """
struct Params {
    count: u32, flags: u32, groups_x: u32, pad0: u32,
    highlights: f32, shadows: f32, vibrance: f32, saturation: f32,
};

@group(0) @binding(0) var<storage, read_write> pixels: array<u32>;
@group(0) @binding(1) var<uniform> P: Params;
@group(0) @binding(2) var<storage, read> tables: array<u32>;
@group(0) @binding(3) var<storage, read_write> sums: array<atomic<u32>>;

fn div(a: f32, b: f32) -> f32 {
    let q = a / b;
    return q + fma(-q, b, a) / b;
}

fn lookup(c: vec3<u32>, table: u32) -> vec3<u32> {
    let base = table * 768u;
    return vec3<u32>(tables[base + c.x], tables[base + 256u + c.y], tables[base + 512u + c.z]);
}

fn unit(c: vec3<u32>) -> vec3<f32> {
    return vec3<f32>(bitcast<f32>(tables[2304u + c.x]), bitcast<f32>(tables[2304u + c.y]),
                     bitcast<f32>(tables[2304u + c.z]));
}

fn to_byte(v: vec3<f32>) -> vec3<u32> {
    return vec3<u32>(clamp(v, vec3<f32>(0.0), vec3<f32>(255.0)));
}

fn pil_luma(c: vec3<u32>) -> u32 {
    return (c.x * 19595u + c.y * 38470u + c.z * 7471u + 32768u) >> 16u;
}

fn highlights_shadows(c: vec3<u32>) -> vec3<u32> {
    let f = vec3<f32>(c);
    let luma = div(0.2126 * f.x + 0.7152 * f.y + 0.0722 * f.z, 255.0);
    let shadow_gain = 1.0 + P.shadows * (1.0 - luma) * 0.8;
    let highlight_gain = 1.0 + P.highlights * luma * 0.8;
    return to_byte(f * (shadow_gain * highlight_gain));
}

fn vibrance(c: vec3<u32>) -> vec3<u32> {
    let v = unit(c);
    let top = max(max(v.x, v.y), v.z);
    let bottom = min(min(v.x, v.y), v.z);
    var sat = 0.0;
    if (top > 0.0) {
        sat = div(top - bottom, max(top, 1e-6));
    }
    let gain = 1.0 + P.vibrance * (1.0 - sat);
    let gray = div(v.x + v.y + v.z, 3.0);
    let moved = gray + (v - gray) * gain;
    return vec3<u32>(clamp(moved, vec3<f32>(0.0), vec3<f32>(1.0)) * 255.0);
}

fn saturation(c: vec3<u32>) -> vec3<u32> {
    let grey = f32(pil_luma(c));
    return to_byte(grey + P.saturation * (vec3<f32>(c) - grey));
}

fn develop(c_in: vec3<u32>, flags: u32) -> vec3<u32> {
    var c = c_in;
    if ((flags & 1u) != 0u) { c = lookup(c, 0u); }
    if ((flags & 2u) != 0u) { c = highlights_shadows(c); }
    if ((flags & 4u) != 0u) { c = lookup(c, 1u); }
    if ((flags & 8u) != 0u) { c = vibrance(c); }
    if ((flags & 16u) != 0u) { c = saturation(c); }
    if ((flags & 32u) != 0u) { c = lookup(c, 2u); }
    return c;
}

@compute @workgroup_size(256)
fn main(@builtin(workgroup_id) wid: vec3<u32>, @builtin(local_invocation_index) lid: u32) {
    let group = wid.y * P.groups_x + wid.x;
    let index = group * 256u + lid;
    if (index >= P.count) {
        return;
    }
    let packed = pixels[index];
    let c = vec3<u32>(packed & 255u, (packed >> 8u) & 255u, (packed >> 16u) & 255u);
    let d = develop(c, P.flags);
    pixels[index] = d.x | (d.y << 8u) | (d.z << 16u) | (packed & 0xff000000u);
    if ((P.flags & 64u) != 0u) {
        atomicAdd(&sums[group], pil_luma(d));
    }
}
"""
