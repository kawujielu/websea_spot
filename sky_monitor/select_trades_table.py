#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询 hedge.trades 中指定 currency、时间范围内的 amount 加总值。

直接运行（无命令行参数，修改下方配置区即可）：

  python 查询trades表amount按currency汇总.py

依赖: pip install pymysql
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Any

# ---------------------------------------------------------------------------
# 配置区（按需修改）
# ---------------------------------------------------------------------------

MYSQL_CONFIG: dict[str, Any] = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "database": "hedge",
}

# 币种
CURRENCY = "PUMP"

# time 起始（含）、结束（含）
TIME_START = "2026-06-01 00:00:00"
TIME_END = "2026-06-05 00:00:00"

# ---------------------------------------------------------------------------


def connect_mysql():
    try:
        import pymysql
    except ImportError as exc:
        raise SystemExit("缺少 pymysql，请执行: pip install pymysql") from exc

    cfg = MYSQL_CONFIG
    return pymysql.connect(
        host=cfg["host"],
        port=int(cfg["port"]),
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def _format_ts(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def fetch_summary(conn) -> dict[str, Any]:
    sql = """
        SELECT
            COUNT(*) AS trade_count,
            COALESCE(SUM(`amount`), 0) AS sum_amount,
            COALESCE(SUM(ABS(`amount`)), 0) AS sum_abs_amount,
            MIN(`time`) AS first_time,
            MAX(`time`) AS last_time
        FROM trades
        WHERE `currency` = %s
          AND `time` >= %s
          AND `time` <= %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (CURRENCY, TIME_START, TIME_END))
        row = cur.fetchone()
    return row or {}


def fetch_by_side(conn) -> list[dict[str, Any]]:
    sql = """
        SELECT
            LOWER(TRIM(`side`)) AS side_key,
            COUNT(*) AS trade_count,
            COALESCE(SUM(`amount`), 0) AS sum_amount
        FROM trades
        WHERE `currency` = %s
          AND `time` >= %s
          AND `time` <= %s
        GROUP BY LOWER(TRIM(`side`))
        ORDER BY side_key
    """
    with conn.cursor() as cur:
        cur.execute(sql, (CURRENCY, TIME_START, TIME_END))
        return list(cur.fetchall() or [])


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print(f"查询条件: currency={CURRENCY}")
    print(f"时间范围: [{TIME_START}, {TIME_END}]")
    print()

    conn = connect_mysql()
    try:
        summary = fetch_summary(conn)
        side_rows = fetch_by_side(conn)
    finally:
        conn.close()

    trade_count = int(summary.get("trade_count") or 0)
    sum_amount = _to_float(summary.get("sum_amount"))
    sum_abs_amount = _to_float(summary.get("sum_abs_amount"))
    first_time = _format_ts(summary.get("first_time"))
    last_time = _format_ts(summary.get("last_time"))

    if trade_count == 0:
        print(f"【结论】该时间范围内无 {CURRENCY} 成交记录。")
        return

    print("【结论】")
    print(
        f"  {CURRENCY} 在 [{TIME_START}, {TIME_END}] 内："
        f"共 {trade_count} 笔，amount 合计 {sum_amount:,.8f}"
    )
    print(f"  |amount| 合计: {sum_abs_amount:,.8f}")
    print(f"  实际成交时间: {first_time} ~ {last_time}")
    print()

    if side_rows:
        print("--- 按 side 拆分 ---")
        for row in side_rows:
            side = row.get("side_key") or "(空)"
            cnt = int(row.get("trade_count") or 0)
            amt = _to_float(row.get("sum_amount"))
            print(f"  {side:>6}: {cnt:>6} 笔, amount 合计 {amt:,.8f}")
        print()


if __name__ == "__main__":
    main()

