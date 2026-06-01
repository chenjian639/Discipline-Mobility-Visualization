#!/usr/bin/env python3
"""
Analyze processed discipline mobility JSON and classify disciplines into four roles:

1. 传播者 (Outflow-dominant)  - 流出远大于流入，知识输出型
2. 定居者 (Inflow-dominant)  - 流入远大于流出，知识吸收型
3. 超越者 (Bridge)           - 高流入 + 高流出，知识枢纽型
4. 孤立者 (Isolated)         - 流入流出均低，内部封闭型

Outputs:
- data/processed/Discipline_Mobility_Analysis.json
- outputs/classification.csv
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np


def load_processed(path: Path) -> Dict:
    """Load the processed JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def build_adjacency(period_obj: Dict) -> Tuple[List[str], List[List[float]]]:
    """Extract node names and adjacency matrix from period data."""
    d = period_obj["d"]
    m = period_obj["m"]
    names = [node["n"] for node in d]
    n = len(names)
    # Convert to float matrix
    matrix = [[float(m[i][j]) for j in range(n)] for i in range(n)]
    return names, matrix


def compute_metrics(names: List[str], matrix: List[List[float]], period_obj: Dict) -> List[Dict]:
    """
    Compute metrics and classify disciplines into four roles.

    Classification rules:
    - 孤立者 (Isolated): total_flow <= 20th percentile
    - 传播者 (Outflow-dominant): outflow > inflow * 2
    - 定居者 (Inflow-dominant): inflow > outflow * 2
    - 超越者 (Bridge): total_flow >= 70th percentile AND outflow > 0 AND inflow > 0
    - 均衡者 (Balanced): 不满足以上任一条件的中等活跃学科
    """
    n = len(names)

    # Calculate outflow, inflow, self
    outflow = [0.0] * n
    inflow = [0.0] * n
    self_flow = [0.0] * n
    total_flow = [0.0] * n

    for i in range(n):
        for j in range(n):
            w = matrix[i][j]
            if w > 0:
                outflow[i] += w
                inflow[j] += w
                if i == j:
                    self_flow[i] += w
        total_flow[i] = outflow[i] + inflow[i]

    # Calculate percentiles
    total_flow_arr = np.array(total_flow)
    p20 = np.percentile(total_flow_arr, 20) if len(total_flow_arr) else 0.0
    p70 = np.percentile(total_flow_arr, 70) if len(total_flow_arr) else 0.0

    # Classify
    rows = []
    for i, name in enumerate(names):
        out_v = outflow[i]
        in_v = inflow[i]
        self_v = self_flow[i]
        net_v = in_v - out_v
        total_v = total_flow[i]
        out_in_ratio = out_v / in_v if in_v > 0 else None

        # Classification logic
        if total_v <= p20:
            role = "isolated"
        elif out_v > in_v * 2:
            role = "output-dominant"
        elif in_v > out_v * 2:
            role = "input-dominant"
        elif total_v >= p70 and out_v > 0 and in_v > 0:
            role = "bridge"
        else:
            role = "balanced"

        rows.append(
            {
                "name": name,
                "category": next((node["c"] for node in period_obj["d"] if node["n"] == name), ""),
                "out": round(out_v, 2),
                "in": round(in_v, 2),
                "self": round(self_v, 2),
                "net": round(net_v, 2),
                "out_in_ratio": round(out_in_ratio, 4) if out_in_ratio is not None else None,
                "strength": round(total_v, 2),
                "role": role,
            }
        )

    return rows


def compute_pagerank(names: List[str], matrix: List[List[float]]) -> List[float]:
    """Compute PageRank for each node."""
    n = len(names)
    # Build adjacency for PageRank (outgoing edges)
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if matrix[i][j] > 0:
                adj[i].append(j)

    # Simple PageRank implementation
    damping = 0.85
    max_iter = 100
    tol = 1e-8
    pr = [1.0 / n] * n

    for _ in range(max_iter):
        new_pr = [0.0] * n
        for i in range(n):
            if len(adj[i]) == 0:
                # Teleport to all nodes
                for j in range(n):
                    new_pr[j] += damping * pr[i] / n
            else:
                out_degree = len(adj[i])
                for j in adj[i]:
                    new_pr[j] += damping * pr[i] / out_degree
        # Add teleportation base
        for j in range(n):
            new_pr[j] += (1 - damping) / n
        # Check convergence
        diff = sum(abs(new_pr[i] - pr[i]) for i in range(n))
        pr = new_pr
        if diff < tol:
            break

    return pr


