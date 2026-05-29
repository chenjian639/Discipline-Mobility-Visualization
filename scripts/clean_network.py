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


SEP_RE = re.compile(r'[-–—→>|:/\\]')


def split_from_to(s: str):
    if pd.isna(s):
        return (None, None)
    t = str(s).strip()
    # 去掉句末的中文句号或多余注释（例如示例中可能有中文句号）
    t = t.rstrip('。.。；; ')  
    # 首先按常见分隔符分割，只分一次
    parts = SEP_RE.split(t, maxsplit=1)
    if len(parts) >= 2:
        a, b = parts[0].strip(), parts[1].strip()
        return (a or None, b or None)
    # 若没有匹配到分隔符，尝试按第一个空格分割
    if ' ' in t:
        a, b = t.split(' ', 1)
        return (a.strip() or None, b.strip() or None)
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

    # 简要报告
    print(f'输出文件已写入: {output_path} (行数 {len(out)})')
    top = out.sort_values('Times', ascending=False).head(10)
    print('Top 10 流动:')
    print(top.to_string(index=False))


def main():
    p = argparse.ArgumentParser(description='清理学科流动 Excel -> 生成 Discipline_Mobility_Network.xlsx')
    p.add_argument('--input', '-i', default='Discipline_Mobility_Network_raw.xlsx', help='原始 Excel 文件路径')
    p.add_argument('--output', '-o', default='../Discipline_Mobility_Network.xlsx', help='输出 Excel，相对 scripts 目录的默认路径')
    p.add_argument('--min-times', type=int, default=1, help='过滤掉 Times 小于此值的行（默认 1）')
    args = p.parse_args()

    inp = Path(args.input)
    out = Path(args.output)
    # 如果使用默认相对路径且脚本在 scripts/ 下，转换为项目根
    if not out.is_absolute():
        out = Path(__file__).resolve().parent.joinpath(out).resolve()

    clean(inp, out, min_times=args.min_times)


if __name__ == '__main__':
    main()
