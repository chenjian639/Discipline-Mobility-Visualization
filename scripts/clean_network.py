#!/usr/bin/env python3
"""
clean_network.py

读取原始 Excel（第一列格式为 "From-To"，第二列为 Times），
把 From 和 To 拆成两列，合并重复对并按 Times 求和，输出为
项目根目录下的 `Discipline_Mobility_Network.xlsx`（会覆盖同名文件）。

用法示例：
  python scripts/clean_network.py \
    --input "Discipline_Mobility_Network_raw.xlsx" \
    --output "Discipline_Mobility_Network.xlsx"

依赖：pandas, openpyxl
安装：pip install pandas openpyxl
"""
import argparse
import os
import re
import sys
from pathlib import Path

import pandas as pd


# Only split on delimiters with surrounding spaces, so hyphens inside names
# such as "Arts & Humanities - Other Topics" stay intact.
SEP_RE = re.compile(r'\s+[-–—]\s+|\s+→\s+|\s+>\s+')


def normalize_name(name: str) -> str:
    if name is None:
        return ''
    s = str(name).strip()
    s = s.replace('—', '-').replace('–', '-')
    # remove common wrapper prefixes/suffixes that are not true discipline names
    s = re.sub(r'^(other topics[-\s]+)+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(language pathology[-\s]+)+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'[-\s]+other topics$', '', s, flags=re.IGNORECASE)
    s = s.strip(' -')
    return s


def classify_category(name: str) -> str:
    base = normalize_name(name)
    primary = re.split(r'\s*-\s*', base, maxsplit=1)[0].strip()
    key = re.sub(r'\s+', ' ', primary.lower()).strip()

    if not key or key == 'other topics':
        return 'Multidisciplinary'

    if key.startswith('science & technology') or key.startswith('life sciences & biomedicine') or key == 'food science & technology':
        return 'Multidisciplinary'

    if re.search(r'\b(acoustics|astronomy|astrophysics|optics|physics|nuclear science & technology)\b', key):
        return 'Physics & Astronomy'

    if re.search(r'\b(biochemistry & molecular biology|chemistry|crystallography|electrochemistry|mineralogy)\b', key):
        return 'Chemistry'

    if re.search(r'\b(genetics & heredity|cell biology|developmental biology|microbiology|biotechnology & applied microbiology|biophysics|marine & freshwater biology|mycology|entomology|evolutionary biology|mathematical & computational biology)\b', key):
        return 'Biology & Biochemistry'

    if re.search(r'\b(anatomy & morphology|allergy|anesthesiology|audiology & speech|biomedical social sciences|cardiovascular system & cardiology|dentistry, oral surgery & medicine|dermatology|emergency medicine|endocrinology & metabolism|gastroenterology & hepatology|general & internal medicine|geriatrics & gerontology|hematology|immunology|infectious diseases|integrative & complementary medicine|language pathology|legal medicine|medical ethics|medical informatics|medical laboratory technology|medicine|nursing|nutrition & dietetics|obstetrics & gynecology|oncology|ophthalmology|orthopedics|otorhinolaryngology|pediatrics|pharmacology & pharmacy|physiology|psychiatry|public, environmental & occupational health|radiology, nuclear medicine & medical imaging|research & experimental medicine|respiratory system|speech language pathology|substance abuse|surgery|urology & nephrology)\b', key):
        return 'Medicine & Health'

    if re.search(r'\b(environmental sciences & ecology|biodiversity & conservation|geochemistry & geophysics|geography|geology|meteorology & atmospheric sciences|oceanography|marine & freshwater biology|ecology|fisheries)\b', key):
        return 'Earth & Environmental'

    if re.search(r'\b(anthropology|area studies|asian studies|business & economics|communication|criminology & penology|cultural studies|demography|education & educational research|ethnic studies|family studies|government & law|information science & library science|international relations|psychology|social sciences|sociology|transportation|mathematical methods in social sciences|mathematical methods in social sciences)\b', key):
        return 'Social Sciences'

    if re.search(r'\b(archaeology|architecture|art|arts & humanities|classics|dance|film, radio & television|history|history & philosophy of science|language pathology|linguistics|literature|music|philosophy|translation studies)\b', key):
        return 'Arts & Humanities'

    if re.search(r'\b(automation & control systems|computer science|construction & building technology|engineering|imaging science & photographic technology|instruments & instrumentation|materials science|mechanics|metallurgy & metallurgical engineering|mining & mineral processing|nuclear science & technology|operations research & management science)\b', key):
        return 'Engineering & Technology'

    if re.search(r'\b(mathematics|mathematical methods in social sciences)\b', key):
        return 'Mathematics & Computer Science'

    # More conservative fallbacks for fields that often behave like science/technology aggregates
    if re.search(r'\b(agriculture|forestry|plant sciences|food science & technology)\b', key):
        return 'Other'

    return 'Other'


def split_from_to(s: str):
    if pd.isna(s):
        return (None, None)
    t = str(s).strip()
    # 去掉句末的中文句号或多余注释（例如示例中可能有中文句号）
    t = t.rstrip('。.。；; ')
    # 只按“左右有空格”的短横线/箭头分割，避免误切学科名里的连字符
    parts = SEP_RE.split(t, maxsplit=1)
    if len(parts) >= 2:
        a, b = parts[0].strip(), parts[1].strip()
        return (a or None, b or None)
    # 最后退回：把整个字符串放到 From，To 设为 None
    return (t or None, None)


def detect_columns(df: pd.DataFrame):
    # 尝试找名为 From-To 或 包含 '-' 的列
    cols = list(df.columns)
    for c in cols:
        low = str(c).lower()
        if 'from' in low and 'to' in low:
            return c, find_times_column(df, exclude=[c])
    # 查找第一列中包含 '-' 的
    first = cols[0]
    if df[first].astype(str).str.contains('-').any() or df[first].astype(str).str.contains('→').any():
        return first, find_times_column(df, exclude=[first])
    # 否则假设前两列是 From-To 和 Times
    if len(cols) >= 2:
        return cols[0], cols[1]
    raise RuntimeError('无法检测到合适的列（请确保 Excel 至少有两列：From-To 和 Times）')


def find_times_column(df: pd.DataFrame, exclude=None):
    exclude = exclude or []
    for c in df.columns:
        if c in exclude:
            continue
        low = str(c).lower()
        if 'time' in low or 'times' in low or 'count' in low or 'value' in low or 'freq' in low:
            return c
    # fallback: 返回除 exclude 外的第一个列
    for c in df.columns:
        if c not in exclude:
            return c
    raise RuntimeError('找不到 Times 列')


def clean(input_path: Path, output_path: Path, min_times: int = 1):
    if not input_path.exists():
        print(f'输入文件不存在: {input_path}', file=sys.stderr)
        sys.exit(2)

    df = pd.read_excel(input_path, dtype=str)
    if df.empty:
        print('输入文件为空，退出', file=sys.stderr)
        sys.exit(2)

    fromto_col, times_col = detect_columns(df)
    print(f'检测到列：FromTo="{fromto_col}", Times="{times_col}"')

    # 清洗 times 列为数值
    df[times_col] = pd.to_numeric(df[times_col].astype(str).str.replace(',', ''), errors='coerce')
    df = df.dropna(subset=[times_col])

    # 拆分 From-To
    splitted = df[fromto_col].astype(str).apply(split_from_to)
    df['From'] = splitted.apply(lambda x: x[0])
    df['To'] = splitted.apply(lambda x: x[1])

    # 丢弃没有 From 或 To 的行
    df = df.dropna(subset=['From'])
    # 如果 To 缺失，则可以选择丢弃或填充为 From（这里丢弃）
    df = df.dropna(subset=['To'])

    # 过滤次数小于 min_times
    df[times_col] = df[times_col].astype(int)
    df = df[df[times_col] >= min_times]

    # 合并重复的 From/To
    out = df.groupby(['From', 'To'], dropna=False)[times_col].sum().reset_index()
    out = out.rename(columns={times_col: 'Times'})

    # 保存（覆盖输出文件）
    out.to_excel(output_path, index=False, engine='openpyxl')
    # 额外写出 JSON 供前端直接加载（结构化为 periods/full/d/m 和 cats）
    try:
        names = sorted(list(pd.unique(out[['From', 'To']].values.ravel('K'))))
        name_idx = {n: i for i, n in enumerate(names)}
        nlen = len(names)
        matrix = [[0] * nlen for _ in range(nlen)]
        for _, row in out.iterrows():
            f = row['From']; t = row['To']; v = int(row['Times'])
            if f in name_idx and t in name_idx:
                matrix[name_idx[f]][name_idx[t]] += int(v)

        # 计算 in/out/self
        dlist = []
        for name in names:
            iidx = name_idx[name]
            out_sum = sum(matrix[iidx])
            in_sum = sum(row[iidx] for row in matrix)
            self_sum = matrix[iidx][iidx]
            dlist.append({
                'n': name,
                'c': classify_category(name),
                'o': int(out_sum),
                'i': int(in_sum),
                's': int(self_sum)
            })

        fullobj = {
            'periods': {
                'full': {
                    'l': 'processed',
                    'd': dlist,
                    'm': matrix
                }
            },
            # 保留简单类别配色，前端会使用
            'cats': [['Other', '#bdc3c7']]
        }
        json_out = output_path.with_suffix('.json')
        import json
        with open(json_out, 'w', encoding='utf-8') as f:
            json.dump(fullobj, f, ensure_ascii=False, indent=2)
        print(f'JSON 已写入: {json_out}')
    except Exception as e:
        print('生成 JSON 失败：', e)

    # 简要报告
    print(f'输出文件已写入: {output_path} (行数 {len(out)})')
    top = out.sort_values('Times', ascending=False).head(10)
    print('Top 10 流动:')
    print(top.to_string(index=False))


def main():
    p = argparse.ArgumentParser(description='清理学科流动 Excel -> 生成 Discipline_Mobility_Network.xlsx')
    p.add_argument('--input', '-i', default='../data/raw/Discipline_Mobility_Network.xlsx', help='原始 Excel 文件路径（默认 data/raw/ 下的文件）')
    p.add_argument('--output', '-o', default='../data/processed/Discipline_Mobility_Network.xlsx', help='输出 Excel（默认写入 data/processed/ 中，不会覆盖原始文件）')
    p.add_argument('--min-times', type=int, default=1, help='过滤掉 Times 小于此值的行（默认 1）')
    args = p.parse_args()

    inp = Path(args.input)
    out = Path(args.output)
    # 解析相对路径（脚本所在目录为基准）
    base = Path(__file__).resolve().parent
    if not inp.is_absolute():
        inp = (base / inp).resolve()
    if not out.is_absolute():
        out = (base / out).resolve()

    # 确保输出目录存在且不会指向原始文件路径下的同名文件
    out.parent.mkdir(parents=True, exist_ok=True)

    clean(inp, out, min_times=args.min_times)


if __name__ == '__main__':
    main()
