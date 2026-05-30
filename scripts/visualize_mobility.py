#!/usr/bin/env python3
"""
Visualize discipline mobility classification results.

Generates:
- outputs/role_distribution.png      — Bar chart: 4 roles count
- outputs/outflow_vs_inflow.png      — Scatter: outflow vs inflow by role
- outputs/role_by_category.png       — Heatmap: role × category
- outputs/top_bridges.png            — Top bridge disciplines
- outputs/网络流动和弦图.html         — 和弦图 (交互式 HTML)
- outputs/角色桑基图.html             — 桑基图 (交互式 HTML)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Micro Hei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

# ── Color & label mapping ──
ROLE_COLORS = {
    "output-dominant": "#e74c3c",  # red
    "input-dominant":  "#3498db",  # blue
    "bridge":          "#2ecc71",  # green
    "isolated":        "#95a5a6",  # grey
}
ROLE_LABELS = {
    "output-dominant": "传播者 (Outflow-dominant)",
    "input-dominant":  "定居者 (Inflow-dominant)",
    "bridge":          "超越者 (Bridge)",
    "isolated":        "孤立者 (Isolated)",
}

CAT_COLORS = [
    ("Physics & Astronomy", "#e74c3c"),
    ("Chemistry", "#9b59b6"),
    ("Biology & Biochemistry", "#2ecc71"),
    ("Medicine & Health", "#3498db"),
    ("Earth & Environmental", "#1abc9c"),
    ("Engineering & Technology", "#f39c12"),
    ("Social Sciences", "#e67e22"),
    ("Mathematics & Computer Science", "#1a5276"),
    ("Arts & Humanities", "#e91e63"),
    ("Multidisciplinary", "#95a5a6"),
    ("Other", "#bdc3c7"),
]
CAT_COLOR_MAP = {k: v for k, v in CAT_COLORS}


# ── Load data ──
analysis = json.loads((BASE / "data" / "processed" / "Discipline_Mobility_Analysis.json").read_text("utf-8"))
rows = analysis["analysis"]
df = pd.DataFrame(rows)

print(f"Loaded {len(df)} disciplines")

# ── 1. Role distribution bar chart ──
def plot_role_distribution() -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    counts = df["role"].value_counts()
    order = ["output-dominant", "input-dominant", "bridge", "isolated"]
    vals = [counts.get(r, 0) for r in order]
    bars = ax.bar(
        [ROLE_LABELS[r] for r in order],
        vals,
        color=[ROLE_COLORS[r] for r in order],
        edgecolor="white", linewidth=0.5,
    )
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{v} ({v / len(df) * 100:.1f}%)", ha="center", fontsize=11)

    ax.set_ylabel("Discipline count")
    ax.set_title("Discipline Role Classification", fontsize=14, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "role_distribution.png", dpi=150)
    plt.close(fig)
    print("  [OK] role_distribution.png")


# ── 2. Outflow vs Inflow scatter ──
def plot_outflow_vs_inflow() -> None:
    fig, ax = plt.subplots(figsize=(10, 8))
    for role in ["output-dominant", "input-dominant", "bridge", "isolated"]:
        sub = df[df["role"] == role]
        if sub.empty:
            continue
        ax.scatter(
            sub["in"], sub["out"],
            c=ROLE_COLORS[role], label=ROLE_LABELS[role],
            alpha=0.7, edgecolors="white", linewidth=0.3, s=40,
        )

    # Diagonal line (out = in)
    mx = max(df["in"].max(), df["out"].max())
    ax.plot([0, mx], [0, mx], "k--", linewidth=0.5, alpha=0.4, label="out = in")

    ax.set_xlabel("Inflow", fontsize=12)
    ax.set_ylabel("Outflow", fontsize=12)
    ax.set_title("Outflow vs Inflow by Role", fontsize=14, fontweight="bold")
    ax.legend(fontsize=10)
    ax.set_xscale("symlog", linthresh=100)
    ax.set_yscale("symlog", linthresh=100)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "outflow_vs_inflow.png", dpi=150)
    plt.close(fig)
    print("  [OK] outflow_vs_inflow.png")


# ── 3. Role × Category heatmap ──
def plot_role_by_category() -> None:
    ct = pd.crosstab(df["category"], df["role"])
    for r in ["output-dominant", "input-dominant", "bridge", "isolated"]:
        if r not in ct.columns:
            ct[r] = 0
    ct = ct[["output-dominant", "input-dominant", "bridge", "isolated"]]
    ct.columns = [ROLE_LABELS[c] for c in ct.columns]

    fig, ax = plt.subplots(figsize=(10, max(6, len(ct) * 0.4)))
    im = ax.imshow(ct.values, cmap="YlOrRd", aspect="auto")

    for i in range(ct.shape[0]):
        for j in range(ct.shape[1]):
            ax.text(j, i, str(int(ct.values[i, j])),
                    ha="center", va="center", fontsize=9,
                    color="white" if ct.values[i, j] > ct.values.max() * 0.6 else "black")

    ax.set_xticks(range(len(ct.columns)))
    ax.set_xticklabels(ct.columns, rotation=20, ha="right", fontsize=9)
    ax.set_yticks(range(len(ct.index)))
    ax.set_yticklabels(ct.index, fontsize=9)
    ax.set_title("Role Distribution by Major Category", fontsize=14, fontweight="bold")
    fig.colorbar(im, ax=ax, shrink=0.6)
    fig.tight_layout()
    fig.savefig(OUT / "role_by_category.png", dpi=150)
    plt.close(fig)
    print("  [OK] role_by_category.png")


# ── 4. Top bridges by strength ──
def plot_top_bridges() -> None:
    bridges = df[df["role"] == "bridge"].nlargest(20, "strength")
    fig, ax = plt.subplots(figsize=(10, 7))
    colors = [CAT_COLOR_MAP.get(c, "#bdc3c7") for c in bridges["category"]]
    bars = ax.barh(range(len(bridges)), bridges["strength"].values, color=colors, edgecolor="white", linewidth=0.3)
    ax.set_yticks(range(len(bridges)))
    ax.set_yticklabels(bridges["name"].values, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Total Flow (out + in)", fontsize=11)
    ax.set_title("Top 20 Bridge Disciplines by Total Flow", fontsize=14, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)

    # Legend for categories
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=v, label=k) for k, v in CAT_COLOR_MAP.items()
                       if k in bridges["category"].values]
    ax.legend(handles=legend_elements, fontsize=7, loc="lower right")

    fig.tight_layout()
    fig.savefig(OUT / "top_bridges.png", dpi=150)
    plt.close(fig)
    print("  [OK] top_bridges.png")


# ── 5. Interactive Chord Diagram (HTML) ──
def write_chord_html() -> None:
    """Group-level flow chord diagram (category → category)."""
    # Build category-level flow matrix
    cats = [c for c, _ in CAT_COLORS if c in df["category"].values]
    if "Other" in df["category"].values:
        cats.append("Other")
    cat_idx = {c: i for i, c in enumerate(cats)}
    n = len(cats)
    matrix = np.zeros((n, n), dtype=float)

    network = json.loads((BASE / "data" / "processed" / "Discipline_Mobility_Network.json").read_text("utf-8"))
    period = network["periods"]["full"]
    d = period["d"]
    m = period["m"]
    node_cats = {node["n"]: node["c"] for node in d}

    for i, src_name in enumerate([node["n"] for node in d]):
        src_cat = node_cats.get(src_name)
        if src_cat not in cat_idx:
            continue
        for j, tgt_name in enumerate([node["n"] for node in d]):
            tgt_cat = node_cats.get(tgt_name)
            if tgt_cat not in cat_idx:
                continue
            if m[i][j] > 0:
                matrix[cat_idx[src_cat], cat_idx[tgt_cat]] += m[i][j]

    # Color hex without #
    cat_hex = [CAT_COLOR_MAP.get(c, "#bdc3c7")[1:] for c in cats]

    cats_json = json.dumps(cats, ensure_ascii=False)
    matrix_json = json.dumps(matrix.tolist())
    colors_json = json.dumps(cat_hex)

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>学科流动和弦图</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:#f8f9fa; display:flex; justify-content:center; align-items:center; min-height:100vh; font-family:"Microsoft YaHei",sans-serif; }
  #chart { width:960px; height:900px; }
  .tooltip { position:absolute; padding:8px 12px; background:rgba(0,0,0,0.8); color:#fff; border-radius:6px; font-size:13px; pointer-events:none; opacity:0; transition:opacity 0.15s; }
</style>
</head>
<body>
<div id="chart"></div>
<div class="tooltip" id="tooltip"></div>
<script>
const cats = """ + cats_json + """;
const matrix = """ + matrix_json + """;
const colors = """ + colors_json + """;

const width = 960, height = 900, outerR = Math.min(width, height) / 2 - 80, innerR = outerR - 20;
const chord = d3.chord().padAngle(0.04).sortSubgroups(d3.descending);
const arc = d3.arc().innerRadius(innerR).outerRadius(outerR);
const ribbon = d3.ribbon().radius(innerR);

const svg = d3.select("#chart").append("svg").attr("width", width).attr("height", height)
  .append("g").attr("transform", `translate(${width/2},${height/2})`);

const chords = chord(matrix);
const color = d3.scaleOrdinal().domain(d3.range(cats.length)).range(colors.map(c => "#" + c));

// Outer arcs
svg.append("g").selectAll("g").data(chords.groups).join("g").append("path")
  .attr("d", arc).attr("fill", d => color(d.index)).attr("stroke", "#fff").attr("stroke-width", 2)
  .on("mouseover", function(ev, d) {
    d3.select(this).attr("stroke-width", 4).attr("stroke", "#333");
    const name = cats[d.index];
    const total = d3.sum(matrix[d.index]);
    tooltip.style("opacity",1).html(`<b>${name}</b><br>Total flow: ${total.toLocaleString()}`);
  })
  .on("mousemove", ev => tooltip.style("left",(ev.pageX+12)+"px").style("top",(ev.pageY-10)+"px"))
  .on("mouseout", function() { d3.select(this).attr("stroke-width",2).attr("stroke","#fff"); tooltip.style("opacity",0); });

// Labels
svg.append("g").selectAll("g").data(chords.groups).join("g").append("text")
  .attr("dy", ".35em").attr("transform", d => {
    const a = (d.startAngle + d.endAngle) / 2, r = outerR + 18;
    return `rotate(${a * 180 / Math.PI - 90}) translate(${r},0) ${a > Math.PI ? "rotate(180)" : ""}`;
  })
  .attr("text-anchor", d => (d.startAngle + d.endAngle) / 2 > Math.PI ? "end" : "start")
  .attr("font-size", "11px").attr("fill", "#333").text(d => cats[d.index]);

// Ribbons
svg.append("g").selectAll("path").data(chords).join("path")
  .attr("d", ribbon).attr("fill", d => color(d.source.index)).attr("opacity", 0.6)
  .on("mouseover", function(ev, d) {
    d3.select(this).attr("opacity",0.9);
    const src = cats[d.source.index], tgt = cats[d.target.index];
    tooltip.style("opacity",1).html(`<b>${src} → ${tgt}</b><br>Flow: ${d.source.value.toLocaleString()}`);
  })
  .on("mousemove", ev => tooltip.style("left",(ev.pageX+12)+"px").style("top",(ev.pageY-10)+"px"))
  .on("mouseout", function() { d3.select(this).attr("opacity",0.6); tooltip.style("opacity",0); });

const tooltip = d3.select("#tooltip");
</script>
</body>
</html>"""
    (OUT / "网络流动弦图.html").write_text(html, encoding="utf-8")
    print("  [OK] 网络流动弦图.html (chord diagram)")


