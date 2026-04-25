#!/usr/bin/env python3
"""
visualize.py — Generate SVG plots for the Dynamic Thermo-Elastic Mesh Simulation.
Uses only Python stdlib + numpy (no matplotlib required).

Usage:
    python3 scripts/visualize.py --heatmap results/heatmaps/heatmap_hotspot1.csv
    python3 scripts/visualize.py --speedup results/benchmark.csv
    python3 scripts/visualize.py --iso3d results/heatmaps/heatmap_hotspot1.csv
    python3 scripts/visualize.py --profile results/heatmaps/heatmap_hotspot1.csv
    python3 scripts/visualize.py --scheduling results/ghc_benchmark.csv
    python3 scripts/visualize.py --load-balance results/ghc_benchmark.csv --pattern hotspot4
    python3 scripts/visualize.py --flat-vs-3d results/flat.csv results/3d.csv
    python3 scripts/visualize.py --all
    python3 scripts/visualize.py --all-ghc
    python3 scripts/visualize.py --all-psc

Outputs SVG files to results/ directory.
"""

import argparse
import csv
import os
import sys
import math
from collections import defaultdict
from typing import List, Tuple, Optional, Dict

import subprocess

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# Detect rsvg-convert (fastest SVG→PNG) or inkscape as fallback
_SVG2PNG_CMD = None
for cmd in ['rsvg-convert', 'inkscape']:
    try:
        subprocess.run([cmd, '--version'], capture_output=True, check=True)
        _SVG2PNG_CMD = cmd
        break
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass


# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------

def clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))

def lerp_color(t: float, c0: Tuple, c1: Tuple) -> Tuple:
    return tuple(int(a + (b - a) * t) for a, b in zip(c0, c1))

def hot_colormap(t: float) -> Tuple[int, int, int]:
    """Approximate matplotlib 'hot' colormap: black -> red -> yellow -> white."""
    t = clamp01(t)
    if t < 1/3:
        s = t * 3
        return (int(255 * s), 0, 0)
    elif t < 2/3:
        s = (t - 1/3) * 3
        return (255, int(255 * s), 0)
    else:
        s = (t - 2/3) * 3
        return (255, 255, int(255 * s))

def rdbu_colormap(t: float) -> Tuple[int, int, int]:
    """RdBu_r colormap: blue (t=0) -> white (t=0.5) -> red (t=1)."""
    t = clamp01(t)
    blue = (33, 102, 172)
    white = (247, 247, 247)
    red = (178, 24, 43)
    if t < 0.5:
        s = t * 2
        return lerp_color(s, blue, white)
    else:
        s = (t - 0.5) * 2
        return lerp_color(s, white, red)

def viridis_colormap(t: float) -> Tuple[int, int, int]:
    """Approximate viridis: purple -> blue -> green -> yellow."""
    stops = [
        (68,  1,  84),
        (59, 82, 139),
        (33, 145, 140),
        (94, 201,  98),
        (253, 231,  37),
    ]
    t = clamp01(t)
    idx = t * (len(stops) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(stops) - 1)
    s = idx - lo
    return lerp_color(s, stops[lo], stops[hi])

def rgb_hex(r: int, g: int, b: int) -> str:
    return f'#{r:02x}{g:02x}{b:02x}'

def svg_to_png(svg_path: str, png_path: str, width: int = 1200):
    """Convert SVG to PNG using rsvg-convert or inkscape."""
    if _SVG2PNG_CMD == 'rsvg-convert':
        subprocess.run(['rsvg-convert', '-w', str(width), '-o', png_path, svg_path],
                       check=True, capture_output=True)
    elif _SVG2PNG_CMD == 'inkscape':
        subprocess.run(['inkscape', f'--export-filename={png_path}',
                        f'--export-width={width}', svg_path],
                       check=True, capture_output=True)
    else:
        pass  # no converter available


def save_svg(svg: str, path: str) -> str:
    """Save SVG to disk and convert to PNG. Returns the PNG path."""
    # Always save SVG for lossless archival
    with open(path, 'w') as f:
        f.write(svg)
    # Also save PNG (user preference: PNG output)
    png_path = path.replace('.svg', '.png')
    if _SVG2PNG_CMD:
        try:
            svg_to_png(path, png_path)
            print(f"Saved: {png_path}")
        except Exception as e:
            print(f"Saved: {path} (PNG conversion failed: {e})")
    else:
        print(f"Saved: {path} (no SVG→PNG converter; install rsvg-convert)")
    return png_path


# ---------------------------------------------------------------------------
# SVG heatmap (top-down 2D view)
# ---------------------------------------------------------------------------

