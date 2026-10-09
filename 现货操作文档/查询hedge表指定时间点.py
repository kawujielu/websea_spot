#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询 fund.hedge 表在指定 time 时刻的全部记录，按 currency 分组展示。

参考: monitor/tt_spot.py（库 fund、表 hedge）
依赖: pip install mysql-connector-python
兼容: Python 3.9+

用法:
  python 查询hedge表指定时间点.py
  python 查询hedge表指定时间点.py --export hedge_snapshots.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional, Tuple

import mysql.connector
from mysql.connector import Error as MySQLError

# 与 tt_spot.py / 关键hedge表查看.py 一致
DB_CONFIG = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "database": "fund",
}

TABLE_NAME = "hedge"

# 查询的时间点（精确到分钟，与库中 time 字段对齐）
SNAPSHOT_TIMES = [
    "2026-04-28 09:30",
    "2026-05-18 12:00",
    "2026-05-22 08:30",
]


def connect():
    return mysql.connector.connect(**DB_CONFIG)


def fetch_rows_at_snapshot(cursor, snapshot: str) -> Tuple[List[str], List[Tuple[Any, ...]]]:
    """
    按分钟匹配 time 字段，避免秒/微秒格式不一致导致查不到。
    """
    sql = f"""
        SELECT *
        FROM `{TABLE_NAME}`
        WHERE DATE_FORMAT(`time`, '%%Y-%%m-%%d %%H:%%i') = %s
        ORDER BY `currency`, `id`
    """
    cursor.execute(sql, (snapshot,))
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return columns, rows


def group_by_currency(
    columns: List[str], rows: List[Tuple[Any, ...]]
) -> DefaultDict[str, List[Dict[str, Any]]]:
    idx_currency = columns.index("currency") if "currency" in columns else None
    grouped: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        record = dict(zip(columns, row))
        key = str(record.get("currency", "")) if idx_currency is not None else "(no currency)"
        if not key:
            key = "(empty)"
        grouped[key].append(record)
    return grouped


def format_value(value: Any) -> str:
    if value is None:
        return "NULL"
    return str(value)


def print_snapshot(snapshot: str, columns: List[str], rows: List[Tuple[Any, ...]]) -> None:
    print("=" * 80)
    print(f"时间点: {snapshot}  |  共 {len(rows)} 行")
    print("=" * 80)

    if not rows:
        print("  (无记录)\n")
        return

    grouped = group_by_currency(columns, rows)
    for currency in sorted(grouped.keys()):
        items = grouped[currency]
        print(f"\n--- currency: {currency} ({len(items)} 行) ---")
        for i, record in enumerate(items, 1):
            print(f"  [{i}]")
            for col in columns:
                print(f"      {col}: {format_value(record.get(col))}")
    print()


def export_csv(path: str, all_data: List[Tuple[str, List[str], List[Tuple[Any, ...]]]]) -> None:
    """合并三个时间点的结果导出 CSV，增加 snapshot_time 列。"""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = None
        for snapshot, columns, rows in all_data:
            for row in rows:
                record = dict(zip(columns, row))
                record["snapshot_time"] = snapshot
                out_cols = ["snapshot_time"] + columns
                if writer is None:
                    writer = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
                    writer.writeheader()
                writer.writerow({k: record.get(k) for k in out_cols})
    print(f"已导出: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="查询 hedge 表指定 time 快照并按 currency 分组")
    parser.add_argument(
        "--export",
        metavar="FILE",
        help="可选，将查询结果导出为 CSV",
    )
    args = parser.parse_args()

    conn = None
    try:
        conn = connect()
        cursor = conn.cursor()
        print(f"已连接数据库: {DB_CONFIG['database']}.{TABLE_NAME}\n")

        export_buffer: List[Tuple[str, List[str], List[Tuple[Any, ...]]]] = []

        for snapshot in SNAPSHOT_TIMES:
            columns, rows = fetch_rows_at_snapshot(cursor, snapshot)
            print_snapshot(snapshot, columns, rows)
            export_buffer.append((snapshot, columns, rows))

        if args.export:
            export_csv(args.export, export_buffer)

        return 0
    except MySQLError as exc:
        print(f"MySQL 错误: {exc}", file=sys.stderr)
        return 1
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