# ── 6. Interactive Sankey (HTML) ──
def write_sankey_html() -> None:
    """Sankey: role → category, showing distribution of roles within categories."""
    # role → category aggregated flow
    # We treat each discipline as a unit of "flow" from its role to its category
    sankey_data = []
    for _, r in df.iterrows():
        sankey_data.append({"source": ROLE_LABELS.get(r["role"], r["role"]), "target": r["category"], "value": 1})
    sdf = pd.DataFrame(sankey_data)
    grouped = sdf.groupby(["source", "target"], as_index=False)["value"].sum()

    sources = grouped["source"].unique().tolist()
    targets = grouped["target"].unique().tolist()
    all_nodes = sources + targets
    node_idx = {n: i for i, n in enumerate(all_nodes)}

    links = []
    for _, r in grouped.iterrows():
        links.append({"source": node_idx[r["source"]], "target": node_idx[r["target"]], "value": int(r["value"])})

    # Colors for nodes
    node_colors = []
    for n in all_nodes:
        if "传播者" in n:
            node_colors.append("#e74c3c")
        elif "定居者" in n:
            node_colors.append("#3498db")
        elif "超越者" in n:
            node_colors.append("#2ecc71")
        elif "孤立者" in n:
            node_colors.append("#95a5a6")
        else:
            node_colors.append(CAT_COLOR_MAP.get(n, "#bdc3c7"))

    nodes_json = json.dumps([{"name": n, "color": c} for n, c in zip(all_nodes, node_colors)], ensure_ascii=False)
    links_json = json.dumps(links)

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>学科角色桑基图</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-sankey@0.12.3/dist/d3-sankey.min.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:#f8f9fa; display:flex; justify-content:center; align-items:center; min-height:100vh; font-family:"Microsoft YaHei",sans-serif; }
  #chart { width:960px; height:700px; }
  .tooltip { position:absolute; padding:6px 10px; background:rgba(0,0,0,0.8); color:#fff; border-radius:4px; font-size:12px; pointer-events:none; opacity:0; }
</style>
</head>
<body>
<div id="chart"></div>
<div class="tooltip" id="tooltip"></div>
<script>
const nodes = """ + nodes_json + """;
const links = """ + links_json + """;

const width = 960, height = 700;

const svg = d3.select("#chart").append("svg").attr("width", width).attr("height", height)
  .append("g").attr("transform", "translate(20,0)");

const sankey = d3.sankey()
  .nodeWidth(20).nodePadding(12)
  .extent([[1, 5], [width - 25, height - 10]]);

const { nodes: snodes, links: slinks } = sankey({
  nodes: nodes.map(d => Object.assign({}, d)),
  links: links.map(d => Object.assign({}, d)),
});

// Links
svg.append("g").selectAll("path").data(slinks).join("path")
  .attr("d", d3.sankeyLinkHorizontal())
  .attr("fill", "none").attr("stroke", d => d.source.color || "#aaa")
  .attr("stroke-opacity", 0.4).attr("stroke-width", d => Math.max(1, d.width))
  .on("mouseover", function(ev, d) {
    d3.select(this).attr("stroke-opacity",0.8);
    tooltip.style("opacity",1).html(`${d.source.name} → ${d.target.name}: ${d.value}`);
  })
  .on("mousemove", ev => tooltip.style("left",(ev.pageX+12)+"px").style("top",(ev.pageY-10)+"px"))
  .on("mouseout", function() { d3.select(this).attr("stroke-opacity",0.4); tooltip.style("opacity",0); });

// Nodes
svg.append("g").selectAll("rect").data(snodes).join("rect")
  .attr("x", d => d.x0).attr("y", d => d.y0)
  .attr("height", d => d.y1 - d.y0).attr("width", d => d.x1 - d.x0)
  .attr("fill", d => d.color).attr("stroke", "#000").attr("stroke-width", 0.5)
  .append("title").text(d => `${d.name}\n${d.value} disciplines`);

// Labels
svg.append("g").selectAll("text").data(snodes).join("text")
  .attr("x", d => d.x0 < width / 2 ? d.x1 + 6 : d.x0 - 6)
  .attr("y", d => (d.y0 + d.y1) / 2).attr("dy", "0.35em")
  .attr("text-anchor", d => d.x0 < width / 2 ? "start" : "end")
  .attr("font-size", "12px").attr("fill", "#333").text(d => d.name);

const tooltip = d3.select("#tooltip");
</script>
</body>
</html>"""
    (OUT / "角色桑基图.html").write_text(html, encoding="utf-8")
    print("  [OK] 角色桑基图.html (sankey diagram)")


# ── Run all ──
if __name__ == "__main__":
    plot_role_distribution()
    plot_outflow_vs_inflow()
    plot_role_by_category()
    plot_top_bridges()
    write_chord_html()
    write_sankey_html()
    print(f"\nAll outputs saved to: {OUT}")
