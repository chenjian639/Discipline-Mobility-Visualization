
"""
Clean the raw matrix workbook `data/raw/Discipline_Mobility_Matrix.xlsx`.

Expected input (per sheet): rows = disciplinary category (From),
columns = disciplinary category (To), cells = accumulative mobility times.

Sheets expected:
- "Disciplinary Mobility for 2008–2018" (full)
- "Disciplinary Mobility for 2009–2013" (early)
- "Disciplinary Mobility for 2014–2018" (late)

This script reads each sheet as a square matrix of categories and
produces `data/processed/Discipline_Mobility_Network.xlsx` and
`data/processed/Discipline_Mobility_Network.json` suitable for the
front-end (periods -> {d: nodes, m: matrix}).
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
]


# 明确的小学科 -> 大类 映射（覆盖正则分类以确保逐一映射）
SUBDISCIPLINE_TO_CATEGORY = {
    "Acoustics": "Physics & Astronomy",
    "Agriculture": "Earth & Environmental",
    "Allergy": "Medicine & Health",
    "Anatomy & Morphology": "Medicine & Health",
    "Anesthesiology": "Medicine & Health",
    "Anthropology": "Social Sciences",
    "Archaeology": "Arts & Humanities",
    "Architecture": "Arts & Humanities",
    "Area Studies": "Social Sciences",
    "Art": "Arts & Humanities",
    "Arts & Humanities - Other Topics": "Arts & Humanities",
    "Asian Studies": "Social Sciences",
    "Astronomy & Astrophysics": "Physics & Astronomy",
    "Audiology & Speech-Language Pathology": "Medicine & Health",
    "Automation & Control Systems": "Engineering & Technology",
    "Behavioral Sciences": "Social Sciences",
    "Biochemistry & Molecular Biology": "Chemistry",
    "Biodiversity & Conservation": "Earth & Environmental",
    "Biomedical Social Sciences": "Medicine & Health",
    "Biophysics": "Biology & Biochemistry",
    "Biotechnology & Applied Microbiology": "Biology & Biochemistry",
    "Business & Economics": "Social Sciences",
    "Cardiovascular System & Cardiology": "Medicine & Health",
    "Cell Biology": "Biology & Biochemistry",
    "Chemistry": "Chemistry",
    "Classics": "Arts & Humanities",
    "Communication": "Social Sciences",
    "Computer Science": "Mathematics & Computer Science",
    "Construction & Building Technology": "Engineering & Technology",
    "Criminology & Penology": "Social Sciences",
    "Crystallography": "Chemistry",
    "Cultural Studies": "Social Sciences",
    "Dance": "Arts & Humanities",
    "Demography": "Social Sciences",
    "Dentistry, Oral Surgery & Medicine": "Medicine & Health",
    "Dermatology": "Medicine & Health",
    "Developmental Biology": "Biology & Biochemistry",
    "Education & Educational Research": "Social Sciences",
    "Electrochemistry": "Chemistry",
    "Emergency Medicine": "Medicine & Health",
    "Endocrinology & Metabolism": "Medicine & Health",
    "Energy & Fuels": "Engineering & Technology",
    "Engineering": "Engineering & Technology",
    "Entomology": "Biology & Biochemistry",
    "Environmental Sciences & Ecology": "Earth & Environmental",
    "Ethnic Studies": "Social Sciences",
    "Evolutionary Biology": "Biology & Biochemistry",
    "Family Studies": "Social Sciences",
    "Film, Radio & Television": "Arts & Humanities",
    "Fisheries": "Earth & Environmental",
    "Food Science & Technology": "Engineering & Technology",
    "Forestry": "Earth & Environmental",
    "Gastroenterology & Hepatology": "Medicine & Health",
    "General & Internal Medicine": "Medicine & Health",
    "Genetics & Heredity": "Biology & Biochemistry",
    "Geochemistry & Geophysics": "Earth & Environmental",
    "Geography": "Earth & Environmental",
    "Geology": "Earth & Environmental",
    "Geriatrics & Gerontology": "Medicine & Health",
    "Government & Law": "Social Sciences",
    "Health Care Sciences & Services": "Medicine & Health",
    "Hematology": "Medicine & Health",
    "History": "Arts & Humanities",
    "History & Philosophy of Science": "Arts & Humanities",
    "Imaging Science & Photographic Technology": "Engineering & Technology",
    "Immunology": "Medicine & Health",
    "Infectious Diseases": "Medicine & Health",
    "Information Science & Library Science": "Social Sciences",
    "Instruments & Instrumentation": "Engineering & Technology",
    "Integrative & Complementary Medicine": "Medicine & Health",
    "International Relations": "Social Sciences",
    "Legal Medicine": "Medicine & Health",
    "Life Sciences & Biomedicine - Other Topics": "Multidisciplinary",
    "Linguistics": "Arts & Humanities",
    "Literature": "Arts & Humanities",
    "Marine & Freshwater Biology": "Biology & Biochemistry",
    "Materials Science": "Engineering & Technology",
    "Mathematical & Computational Biology": "Biology & Biochemistry",
    "Mathematical Methods In Social Sciences": "Social Sciences",
    "Mathematics": "Mathematics & Computer Science",
    "Mechanics": "Engineering & Technology",
    "Medical Ethics": "Medicine & Health",
    "Medical Informatics": "Medicine & Health",
    "Medical Laboratory Technology": "Medicine & Health",
    "Metallurgy & Metallurgical Engineering": "Engineering & Technology",
    "Meteorology & Atmospheric Sciences": "Earth & Environmental",
    "Microbiology": "Biology & Biochemistry",
    "Microscopy": "Biology & Biochemistry",
    "Mineralogy": "Chemistry",
    "Mining & Mineral Processing": "Engineering & Technology",
    "Music": "Arts & Humanities",
    "Mycology": "Biology & Biochemistry",
    "Neurosciences & Neurology": "Medicine & Health",
    "Nuclear Science & Technology": "Physics & Astronomy",
    "Nursing": "Medicine & Health",
    "Nutrition & Dietetics": "Medicine & Health",
    "Obstetrics & Gynecology": "Medicine & Health",
    "Oceanography": "Earth & Environmental",
    "Oncology": "Medicine & Health",
    "Operations Research & Management Science": "Engineering & Technology",
    "Ophthalmology": "Medicine & Health",
    "Optics": "Physics & Astronomy",
    "Orthopedics": "Medicine & Health",
    "Otorhinolaryngology": "Medicine & Health",
    "Paleontology": "Earth & Environmental",
    "Parasitology": "Medicine & Health",
    "Pathology": "Medicine & Health",
    "Pediatrics": "Medicine & Health",
    "Pharmacology & Pharmacy": "Medicine & Health",
    "Philosophy": "Arts & Humanities",
    "Physical Geography": "Earth & Environmental",
    "Physics": "Physics & Astronomy",
    "Physiology": "Medicine & Health",
    "Plant Sciences": "Biology & Biochemistry",
    "Polymer Science": "Chemistry",
    "Psychiatry": "Medicine & Health",
    "Psychology": "Social Sciences",
    "Public Administration": "Social Sciences",
    "Public, Environmental & Occupational Health": "Medicine & Health",
    "Radiology, Nuclear Medicine & Medical Imaging": "Medicine & Health",
    "Rehabilitation": "Medicine & Health",
    "Religion": "Arts & Humanities",
    "Remote Sensing": "Earth & Environmental",
    "Reproductive Biology": "Biology & Biochemistry",
    "Research & Experimental Medicine": "Medicine & Health",
    "Respiratory System": "Medicine & Health",
    "Rheumatology": "Medicine & Health",
    "Robotics": "Engineering & Technology",
    "Science & Technology - Other Topics": "Multidisciplinary",
    "Social Issues": "Social Sciences",
    "Social Sciences - Other Topics": "Social Sciences",
    "Social Work": "Social Sciences",
    "Sociology": "Social Sciences",
    "Spectroscopy": "Chemistry",
    "Sport Sciences": "Medicine & Health",
    "Substance Abuse": "Medicine & Health",
    "Surgery": "Medicine & Health",
    "Telecommunications": "Engineering & Technology",
    "Theater": "Arts & Humanities",
    "Thermodynamics": "Physics & Astronomy",
    "Toxicology": "Medicine & Health",
    "Transplantation": "Medicine & Health",
    "Transportation": "Social Sciences",
    "Tropical Medicine": "Medicine & Health",
    "Urban Studies": "Social Sciences",
    "Urology & Nephrology": "Medicine & Health",
    "Veterinary Sciences": "Medicine & Health",
    "Virology": "Medicine & Health",
    "Water Resources": "Earth & Environmental",
    "Women's Studies": "Social Sciences",
    "Zoology": "Biology & Biochemistry",
}


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
    """分类学科到大类，优先级从高到低"""
    base = normalize_name(name)
    if base in SUBDISCIPLINE_TO_CATEGORY:
        return SUBDISCIPLINE_TO_CATEGORY[base]
    if name in SUBDISCIPLINE_TO_CATEGORY:
        return SUBDISCIPLINE_TO_CATEGORY[name]
    primary = re.split(r"\s*-\s*", base, maxsplit=1)[0].strip()
    key = re.sub(r"\s+", " ", primary.lower()).strip()

    # 1. 多学科
    if not key or key == "other topics":
        return "Multidisciplinary"
    if key.startswith("science & technology") or key.startswith("life sciences & biomedicine"):
        return "Multidisciplinary"

    # 2. 物理学与天文学
    if re.search(r"\b(acoustics|astronomy|astrophysics|optics|physics|nuclear science & technology|thermodynamics)\b", key):
        return "Physics & Astronomy"

    # 3. 化学
    if re.search(r"\b(biochemistry & molecular biology|chemistry|crystallography|electrochemistry|mineralogy|spectroscopy|polymer science)\b", key):
        return "Chemistry"

    # 4. 生物学与生物化学
    if re.search(
        r"\b(genetics & heredity|cell biology|developmental biology|microbiology|biotechnology & applied microbiology|"
        r"biophysics|marine & freshwater biology|mycology|entomology|evolutionary biology|mathematical & computational biology|"
        r"plant sciences|zoology|reproductive biology)\b",
        key,
    ):
        return "Biology & Biochemistry"

    # 5. 医学与健康
    if re.search(
        r"\b(anatomy & morphology|allergy|anesthesiology|audiology & speech|biomedical social sciences|"
        r"cardiovascular system & cardiology|dentistry, oral surgery & medicine|dermatology|emergency medicine|"
        r"endocrinology & metabolism|gastroenterology & hepatology|general & internal medicine|geriatrics & gerontology|"
        r"hematology|immunology|infectious diseases|integrative & complementary medicine|language pathology|legal medicine|"
        r"medical ethics|medical informatics|medical laboratory technology|medicine|nursing|nutrition & dietetics|"
        r"obstetrics & gynecology|oncology|ophthalmology|orthopedics|otorhinolaryngology|pediatrics|pharmacology & pharmacy|"
        r"physiology|psychiatry|public, environmental & occupational health|radiology, nuclear medicine & medical imaging|"
        r"research & experimental medicine|respiratory system|speech language pathology|substance abuse|surgery|"
        r"urology & nephrology|neurology|neurosciences|pathology|virology|parasitology|toxicology|sport sciences|"
        r"rehabilitation)\b",
        key,
    ):
        return "Medicine & Health"

    # 6. 地球与环境科学
    if re.search(
        r"\b(environmental sciences & ecology|biodiversity & conservation|geochemistry & geophysics|geography|geology|"
        r"meteorology & atmospheric sciences|oceanography|ecology|fisheries|forestry|remote sensing|water resources)\b",
        key,
    ):
        return "Earth & Environmental"

    # 7. 社会科学
    if re.search(
        r"\b(anthropology|area studies|asian studies|business & economics|communication|criminology & penology|"
        r"cultural studies|demography|education & educational research|ethnic studies|family studies|government & law|"
        r"information science & library science|international relations|psychology|social sciences|sociology|transportation|"
        r"mathematical methods in social sciences|public administration|social work|urban studies|women's studies)\b",
        key,
    ):
        return "Social Sciences"

    # 8. 数学与计算机科学
    if re.search(r"\b(mathematics|computer science)\b", key):
        return "Mathematics & Computer Science"

    # 9. 艺术与人文学科
    if re.search(
        r"\b(archaeology|architecture|art|arts & humanities|classics|dance|film, radio & television|history|"
        r"history & philosophy of science|linguistics|literature|music|philosophy|religion|theater)\b",
        key,
    ):
        return "Arts & Humanities"

    # 10. 工程与技术
    if re.search(
        r"\b(automation & control systems|computer science|construction & building technology|engineering|"
        r"imaging science & photographic technology|instruments & instrumentation|materials science|mechanics|"
        r"metallurgy & metallurgical engineering|mining & mineral processing|operations research & management science|"
        r"energy & fuels|food science & technology|robotics|telecommunications)\b",
        key,
    ):
        return "Engineering & Technology"

    # 11. 兜底：归入多学科
    return "Multidisciplinary"


def _read_matrix_sheet(df: pd.DataFrame) -> Tuple[list, list]:
    """Return (categories, matrix) given a DataFrame read from a matrix sheet.

    The sheet is expected to have the row labels in the first column (index)
    and the target categories as column headers. Values will be coerced to
    integers (missing -> 0). If rows/columns mismatch, we align them and
    fill missing entries with zeros.
    """
    # If first column is unnamed and became 'Unnamed: 0', treat it as index
    if df.columns[0].lower().startswith("unnamed"):
        df = df.set_index(df.columns[0])

    # Ensure index and columns are strings (category names)
    df.index = df.index.astype(str).str.strip()
    df.columns = df.columns.astype(str).str.strip()

    rows = list(df.index)
    cols = list(df.columns)
    cats = sorted(list(dict.fromkeys(rows + cols)), key=lambda x: x)

    # Build aligned matrix
    import numpy as _np

    mat = _np.zeros((len(cats), len(cats)), dtype=int)
    for rname in rows:
        for cname in cols:
            try:
                val = pd.to_numeric(df.at[rname, cname], errors="coerce")
            except Exception:
                val = 0
            if pd.isna(val):
                val = 0
            mat[cats.index(rname), cats.index(cname)] = int(val)

    return cats, mat.tolist()


def detect_columns(df: pd.DataFrame) -> Tuple[str, str]:
    cols = list(df.columns)
    for c in cols:
        low = str(c).lower()
        if "from" in low and "to" in low:
            return c, find_times_column(df, exclude=[c])
    if len(cols) == 2:
        return cols[0], cols[1]
    raise RuntimeError(f"Unable to detect From-To and Times columns from headers: {cols}")


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


def clean_matrix_sheet(df: pd.DataFrame) -> Dict:
    cats, matrix = _read_matrix_sheet(df)

    d = []
    for i, name in enumerate(cats):
        out_sum = sum(matrix[i])
        in_sum = sum(row[i] for row in matrix)
        self_sum = matrix[i][i]
        d.append({"n": name, "c": classify_category(name), "o": int(out_sum), "i": int(in_sum), "s": int(self_sum)})

    return {"d": d, "m": matrix}


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
    parser = argparse.ArgumentParser(description="Clean the raw Discipline Mobility matrix workbook")
    parser.add_argument("--input", "-i", default="../data/raw/Discipline_Mobility_Matrix.xlsx", help="Raw matrix workbook path")
    parser.add_argument("--output", "-o", default="../data/processed/Discipline_Mobility_Network.xlsx", help="Processed workbook path to write")
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

    try:
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            for sheet_name in xls.sheet_names:
                raw = pd.read_excel(inp, sheet_name=sheet_name, dtype=str, header=0)
                payload = clean_matrix_sheet(raw)
                # write back the matrix sheet for reference
                df_out = pd.DataFrame(payload["m"], index=[n["n"] for n in payload["d"]], columns=[n["n"] for n in payload["d"]])
                df_out.to_excel(writer, sheet_name=sheet_name)

                key, label = sheet_to_period_key(sheet_name)
                periods[key] = {"l": label, "d": payload["d"], "m": payload["m"]}
    except OSError as exc:
        print(f"Failed to overwrite workbook {out}: {exc}", file=sys.stderr)
        return

    json_out = out.with_suffix(".json")
    json_obj = {"periods": periods, "cats": CAT_COLORS}
    try:
        json_out.write_text(json.dumps(json_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"Failed to write JSON {json_out}: {exc}", file=sys.stderr)
        return

    print(f"Processed workbook written to: {out}")
    print(f"Processed JSON written to: {json_out}")
    for k, v in periods.items():
        print(f"- {k}: {len(v['d'])} nodes")


if __name__ == "__main__":
    main()