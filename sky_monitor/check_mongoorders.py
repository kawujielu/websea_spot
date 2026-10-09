#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询 fund.mongoorders 中指定 symbol、ts 条件下的成交汇总（仅打印结论）。

  python mongoorders_eurr_summary.py

依赖: pip install pymysql
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

# ---------------------------------------------------------------------------
# MySQL（fund 库，与 monitor/export_hedge_by_currency.py 一致）
# ---------------------------------------------------------------------------
MYSQL_CONFIG: dict[str, Any] = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "database": "fund",
}

SYMBOL = "EURR-USDT"
TS_AFTER = "2026-05-23"


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
            COALESCE(AVG(`price`), 0) AS avg_price,
            COALESCE(MAX(`price`), 0) AS max_price,
            COALESCE(MIN(`price`), 0) AS min_price,
            COALESCE(SUM(`amountQuote`), 0) AS sum_amount_quote,
            MIN(`ts`) AS first_ts,
            MAX(`ts`) AS last_ts
        FROM mongoorders
        WHERE `symbol` = %s AND `ts` > %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (SYMBOL, TS_AFTER))
        row = cur.fetchone()
    return row or {}


def main() -> None:
    conn = connect_mysql()
    try:
        row = fetch_summary(conn)
    finally:
        conn.close()

    trade_count = int(row.get("trade_count") or 0)
    sum_amount = _to_float(row.get("sum_amount"))
    avg_price = _to_float(row.get("avg_price"))
    max_price = _to_float(row.get("max_price"))
    min_price = _to_float(row.get("min_price"))
    sum_amount_quote = _to_float(row.get("sum_amount_quote"))
    first_ts = _format_ts(row.get("first_ts"))
    last_ts = _format_ts(row.get("last_ts"))

    if trade_count == 0:
        conclusion = f"{SYMBOL} 在 ts > {TS_AFTER} 之后无成交记录。"
        time_range = "-"
    else:
        time_range = f"{first_ts} ~ {last_ts}"
        conclusion = (
            f"{SYMBOL}（ts > {TS_AFTER}）共 {trade_count} 笔；"
            f"交易时间 {time_range}；"
            f"amount 合计 {sum_amount:,.8f}，amountQuote 合计 {sum_amount_quote:,.8f}；"
            f"平均价格 {avg_price:.8f}，价格区间 [{min_price:.8f}, {max_price:.8f}]。"
        )

    print("【结论】")
    print(conclusion)
    print()
    print(f"交易笔数:        {trade_count}")
    print(f"第一笔时间:      {first_ts}")
    print(f"最后一笔时间:    {last_ts}")
    print(f"交易时间范围:    {time_range}")
    print(f"amount 总和:     {sum_amount:,.8f}")
    print(f"平均价格:        {avg_price:.8f}")
    print(f"最大价格:        {max_price:.8f}")
    print(f"最小价格:        {min_price:.8f}")
    print(f"amountQuote 总和:{sum_amount_quote:,.8f}")


if __name__ == "__main__":
    main()