def svg_heatmap(grid_2d: list, colormap_fn, title: str, legend_label: str,
                cell_px: int = 5) -> str:
    """Generate SVG heatmap from a 2D list of normalized (0..1) values."""
    rows = len(grid_2d)
    cols = len(grid_2d[0])
    margin = 60
    legend_w = 80
    W = cols * cell_px + 2 * margin + legend_w
    H = rows * cell_px + 2 * margin

    rects = []
    for r in range(rows):
        for c in range(cols):
            v = grid_2d[r][c]
            color = colormap_fn(v)
            x = margin + c * cell_px
            y = margin + (rows - 1 - r) * cell_px  # flip y so row 0 is bottom
            rects.append(
                f'<rect x="{x}" y="{y}" width="{cell_px}" height="{cell_px}" '
                f'fill="{rgb_hex(*color)}" />'
            )

    # Color legend (gradient bar)
    legend_x = margin + cols * cell_px + 15
    legend_h = rows * cell_px
    legend_steps = 20
    legend_rects = []
    for i in range(legend_steps):
        t = 1.0 - i / (legend_steps - 1)
        color = colormap_fn(t)
        ly = margin + int(i * legend_h / legend_steps)
        lh = max(1, int(legend_h / legend_steps) + 1)
        legend_rects.append(
            f'<rect x="{legend_x}" y="{ly}" width="18" height="{lh}" '
            f'fill="{rgb_hex(*color)}" />'
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">
  <rect width="{W}" height="{H}" fill="white"/>
  <text x="{W//2}" y="30" text-anchor="middle" font-size="14" font-weight="bold">{title}</text>
  {''.join(rects)}
  {''.join(legend_rects)}
  <text x="{legend_x + 22}" y="{margin}" font-size="9" dominant-baseline="middle">max</text>
  <text x="{legend_x + 22}" y="{margin + legend_h}" font-size="9" dominant-baseline="middle">min</text>
  <text x="{legend_x + 10}" y="{margin + legend_h + 20}" font-size="9" text-anchor="middle"
        transform="rotate(90 {legend_x + 10} {margin + legend_h//2})">{legend_label}</text>
  <text x="{margin}" y="{H - 10}" font-size="10">Col →</text>
  <text x="10" y="{margin + legend_h//2}" font-size="10"
        transform="rotate(-90 10 {margin + legend_h//2})">Row →</text>
</svg>'''
    return svg


def load_heatmap_csv(csv_path: str):
    """Load heatmap CSV; returns (rows_n, cols_n, T_grid, z_grid, type_grid)."""
    with open(csv_path) as f:
        records = list(csv.DictReader(f))
    if not records:
        raise ValueError(f"Empty heatmap file: {csv_path}")
    rows_n = max(int(r['row']) for r in records) + 1
    cols_n = max(int(r['col']) for r in records) + 1
    T_grid = [[0.0]*cols_n for _ in range(rows_n)]
    z_grid = [[0.0]*cols_n for _ in range(rows_n)]
    type_grid = [[0]*cols_n for _ in range(rows_n)]
    for rec in records:
        rr, cc = int(rec['row']), int(rec['col'])
        T_grid[rr][cc] = float(rec['T'])
        z_grid[rr][cc] = float(rec['z'])
        type_grid[rr][cc] = int(rec.get('type', 0))
    return rows_n, cols_n, T_grid, z_grid, type_grid


def plot_heatmap(csv_path: str, out_prefix: str = None):
    rows_n, cols_n, T_vals, z_vals, _ = load_heatmap_csv(csv_path)

    T_min = min(T_vals[r][c] for r in range(rows_n) for c in range(cols_n))
    T_max = max(T_vals[r][c] for r in range(rows_n) for c in range(cols_n))
    T_range = T_max - T_min if T_max > T_min else 1.0

    z_min = min(z_vals[r][c] for r in range(rows_n) for c in range(cols_n))
    z_max = max(z_vals[r][c] for r in range(rows_n) for c in range(cols_n))
    z_abs_max = max(abs(z_min), abs(z_max), 1e-9)

    T_norm = [[(T_vals[r][c] - T_min) / T_range for c in range(cols_n)] for r in range(rows_n)]
    z_norm = [[(z_vals[r][c] + z_abs_max) / (2 * z_abs_max) for c in range(cols_n)] for r in range(rows_n)]

    if out_prefix is None:
        base = os.path.splitext(os.path.basename(csv_path))[0]
        out_prefix = os.path.join(RESULTS_DIR, base)

    cell_px = max(2, min(8, 600 // max(rows_n, cols_n)))

    svg = svg_heatmap(T_norm, hot_colormap,
                      f'Temperature Distribution ({rows_n}×{cols_n}) — T_max={T_max:.1f}K',
                      'Temperature (K)', cell_px)
    save_svg(svg, out_prefix + '_T.svg')

    svg = svg_heatmap(z_norm, rdbu_colormap,
                      f'3D Out-of-Plane Buckling ({rows_n}×{cols_n}) — z_max={z_max:.4f}',
                      'Z-displacement', cell_px)
    save_svg(svg, out_prefix + '_z.svg')


# ---------------------------------------------------------------------------
# Isometric 3D surface view — the "money shot" for 3D buckling
# ---------------------------------------------------------------------------

def iso_project(gx: float, gy: float, gz: float,
                cx: float, cy: float,
                scale: float, z_scale: float) -> Tuple[float, float]:
    """
    Isometric projection: world (gx, gy, gz) → screen (sx, sy).
    gx/gy are grid column/row, gz is z-displacement.
    """
    angle = math.radians(30)
    sx = (gx - gy) * math.cos(angle) * scale + cx
    sy = (gx + gy) * math.sin(angle) * scale - gz * z_scale + cy
    return sx, sy


def plot_iso3d(csv_path: str, out_prefix: str = None, z_amplify: float = 80.0):
    """
    Generate an isometric 3D surface view showing out-of-plane buckling.
    Each cell is drawn as a filled parallelogram. Cells sorted back-to-front
    (painter's algorithm). Colored by temperature (hot colormap).
    """
    rows_n, cols_n, T_grid, z_grid, type_grid = load_heatmap_csv(csv_path)

    T_min = min(T_grid[r][c] for r in range(rows_n) for c in range(cols_n))
    T_max = max(T_grid[r][c] for r in range(rows_n) for c in range(cols_n))
    T_range = T_max - T_min if T_max > T_min else 1.0
    z_max = max(abs(z_grid[r][c]) for r in range(rows_n) for c in range(cols_n))

    # Canvas sizing
    W, H = 800, 600
    scale = min(300.0 / max(rows_n, cols_n), 8.0)
    cx = W // 2
    cy = H // 3

    # Sort cells back-to-front in isometric view (larger col+row = closer to viewer)
    cell_order = sorted(
        [(r, c) for r in range(rows_n) for c in range(cols_n)],
        key=lambda rc: rc[0] + rc[1]
    )

    polys = []
    for r, c in cell_order:
        gz = z_grid[r][c]
        t_norm = (T_grid[r][c] - T_min) / T_range
        color = hot_colormap(t_norm)
        # 4 corners of this cell in grid space (col, row order for x, y)
        corners_gxy = [(c, r), (c+1, r), (c+1, r+1), (c, r+1)]
        # Use the cell's z for all corners (simplified — looks good for visualization)
        pts = [iso_project(gx, gy, gz, cx, cy, scale, z_amplify)
               for gx, gy in corners_gxy]
        pts_str = ' '.join(f'{px:.1f},{py:.1f}' for px, py in pts)
        # Slightly darker edge to show grid structure
        edge = rgb_hex(max(0, color[0]-30), max(0, color[1]-30), max(0, color[2]-30))
        polys.append(
            f'<polygon points="{pts_str}" fill="{rgb_hex(*color)}" '
            f'stroke="{edge}" stroke-width="0.3"/>'
        )

    # Axes labels and annotations
    o_pt = iso_project(0, rows_n, 0, cx, cy, scale, z_amplify)
    x_pt = iso_project(cols_n, rows_n, 0, cx, cy, scale, z_amplify)
    y_pt = iso_project(0, 0, 0, cx, cy, scale, z_amplify)
    z_pt = iso_project(0, rows_n, z_max * z_amplify / scale, cx, cy, scale, z_amplify)

    annotations = (
        f'<text x="{x_pt[0]:.0f}" y="{x_pt[1]+14:.0f}" text-anchor="middle" '
        f'font-size="11" fill="#555">Column →</text>'
        f'<text x="{y_pt[0]-8:.0f}" y="{y_pt[1]:.0f}" text-anchor="end" '
        f'font-size="11" fill="#555">← Row</text>'
        f'<text x="{o_pt[0]:.0f}" y="{o_pt[1]+14:.0f}" text-anchor="middle" '
        f'font-size="9" fill="#888">(0,0)</text>'
    )

    # Stats box
    stats = (
        f'<text x="10" y="20" font-size="10" fill="#333">T_max = {T_max:.1f} K</text>'
        f'<text x="10" y="34" font-size="10" fill="#333">T_min = {T_min:.1f} K</text>'
        f'<text x="10" y="48" font-size="10" fill="#333">z_max = {z_max:.4f}</text>'
        f'<text x="10" y="62" font-size="10" fill="#333">Mesh: {rows_n}×{cols_n}</text>'
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">'
        f'<rect width="{W}" height="{H}" fill="#f8f8f8"/>'
        f'<text x="{W//2}" y="22" text-anchor="middle" font-size="14" font-weight="bold">'
        f'3D Thermo-Elastic Buckling — Isometric View</text>'
        + ''.join(polys)
        + annotations + stats +
        f'</svg>'
    )

    if out_prefix is None:
        base = os.path.splitext(os.path.basename(csv_path))[0]
        out_prefix = os.path.join(RESULTS_DIR, base)

    save_svg(svg, out_prefix + '_iso3d.svg')


# ---------------------------------------------------------------------------
# Z-displacement profile (center-row cross-section)
# ---------------------------------------------------------------------------

def plot_profile(csv_path: str, out_prefix: str = None):
    """
    Plot z-displacement and temperature along the center row/column as a
    2-panel line chart. Shows the 'dome' shape caused by hotspot buckling.
    """
    rows_n, cols_n, T_grid, z_grid, _ = load_heatmap_csv(csv_path)

    center_r = rows_n // 2
    center_c = cols_n // 2
    cols_range = list(range(cols_n))
    rows_range = list(range(rows_n))

    z_row = [z_grid[center_r][c] for c in cols_range]
    T_row = [T_grid[center_r][c] for c in cols_range]
    z_col = [z_grid[r][center_c] for r in rows_range]
    T_col = [T_grid[r][center_c] for r in rows_range]

    W, H = 700, 400
    margin = {'top': 45, 'right': 20, 'bottom': 55, 'left': 70}
    pw = (W - margin['left'] - margin['right']) // 2 - 20
    ph = H - margin['top'] - margin['bottom']

    def panel(xs, z_vals, T_vals, title, ox, oy):
        """Draw a two-line (z + T) chart in a panel at screen offset (ox, oy)."""
        z_min_v, z_max_v = min(z_vals), max(z_vals)
        T_min_v, T_max_v = min(T_vals), max(T_vals)
        x_min, x_max = xs[0], xs[-1]

        def sc_x(v):
            if x_max == x_min: return ox
            return ox + (v - x_min) / (x_max - x_min) * pw

        def sc_z(v):
            rng = z_max_v - z_min_v if z_max_v != z_min_v else 1.0
            return oy + ph - (v - z_min_v) / rng * ph

        def sc_T(v):
            rng = T_max_v - T_min_v if T_max_v != T_min_v else 1.0
            return oy + ph - (v - T_min_v) / rng * ph * 0.8 - ph * 0.1

        z_path = 'M' + ' L'.join(f'{sc_x(xs[i]):.1f},{sc_z(z_vals[i]):.1f}' for i in range(len(xs)))
        T_path = 'M' + ' L'.join(f'{sc_x(xs[i]):.1f},{sc_T(T_vals[i]):.1f}' for i in range(len(xs)))

        # Zero line for z
        zero_y = sc_z(0.0)
        items = [
            f'<rect x="{ox}" y="{oy}" width="{pw}" height="{ph}" fill="white" stroke="#ccc"/>',
            f'<line x1="{ox}" y1="{zero_y:.1f}" x2="{ox+pw}" y2="{zero_y:.1f}" '
            f'stroke="#ddd" stroke-dasharray="4,2"/>',
            f'<path d="{z_path}" stroke="#e74c3c" fill="none" stroke-width="2"/>',
            f'<path d="{T_path}" stroke="#3498db" fill="none" stroke-width="1.5" stroke-dasharray="6,3"/>',
            f'<text x="{ox + pw//2}" y="{oy - 8}" text-anchor="middle" font-size="11" font-weight="bold">{title}</text>',
            f'<text x="{ox - 5}" y="{oy + ph//2}" text-anchor="end" font-size="9" fill="#e74c3c"'
            f' transform="rotate(-90 {ox-5} {oy+ph//2})">z-displacement</text>',
            f'<text x="{ox + pw//2}" y="{oy + ph + 14}" text-anchor="middle" font-size="10">Index</text>',
            # y-axis labels
            f'<text x="{ox-3}" y="{oy+4}" text-anchor="end" font-size="8">{z_max_v:.3f}</text>',
            f'<text x="{ox-3}" y="{oy+ph}" text-anchor="end" font-size="8">{z_min_v:.3f}</text>',
        ]
        return ''.join(items)

    p1 = panel(cols_range, z_row, T_row, f'Center Row (r={center_r})',
               margin['left'], margin['top'])
    p2 = panel(rows_range, z_col, T_col, f'Center Column (c={center_c})',
               margin['left'] + pw + 40, margin['top'])

    legend = (
        f'<line x1="{W//2-60}" y1="{H-12}" x2="{W//2-40}" y2="{H-12}" '
        f'stroke="#e74c3c" stroke-width="2"/>'
        f'<text x="{W//2-36}" y="{H-8}" font-size="10">z-displacement</text>'
        f'<line x1="{W//2+40}" y1="{H-12}" x2="{W//2+60}" y2="{H-12}" '
        f'stroke="#3498db" stroke-width="2" stroke-dasharray="6,3"/>'
        f'<text x="{W//2+64}" y="{H-8}" font-size="10">Temperature (K)</text>'
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">'
        f'<rect width="{W}" height="{H}" fill="white"/>'
        f'<text x="{W//2}" y="22" text-anchor="middle" font-size="13" font-weight="bold">'
        f'Buckling Profile — Cross-Section Through Hotspot</text>'
        + p1 + p2 + legend +
        f'</svg>'
    )

    if out_prefix is None:
        base = os.path.splitext(os.path.basename(csv_path))[0]
        out_prefix = os.path.join(RESULTS_DIR, base)
    save_svg(svg, out_prefix + '_profile.svg')


# ---------------------------------------------------------------------------
# Flat vs 3D temperature difference
# ---------------------------------------------------------------------------

def plot_flat_vs_3d(flat_csv: str, d3_csv: str, out_prefix: str = None):
    """
    Overlay two heatmap CSVs (flat mode and 3D mode) and show the temperature
    difference. Positive = 3D is hotter than flat (feedback increases conductance).
    """
    rows_n, cols_n, T_flat, _, _ = load_heatmap_csv(flat_csv)
    _, _, T_3d, _, _ = load_heatmap_csv(d3_csv)

    delta = [[T_3d[r][c] - T_flat[r][c] for c in range(cols_n)] for r in range(rows_n)]
    d_min = min(delta[r][c] for r in range(rows_n) for c in range(cols_n))
    d_max = max(delta[r][c] for r in range(rows_n) for c in range(cols_n))
    d_abs = max(abs(d_min), abs(d_max), 1e-9)
    d_norm = [[(delta[r][c] + d_abs) / (2 * d_abs) for c in range(cols_n)] for r in range(rows_n)]

    cell_px = max(2, min(8, 600 // max(rows_n, cols_n)))
    svg = svg_heatmap(d_norm, rdbu_colormap,
                      f'Temperature Δ: 3D minus Flat (d_max={d_max:.4f} K)',
                      'ΔT (K)', cell_px)

    if out_prefix is None:
        out_prefix = os.path.join(RESULTS_DIR, 'flat_vs_3d')
    save_svg(svg, out_prefix + '.svg')
    print(f"  ΔT range: [{d_min:.4f}, {d_max:.4f}] K — "
          f"{'3D feedback reduces temp' if d_max < 0 else '3D feedback raises temp'}")


# ---------------------------------------------------------------------------
# SVG line chart (reusable)
# ---------------------------------------------------------------------------

def svg_linechart(series: dict, title: str, xlabel: str, ylabel: str,
                  ideal_line: bool = True, W: int = 560, H: int = 400) -> str:
    """series = {label: [(x, y), ...]}"""
    margin = {'top': 40, 'right': 20, 'bottom': 60, 'left': 70}
    plot_w = W - margin['left'] - margin['right']
    plot_h = H - margin['top'] - margin['bottom']

    all_x = [x for pts in series.values() for x, y in pts]
    all_y = [y for pts in series.values() for x, y in pts]
    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = 0, max(all_y) * 1.1
    if ideal_line:
        y_max = max(y_max, x_max * 1.05)

    def px(xv, yv):
        sx = margin['left'] + (xv - x_min) / (x_max - x_min) * plot_w
        sy = margin['top'] + plot_h - (yv - y_min) / (y_max - y_min) * plot_h
        return sx, sy

    palette = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c',
               '#e67e22', '#16a085']
    lines = []
    legend_items = []

    if ideal_line:
        p1 = px(x_min, x_min)
        p2 = px(x_max, x_max)
        lines.append(
            f'<line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" '
            f'x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" '
            f'stroke="#aaa" stroke-dasharray="6,3" stroke-width="1.5"/>'
        )
        legend_items.append(('<line x1="0" y1="6" x2="20" y2="6" stroke="#aaa" '
                              'stroke-dasharray="6,3" stroke-width="1.5"/>', 'Ideal linear'))

    for i, (label, pts) in enumerate(series.items()):
        color = palette[i % len(palette)]
        pts_sorted = sorted(pts)
        path_d = ' '.join(
            f'{"M" if j == 0 else "L"}{px(x, y)[0]:.1f},{px(x, y)[1]:.1f}'
            for j, (x, y) in enumerate(pts_sorted)
        )
        lines.append(f'<path d="{path_d}" stroke="{color}" fill="none" stroke-width="2"/>')
        dots = ''.join(
            f'<circle cx="{px(x,y)[0]:.1f}" cy="{px(x,y)[1]:.1f}" r="4" fill="{color}"/>'
            for x, y in pts_sorted
        )
        lines.append(dots)
        legend_items.append((f'<line x1="0" y1="6" x2="20" y2="6" stroke="{color}" stroke-width="2"/>',
                              label))

    # Axes
    ox, oy = px(x_min, y_min)
    ax_path = (f'M{margin["left"]:.1f},{margin["top"]:.1f} '
               f'L{margin["left"]:.1f},{oy:.1f} '
               f'L{margin["left"]+plot_w:.1f},{oy:.1f}')
    axes = f'<path d="{ax_path}" stroke="#333" fill="none" stroke-width="1.5"/>'

    x_ticks = sorted(set(all_x))
    xtick_svg = ''
    for xv in x_ticks:
        sx, sy = px(xv, y_min)
        xtick_svg += (f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{sx:.1f}" y2="{sy+5:.1f}" '
                      f'stroke="#333"/>'
                      f'<text x="{sx:.1f}" y="{sy+16:.1f}" text-anchor="middle" '
                      f'font-size="11">{int(xv)}</text>')

    ytick_count = 5
    ytick_svg = ''
    for i in range(ytick_count + 1):
        yv = y_min + (y_max - y_min) * i / ytick_count
        sx, sy = px(x_min, yv)
        ytick_svg += (f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{sx-5:.1f}" y2="{sy:.1f}" '
                      f'stroke="#333"/>'
                      f'<text x="{sx-8:.1f}" y="{sy+4:.1f}" text-anchor="end" '
                      f'font-size="10">{yv:.1f}</text>')

    legend_svg = ''
    lx = margin['left'] + 10
    ly = margin['top'] + 10
    for icon, lbl in legend_items:
        legend_svg += (f'<g transform="translate({lx},{ly})">{icon}'
                       f'<text x="24" y="10" font-size="10">{lbl}</text></g>')
        ly += 18

    lbl_x = W // 2
    lbl_y = H - 10
    title_y = margin['top'] - 10
    xlabel_svg = f'<text x="{lbl_x}" y="{lbl_y}" text-anchor="middle" font-size="12">{xlabel}</text>'
    ylabel_svg = (f'<text x="14" y="{H//2}" text-anchor="middle" font-size="12" '
                  f'transform="rotate(-90 14 {H//2})">{ylabel}</text>')
    title_svg = (f'<text x="{W//2}" y="{title_y}" text-anchor="middle" font-size="13" '
                 f'font-weight="bold">{title}</text>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">'
            f'<rect width="{W}" height="{H}" fill="white"/>'
            f'{title_svg}{axes}{xtick_svg}{ytick_svg}'
            f'{"".join(lines)}{legend_svg}{xlabel_svg}{ylabel_svg}'
            f'</svg>')


def svg_bar_chart(groups: Dict[str, List[float]], title: str,
                  xlabel: str, ylabel: str, group_labels: List[str]) -> str:
    """
    Grouped bar chart. groups = {series_label: [value_per_group]}.
    group_labels = x-axis labels (one per group).
    """
    W, H = 600, 400
    margin = {'top': 45, 'right': 20, 'bottom': 70, 'left': 70}
    pw = W - margin['left'] - margin['right']
    ph = H - margin['top'] - margin['bottom']

    n_groups = len(group_labels)
    series_names = list(groups.keys())
    n_series = len(series_names)
    palette = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6']

    all_vals = [v for vals in groups.values() for v in vals]
    y_max = max(all_vals) * 1.15 if all_vals else 1.0

    group_w = pw / n_groups
    bar_w = group_w * 0.8 / n_series

    bars = []
    for gi, glabel in enumerate(group_labels):
        gx = margin['left'] + gi * group_w + group_w * 0.1
        for si, sname in enumerate(series_names):
            val = groups[sname][gi] if gi < len(groups[sname]) else 0.0
            bar_h = (val / y_max) * ph
            bx = gx + si * bar_w
            by = margin['top'] + ph - bar_h
            color = palette[si % len(palette)]
            bars.append(
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" '
                f'height="{bar_h:.1f}" fill="{color}" opacity="0.85"/>'
            )
        # x-axis label
        lx = margin['left'] + gi * group_w + group_w / 2
        bars.append(
            f'<text x="{lx:.1f}" y="{margin["top"] + ph + 14}" '
            f'text-anchor="middle" font-size="10">{glabel}</text>'
        )

    # y-axis ticks
    yticks = ''
    for i in range(6):
        yv = y_max * i / 5
        sy = margin['top'] + ph - (yv / y_max) * ph
        yticks += (
            f'<line x1="{margin["left"]}" y1="{sy:.1f}" '
            f'x2="{margin["left"]-5}" y2="{sy:.1f}" stroke="#333"/>'
            f'<text x="{margin["left"]-8}" y="{sy+4:.1f}" '
            f'text-anchor="end" font-size="9">{yv:.1f}</text>'
        )

    # Axes
    ax = (f'<line x1="{margin["left"]}" y1="{margin["top"]}" '
          f'x2="{margin["left"]}" y2="{margin["top"]+ph}" stroke="#333" stroke-width="1.5"/>'
          f'<line x1="{margin["left"]}" y1="{margin["top"]+ph}" '
          f'x2="{margin["left"]+pw}" y2="{margin["top"]+ph}" stroke="#333" stroke-width="1.5"/>')

    # Legend
    legend = ''
    lx = margin['left'] + 10
    ly = margin['top'] + 10
    for si, sname in enumerate(series_names):
        color = palette[si % len(palette)]
        legend += (f'<rect x="{lx}" y="{ly-8}" width="14" height="10" fill="{color}"/>'
                   f'<text x="{lx+17}" y="{ly}" font-size="10">{sname}</text>')
        lx += 120

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">'
        f'<rect width="{W}" height="{H}" fill="white"/>'
        f'<text x="{W//2}" y="25" text-anchor="middle" font-size="13" font-weight="bold">{title}</text>'
        + ax + ''.join(bars) + yticks + legend +
        f'<text x="{W//2}" y="{H-8}" text-anchor="middle" font-size="11">{xlabel}</text>'
        f'<text x="12" y="{H//2}" text-anchor="middle" font-size="11" '
        f'transform="rotate(-90 12 {H//2})">{ylabel}</text>'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Speedup from benchmark CSV
# ---------------------------------------------------------------------------

def load_benchmark(csv_path: str):
    """Load benchmark CSV; filter out thread_stat rows."""
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        return [r for r in reader if not r.get('threads', '').startswith('thread_stat')]


def plot_speedup(csv_path: str, out_dir: str = None):
    if out_dir is None:
        out_dir = RESULTS_DIR
    records = load_benchmark(csv_path)
    if not records:
        print(f"No data in {csv_path}")
        return

    baselines = {}
    for rec in records:
        if int(rec['threads']) == 1:
            key = (rec['rows'], rec['cols'], rec['pattern'], rec['schedule'])
            baselines[key] = float(rec['total_ms'])

    size_labels = sorted(set(f"{r['rows']}x{r['cols']}" for r in records))
    patterns = sorted(set(r['pattern'] for r in records))
    schedules = sorted(set(r['schedule'] for r in records))

    for sched in schedules:
        for size_label in size_labels:
            rows_s, cols_s = size_label.split('x')
            series = {}
            for pattern in patterns:
                pts = []
                key = (rows_s, cols_s, pattern, sched)
                if key not in baselines:
                    continue
                b = baselines[key]
                for rec in records:
                    if (rec['rows'] == rows_s and rec['cols'] == cols_s
                            and rec['pattern'] == pattern and rec['schedule'] == sched):
                        t = float(rec['threads'])
                        ms_v = float(rec['total_ms'])
                        pts.append((t, b / ms_v))
                if pts:
                    series[pattern] = pts
            if not series:
                continue
            svg = svg_linechart(series,
                                f'Speedup — {size_label} mesh, {sched} scheduling',
                                'Number of Threads', 'Speedup', ideal_line=True)
            out = os.path.join(out_dir, f'speedup_{size_label}_{sched}.svg')
            save_svg(svg, out)

    # Time breakdown
    for size_label in size_labels:
        rows_s, cols_s = size_label.split('x')
        pts_t, pts_g = [], []
        for rec in records:
            if (rec['rows'] == rows_s and rec['cols'] == cols_s
                    and rec.get('pattern', '') == 'uniform'
                    and rec.get('schedule', '') == 'static'
                    and 'thermal_ms' in rec):
                t = float(rec['threads'])
                pts_t.append((t, float(rec['thermal_ms'])))
                pts_g.append((t, float(rec.get('geometry_ms', 0))))
        if pts_t:
            svg = svg_linechart({'Thermal update': pts_t, 'Geometry update': pts_g},
                                f'Time Breakdown — {size_label}, uniform, static',
                                'Number of Threads', 'Time (ms)', ideal_line=False)
            out = os.path.join(out_dir, f'time_breakdown_{size_label}.svg')
            save_svg(svg, out)

    print_efficiency_table(records)


def print_efficiency_table(records):
    baselines = {}
    for rec in records:
        if int(rec['threads']) == 1:
            key = (rec['rows'], rec['cols'], rec['pattern'], rec['schedule'])
            baselines[key] = float(rec['total_ms'])
    print("\nParallel Efficiency (static schedule):")
    print(f"{'Threads':>8} {'Size':>8} {'Pattern':>12} {'Speedup':>8} {'Efficiency':>10}")
    print('-' * 55)
    for rec in sorted(records, key=lambda r: (r['rows'], r.get('pattern',''), int(r['threads']))):
        if rec.get('schedule') != 'static':
            continue
        key = (rec['rows'], rec['cols'], rec.get('pattern',''), rec.get('schedule',''))
        if key not in baselines:
            continue
        t = int(rec['threads'])
        speedup = baselines[key] / float(rec['total_ms'])
        eff = speedup / t * 100
        size_lbl = f"{rec['rows']}x{rec['cols']}"
        print(f"{t:>8} {size_lbl:>8} {rec.get('pattern',''):>12} {speedup:>8.2f} {eff:>9.1f}%")


# ---------------------------------------------------------------------------
# Static vs dynamic scheduling comparison
# ---------------------------------------------------------------------------

def plot_scheduling(csv_path: str, out_dir: str = None):
    """
    For each pattern and mesh size, plot speedup for both static and dynamic
    scheduling on the same chart. Highlights where dynamic wins.
    """
    if out_dir is None:
        out_dir = RESULTS_DIR
    records = load_benchmark(csv_path)
    if not records:
        print(f"No data in {csv_path}")
        return

    baselines = {}
    for rec in records:
        if int(rec['threads']) == 1 and rec.get('schedule') == 'static':
            key = (rec['rows'], rec['cols'], rec.get('pattern',''))
            baselines[key] = float(rec['total_ms'])

    size_labels = sorted(set(f"{r['rows']}x{r['cols']}" for r in records))
    patterns = sorted(set(r.get('pattern','') for r in records))

    for size_label in size_labels:
        rows_s, cols_s = size_label.split('x')
        for pattern in patterns:
            key = (rows_s, cols_s, pattern)
            if key not in baselines:
                continue
            b = baselines[key]
            series = {}
            for sched in ['static', 'dynamic']:
                pts = []
                for rec in records:
                    if (rec['rows'] == rows_s and rec['cols'] == cols_s
                            and rec.get('pattern') == pattern
                            and rec.get('schedule') == sched):
                        t = float(rec['threads'])
                        pts.append((t, b / float(rec['total_ms'])))
                if pts:
                    series[sched] = pts
            if len(series) < 2:
                continue
            svg = svg_linechart(series,
                                f'Static vs Dynamic — {pattern}, {size_label}',
                                'Number of Threads', 'Speedup', ideal_line=True)
            out = os.path.join(out_dir, f'scheduling_{pattern}_{size_label}.svg')
            save_svg(svg, out)


# ---------------------------------------------------------------------------
# Per-thread load balance bar chart
# ---------------------------------------------------------------------------

def plot_load_balance(csv_path: str, pattern: str = 'hotspot4',
                      size: str = None, out_dir: str = None):
    """
    Read thread_stat rows from the CSV and show per-thread thermal time as a
    grouped bar chart (one group per thread-count configuration).
    """
    if out_dir is None:
        out_dir = RESULTS_DIR

    with open(csv_path) as f:
        rows = list(csv.reader(f))
    if not rows:
        return

    # Parse header to find index mapping
    header = rows[0]
    # Find thread_stat rows: "thread_stat,<tid>,<ms>"
    thread_data = defaultdict(lambda: defaultdict(list))
    nthreads_seen = set()
    i = 0
    while i < len(rows):
        row = rows[i]
        if len(row) >= 3 and row[0] == 'thread_stat':
            # Look back to find which config this belongs to
            pass
        i += 1

    # Simpler: re-read with csv.DictReader, keep track of last config
    configs = []
    thread_stats_by_config = {}
    current_config = None
    with open(csv_path) as f:
        reader = csv.reader(f)
        hdr = next(reader)
        for row in reader:
            if not row:
                continue
            if row[0] == 'thread_stat':
                if current_config is not None:
                    key = current_config
                    if key not in thread_stats_by_config:
                        thread_stats_by_config[key] = {}
                    tid = int(row[1])
                    thread_stats_by_config[key][tid] = float(row[2])
            else:
                d = dict(zip(hdr, row))
                if (d.get('pattern') == pattern and
                        (size is None or f"{d['rows']}x{d['cols']}" == size)):
                    current_config = (d['rows'], d['cols'], d.get('pattern'), d.get('schedule'), d['threads'])
                    configs.append(current_config)
                else:
                    current_config = None

    if not thread_stats_by_config:
        print(f"No thread stats found for pattern={pattern}. Run with --track-threads.")
        return

    # Build bar chart: groups = thread-count configs, bars = per-thread time
    for config, stats in thread_stats_by_config.items():
        rows_s, cols_s, pat, sched, nthreads = config
        n = int(nthreads)
        if n < 2 or not stats:
            continue
        thread_ids = sorted(stats.keys())
        vals = [stats[t] for t in thread_ids]
        avg = sum(vals) / len(vals)
        imbalance = (max(vals) - min(vals)) / avg * 100

        # Normalize to fraction of average
        norm_vals = [v / avg for v in vals]
        groups = {'Thread time (normalized to avg)': norm_vals}
        group_labels = [f'T{t}' for t in thread_ids]

        svg = svg_bar_chart(groups,
                            f'Load Balance — {pat}, {rows_s}×{cols_s}, {n} threads, {sched}\n'
                            f'Imbalance: {imbalance:.1f}%',
                            'Thread ID', 'Time (normalized to avg)', group_labels)
        fname = f'load_balance_{pat}_{rows_s}x{cols_s}_{n}threads_{sched}.svg'
        save_svg(svg, os.path.join(out_dir, fname))


# ---------------------------------------------------------------------------
# Generate all plots for a benchmark CSV (--all-ghc / --all-psc)
# ---------------------------------------------------------------------------

def generate_all_plots(csv_path: str, heatmap_dir: str, out_dir: str, label: str):
    """Run all plot types for a given benchmark CSV."""
    print(f"\n=== Generating all plots for {label} ===")
    os.makedirs(out_dir, exist_ok=True)

    # Speedup curves
    plot_speedup(csv_path, out_dir)

    # Static vs dynamic scheduling comparison
    plot_scheduling(csv_path, out_dir)

    # Load balance (if thread_stat rows present)
    for pattern in ['hotspot4', 'hotspot1', 'random']:
        plot_load_balance(csv_path, pattern=pattern, out_dir=out_dir)

    # Heatmaps and 3D visualizations
    for pattern in ['uniform', 'hotspot1', 'hotspot4', 'random']:
        heatmap_csv = os.path.join(heatmap_dir, f'heatmap_{pattern}.csv')
        if os.path.exists(heatmap_csv):
            base = os.path.join(out_dir, f'heatmap_{pattern}')
            plot_heatmap(heatmap_csv, base)
            plot_iso3d(heatmap_csv, base)
            plot_profile(heatmap_csv, base)
        else:
            print(f"  Skipping (not found): {heatmap_csv}")

    # Flat vs 3D comparison (if both files exist)
    flat_csv = os.path.join(heatmap_dir, 'heatmap_flat_hotspot1.csv')
    d3_csv  = os.path.join(heatmap_dir, 'heatmap_3d_hotspot1.csv')
    if os.path.exists(flat_csv) and os.path.exists(d3_csv):
        plot_flat_vs_3d(flat_csv, d3_csv, os.path.join(out_dir, 'flat_vs_3d'))
    else:
        print("  Skipping flat-vs-3d (run scripts/run_ghc.sh to generate data)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Visualize thermo-elastic mesh simulation results')
    parser.add_argument('--heatmap',      help='Path to heatmap CSV (top-down T and z views)')
    parser.add_argument('--speedup',      help='Path to benchmark CSV (speedup curves)')
    parser.add_argument('--iso3d',        help='Path to heatmap CSV (isometric 3D surface view)')
    parser.add_argument('--profile',      help='Path to heatmap CSV (center-row cross-section)')
    parser.add_argument('--scheduling',   help='Path to benchmark CSV (static vs dynamic comparison)')
    parser.add_argument('--load-balance', help='Path to benchmark CSV (per-thread bar chart)')
    parser.add_argument('--flat-vs-3d',   nargs=2, metavar=('FLAT_CSV', 'D3_CSV'),
                        help='Compare flat-mode and 3D-mode heatmap CSVs')
    parser.add_argument('--pattern',      default='hotspot4',
                        help='Pattern filter for --load-balance (default: hotspot4)')
    parser.add_argument('--out',          help='Output filename prefix (optional)')
    parser.add_argument('--all',          action='store_true',
                        help='Generate all plots from default paths (legacy)')
    parser.add_argument('--all-ghc',      action='store_true',
                        help='Generate all plots from GHC benchmark results')
    parser.add_argument('--all-psc',      action='store_true',
                        help='Generate all plots from PSC benchmark results')
    args = parser.parse_args()

    if args.all_ghc:
        generate_all_plots(
            csv_path='results/ghc_benchmark.csv',
            heatmap_dir='results/heatmaps',
            out_dir='results',
            label='GHC'
        )
        return

    if args.all_psc:
        generate_all_plots(
            csv_path='results/psc_benchmark.csv',
            heatmap_dir='results/psc_heatmaps',
            out_dir='results',
            label='PSC'
        )
        return

    if args.all:
        for pattern in ['uniform', 'hotspot1', 'hotspot4']:
            path = f'results/heatmaps/heatmap_{pattern}.csv'
            if os.path.exists(path):
                plot_heatmap(path)
                plot_iso3d(path)
                plot_profile(path)
            else:
                print(f"Skipping (not found): {path}")
        bench_path = 'results/benchmark.csv'
        if os.path.exists(bench_path):
            plot_speedup(bench_path)
        else:
            print(f"Skipping (not found): {bench_path}")
        return

    if args.heatmap:
        plot_heatmap(args.heatmap, args.out)
    if args.iso3d:
        plot_iso3d(args.iso3d, args.out)
    if args.profile:
        plot_profile(args.profile, args.out)
    if args.speedup:
        plot_speedup(args.speedup)
    if args.scheduling:
        plot_scheduling(args.scheduling)
    if args.load_balance:
        plot_load_balance(args.load_balance, pattern=args.pattern)
    if args.flat_vs_3d:
        plot_flat_vs_3d(args.flat_vs_3d[0], args.flat_vs_3d[1], args.out)

    if not any([args.heatmap, args.speedup, args.iso3d, args.profile,
                args.scheduling, args.load_balance, args.flat_vs_3d,
                args.all, args.all_ghc, args.all_psc]):
        parser.print_help()


if __name__ == '__main__':
    main()