def detect_communities(names: List[str], matrix: List[List[float]]) -> List[int]:
    """
    Detect communities using greedy modularity on undirected version.
    Falls back to -1 if networkx is not available.
    """
    try:
        import networkx as nx

        G = nx.Graph()
        for i, name_i in enumerate(names):
            G.add_node(name_i)
        n = len(names)
        for i in range(n):
            for j in range(i + 1, n):
                # Use total flow as undirected weight
                w = matrix[i][j] + matrix[j][i]
                if w > 0:
                    G.add_edge(names[i], names[j], weight=w)

        comps = list(nx.algorithms.community.greedy_modularity_communities(G, weight="weight"))
        node2c = {}
        for cid, comp in enumerate(comps):
            for node in comp:
                node2c[node] = cid
        return [node2c.get(name, -1) for name in names]
    except ImportError:
        print("Warning: networkx not installed, community detection skipped")
        return [-1 for _ in names]
    except Exception as e:
        print(f"Warning: community detection failed: {e}")
        return [-1 for _ in names]


def write_outputs(rows: List[Dict], out_json: Path, out_csv: Path) -> None:
    """Write analysis results to JSON and CSV files."""
    obj = {"period": "full", "analysis": rows}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    header = "name,category,out,in,self,net,out_in_ratio,strength,role\n"
    lines = [header]
    for r in rows:
        out_in = r["out_in_ratio"]
        out_in_str = f"{out_in:.4f}" if isinstance(out_in, (int, float)) else ""
        line = f"{r['name']},{r['category']},{r['out']},{r['in']},{r['self']},{r['net']},{out_in_str},{r['strength']},{r['role']}\n"
        lines.append(line)
    out_csv.write_text("".join(lines), encoding="utf-8")

    # Also print summary statistics
    print("\n" + "=" * 60)
    print("Classification Summary")
    print("=" * 60)
    role_counts = {}
    for r in rows:
        role_counts[r["role"]] = role_counts.get(r["role"], 0) + 1
    for role, count in role_counts.items():
        role_name = {
            "output-dominant": "传播者 (Outflow-dominant)",
            "input-dominant": "定居者 (Inflow-dominant)",
            "bridge": "超越者 (Bridge)",
            "isolated": "孤立者 (Isolated)",
            "balanced": "均衡者 (Balanced)",
        }.get(role, role)
        pct = count / len(rows) * 100
        print(f"  {role_name}: {count} ({pct:.1f}%)")
    print("=" * 60 + "\n")


def main() -> None:
    base = Path(__file__).resolve().parent.parent
    proc = base / "data" / "processed" / "Discipline_Mobility_Network.json"

    if not proc.exists():
        print(f"Error: Processed network JSON not found: {proc}")
        print("Please run clean_discipline_data.py first.")
        return

    data = load_processed(proc)
    # Use 'full' period if available, otherwise first period
    period_obj = data.get("periods", {}).get("full")
    if not period_obj:
        period_obj = next(iter(data.get("periods", {}).values()))
        print(f"Using period: {period_obj.get('l', 'unknown')}")

    names, matrix = build_adjacency(period_obj)
    rows = compute_metrics(names, matrix, period_obj)

    # Add PageRank (optional, for reference)
    pr = compute_pagerank(names, matrix)
    for i, r in enumerate(rows):
        r["pagerank"] = round(pr[i], 6)

    # Add community detection (optional)
    communities = detect_communities(names, matrix)
    for i, r in enumerate(rows):
        r["community"] = communities[i]

    out_json = base / "data" / "processed" / "Discipline_Mobility_Analysis.json"
    out_csv = base / "outputs" / "classification.csv"
    write_outputs(rows, out_json, out_csv)

    print(f"Analysis JSON written to: {out_json}")
    print(f"Classification CSV written to: {out_csv}")


if __name__ == "__main__":
    main()