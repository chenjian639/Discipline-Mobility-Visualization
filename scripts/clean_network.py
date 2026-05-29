#!/usr/bin/env python3
"""
Clean the raw workbook `data/raw/Discipline_Mobility_Network.xlsx`.

Rules:
- Treat only hyphens WITHOUT surrounding spaces as the From-To separator.
- Keep suffixes like ` - Other Topics` inside discipline names.
- Process every sheet in the workbook.
- Write a cleaned Excel workbook to `data/processed/Discipline_Mobility_Network.xlsx`.
- Also write a JSON file with multiple periods for the front-end.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


# Hyphen used as a suffix or inside a discipline name should be preserved.
# We only split on hyphens that have no spaces on either side.
PAIR_SPLIT_RE = re.compile(r"(?<!\s)-(?!\s)")

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


def normalize_name(name: str) -> str:
    if name is None:
        return ""
    s = str(name).strip()
    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"^(other topics[-\s]+)+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^(language pathology[-\s]+)+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[-\s]+other topics$", "", s, flags=re.IGNORECASE)
    return s.strip(" -")


def classify_category(name: str) -> str:
    base = normalize_name(name)
    primary = re.split(r"\s*-\s*", base, maxsplit=1)[0].strip()
    key = re.sub(r"\s+", " ", primary.lower()).strip()

    if not key or key == "other topics":
        return "Multidisciplinary"

    if key.startswith("science & technology") or key.startswith("life sciences & biomedicine"):
        return "Multidisciplinary"

    if re.search(r"\b(acoustics|astronomy|astrophysics|optics|physics|nuclear science & technology)\b", key):
        return "Physics & Astronomy"

    if re.search(r"\b(biochemistry & molecular biology|chemistry|crystallography|electrochemistry|mineralogy)\b", key):
        return "Chemistry"

    if re.search(
        r"\b(genetics & heredity|cell biology|developmental biology|microbiology|biotechnology & applied microbiology|"
        r"biophysics|marine & freshwater biology|mycology|entomology|evolutionary biology|mathematical & computational biology)\b",
        key,
    ):
        return "Biology & Biochemistry"

    if re.search(
        r"\b(anatomy & morphology|allergy|anesthesiology|audiology & speech|biomedical social sciences|"
        r"cardiovascular system & cardiology|dentistry, oral surgery & medicine|dermatology|emergency medicine|"
        r"endocrinology & metabolism|gastroenterology & hepatology|general & internal medicine|geriatrics & gerontology|"
        r"hematology|immunology|infectious diseases|integrative & complementary medicine|language pathology|legal medicine|"
        r"medical ethics|medical informatics|medical laboratory technology|medicine|nursing|nutrition & dietetics|"
        r"obstetrics & gynecology|oncology|ophthalmology|orthopedics|otorhinolaryngology|pediatrics|pharmacology & pharmacy|"
        r"physiology|psychiatry|public, environmental & occupational health|radiology, nuclear medicine & medical imaging|"
        r"research & experimental medicine|respiratory system|speech language pathology|substance abuse|surgery|"
        r"urology & nephrology)\b",
        key,
    ):
        return "Medicine & Health"

    if re.search(
        r"\b(environmental sciences & ecology|biodiversity & conservation|geochemistry & geophysics|geography|geology|"
        r"meteorology & atmospheric sciences|oceanography|ecology|fisheries|forestry)\b",
        key,
    ):
        return "Earth & Environmental"

    if re.search(
        r"\b(anthropology|area studies|asian studies|business & economics|communication|criminology & penology|"
        r"cultural studies|demography|education & educational research|ethnic studies|family studies|government & law|"
        r"information science & library science|international relations|psychology|social sciences|sociology|transportation|"
        r"mathematical methods in social sciences)\b",
        key,
    ):
        return "Social Sciences"

    if re.search(
        r"\b(archaeology|architecture|art|arts & humanities|classics|dance|film, radio & television|history|"
        r"history & philosophy of science|linguistics|literature|music|philosophy)\b",
        key,
    ):
        return "Arts & Humanities"

    if re.search(
        r"\b(automation & control systems|computer science|construction & building technology|engineering|"
        r"imaging science & photographic technology|instruments & instrumentation|materials science|mechanics|"
        r"metallurgy & metallurgical engineering|mining & mineral processing|operations research & management science)\b",
        key,
    ):
        return "Engineering & Technology"

    if re.search(r"\b(mathematics)\b", key):
        return "Mathematics & Computer Science"

    return "Other"


def split_from_to(s: str) -> Tuple[str | None, str | None]:
    if pd.isna(s):
        return None, None
    t = str(s).strip().rstrip("。.。；; ")
    parts = PAIR_SPLIT_RE.split(t, maxsplit=1)
    if len(parts) == 2:
        left = parts[0].strip()
        right = parts[1].strip()
        return (left or None, right or None)
    return (t or None, None)


def detect_columns(df: pd.DataFrame) -> Tuple[str, str]:
    cols = list(df.columns)
    for c in cols:
        low = str(c).lower()
        if "from" in low and "to" in low:
            return c, find_times_column(df, exclude=[c])
    if len(cols) >= 2:
        return cols[0], cols[1]
    raise RuntimeError("Unable to detect From-To and Times columns")


def find_times_column(df: pd.DataFrame, exclude: List[str] | None = None) -> str:
    exclude = exclude or []
    for c in df.columns:
        if c in exclude:
            continue
        low = str(c).lower()
        if any(k in low for k in ("time", "count", "value", "freq")):
            return c
    for c in df.columns:
        if c not in exclude:
            return c
    raise RuntimeError("Unable to detect Times column")


def clean_sheet(df: pd.DataFrame, min_times: int = 1) -> Tuple[pd.DataFrame, Dict]:
    fromto_col, times_col = detect_columns(df)

    work = df[[fromto_col, times_col]].copy()
    work[times_col] = pd.to_numeric(work[times_col].astype(str).str.replace(",", "", regex=False), errors="coerce")
    work = work.dropna(subset=[times_col])

    pairs = work[fromto_col].astype(str).apply(split_from_to)
    work["From"] = pairs.apply(lambda x: x[0])
    work["To"] = pairs.apply(lambda x: x[1])
    work = work.dropna(subset=["From", "To"])
    work[times_col] = work[times_col].astype(int)
    work = work[work[times_col] >= min_times]

    out = work.groupby(["From", "To"], dropna=False)[times_col].sum().reset_index()
    out = out.rename(columns={times_col: "Times"})

    # Build a period-like JSON payload for the front-end.
    nodes = sorted(set(out["From"]).union(set(out["To"])))
    flow_by_name = defaultdict(int)
    for _, row in out.iterrows():
        flow_by_name[row["From"]] += int(row["Times"])
        flow_by_name[row["To"]] += int(row["Times"])

    nodes = sorted(nodes, key=lambda n: (-flow_by_name[n], n))
    idx = {n: i for i, n in enumerate(nodes)}
    matrix = [[0] * len(nodes) for _ in nodes]
    for _, row in out.iterrows():
        matrix[idx[row["From"]]][idx[row["To"]]] += int(row["Times"])

    d = []
    for name in nodes:
        i = idx[name]
        out_sum = sum(matrix[i])
        in_sum = sum(r[i] for r in matrix)
        self_sum = matrix[i][i]
        d.append(
            {
                "n": name,
                "c": classify_category(name),
                "o": int(out_sum),
                "i": int(in_sum),
                "s": int(self_sum),
            }
        )

    return out, {"d": d, "m": matrix}


def sheet_to_period_key(sheet_name: str) -> Tuple[str, str]:
    low = sheet_name.lower()
    if "2008-2018" in low:
        return "full", "2008–2018 (全部)"
    if "2009-2013" in low:
        return "early", "2009–2013"
    if "2014-2018" in low:
        return "late", "2014–2018"
    key = re.sub(r"[^a-z0-9]+", "_", low).strip("_") or "period"
    return key, sheet_name


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean the raw Discipline Mobility workbook")
    parser.add_argument("--input", "-i", default="../data/raw/Discipline_Mobility_Network.xlsx", help="Raw workbook path")
    parser.add_argument("--output", "-o", default="../data/processed/Discipline_Mobility_Network.xlsx", help="Processed workbook path")
    parser.add_argument("--min-times", type=int, default=1, help="Drop rows with Times below this threshold")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    inp = Path(args.input)
    out = Path(args.output)
    if not inp.is_absolute():
        inp = (base / inp).resolve()
    if not out.is_absolute():
        out = (base / out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    if not inp.exists():
        print(f"Input workbook not found: {inp}", file=sys.stderr)
        sys.exit(2)

    xls = pd.ExcelFile(inp)
    periods: Dict[str, Dict] = {}

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for sheet_name in xls.sheet_names:
            raw = pd.read_excel(inp, sheet_name=sheet_name, dtype=str)
            cleaned, payload = clean_sheet(raw, min_times=args.min_times)
            cleaned.to_excel(writer, sheet_name=sheet_name, index=False)

            key, label = sheet_to_period_key(sheet_name)
            periods[key] = {
                "l": label,
                "d": payload["d"],
                "m": payload["m"],
            }

    json_out = out.with_suffix(".json")
    json_obj = {
        "periods": periods,
        "cats": CAT_COLORS,
    }
    json_out.write_text(json.dumps(json_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Processed workbook written to: {out}")
    print(f"Processed JSON written to: {json_out}")
    for k, v in periods.items():
        print(f"- {k}: {len(v['d'])} nodes")


if __name__ == "__main__":
    main()
