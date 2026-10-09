#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 fund.hedge 查询指定 time 片段的数据，按 currency 分 sheet 导出 xlsx。
单文件独立运行，不依赖项目 libs。

  python export_hedge_by_currency.py

依赖: pip install pandas openpyxl pymysql
"""
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import pymysql

MYSQL_CONFIG = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "database": "fund",
    "charset": "utf8",
}

# time 字段需包含以下片段（秒级时间戳可能不同，用 LIKE 匹配）
TIME_PATTERNS = (
    "2026-04-28 09:30",
    "2026-05-18 15:30",
    "2026-05-25 11:20",
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _build_sql():
    conditions = " OR ".join(f"`time` LIKE '%{p}%'" for p in TIME_PATTERNS)
    return f"SELECT * FROM hedge WHERE {conditions} ORDER BY currency, `time`"


def _safe_sheet_name(name: str, used: set) -> str:
    """Excel sheet 名最长 31 字符，且不能含 \\ / ? * [ ] :"""
    s = re.sub(r'[\\/*?:\[\]]', "_", str(name))[:31] or "sheet"
    base, n = s, 1
    while s in used:
        suffix = f"_{n}"
        s = (base[: 31 - len(suffix)] + suffix) if len(base) + len(suffix) > 31 else base + suffix
        n += 1
    used.add(s)
    return s


def fetch_hedge_rows():
    sql = _build_sql()
    print("执行 SQL:", sql)
    conn = pymysql.connect(**MYSQL_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            columns = [col[0] for col in cur.description] if cur.description else []
    finally:
        conn.close()

    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)


def export_to_xlsx(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    used_names = set()

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary = df.sort_values(["currency", "time"], kind="mergesort")
        summary.to_excel(writer, sheet_name="全部数据", index=False)

        if "currency" not in df.columns:
            print("警告: 结果中无 currency 列，仅导出「全部数据」")
            return

        for currency, group in df.groupby("currency", sort=True):
            sheet = _safe_sheet_name(currency, used_names)
            group.sort_values("time", kind="mergesort").to_excel(
                writer, sheet_name=sheet, index=False
            )

    n_currency = df["currency"].nunique() if "currency" in df.columns else 0
    print(f"已导出 {len(df)} 行, {n_currency} 个币种")
    print(f"文件: {output_path}")


def main():
    df = fetch_hedge_rows()
    if df.empty:
        print("未查询到匹配数据，请检查 TIME_PATTERNS 或数据库中的 time 格式")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = OUTPUT_DIR / f"hedge_by_currency_{ts}.xlsx"
    export_to_xlsx(df, out_file)


if __name__ == "__main__":
    main()
