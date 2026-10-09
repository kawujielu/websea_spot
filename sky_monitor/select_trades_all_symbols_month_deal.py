#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询 hedge.trades：2026-07-01 ~ 2026-08-01，按 symbol/side 汇总对冲成交（成交金额=price*amount），并统计总手续费。

  python trades_hedge_summary_202607.py

依赖: pip install pymysql
"""
from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

MYSQL_CONFIG: dict[str, Any] = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "database": "hedge",
}

TIME_START = "2026-07-01 00:00:00"
TIME_END = "2026-08-01 00:00:00"  # 不含


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


def f(v: Any) -> float:
    if v is None:
        return 0.0
    return float(v) if not isinstance(v, Decimal) else float(v)


def main() -> None:
    sql_side = """
        SELECT
            `symbol`,
            LOWER(TRIM(`side`)) AS side_key,
            COALESCE(SUM(ABS(`amount`)), 0) AS sum_amount,
            COALESCE(SUM(ABS(`price` * `amount`)), 0) AS sum_quote
        FROM trades
        WHERE `time` >= %s AND `time` < %s
          AND LOWER(TRIM(`side`)) IN ('buy', 'sell')
        GROUP BY `symbol`, LOWER(TRIM(`side`))
        ORDER BY `symbol`, side_key
    """
    sql_fee = """
        SELECT
            COALESCE(NULLIF(TRIM(`feecoin`), ''), '(unknown)') AS feecoin,
            COALESCE(SUM(ABS(`fee`)), 0) AS sum_fee
        FROM trades
        WHERE `time` >= %s AND `time` < %s
        GROUP BY COALESCE(NULLIF(TRIM(`feecoin`), ''), '(unknown)')
        ORDER BY sum_fee DESC
    """

    conn = connect_mysql()
    try:
        with conn.cursor() as cur:
            cur.execute(sql_side, (TIME_START, TIME_END))
            rows = list(cur.fetchall() or [])
            cur.execute(sql_fee, (TIME_START, TIME_END))
            fee_rows = list(cur.fetchall() or [])
    finally:
        conn.close()

    data: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: {
            "buy": {"amount": 0.0, "quote": 0.0},
            "sell": {"amount": 0.0, "quote": 0.0},
        }
    )
    for r in rows:
        s = str(r["side_key"]).lower()
        data[r["symbol"]][s] = {"amount": f(r["sum_amount"]), "quote": f(r["sum_quote"])}

    out_path = Path(__file__).with_name("trades_hedge_summary_202607.csv")
    fields = ["symbol", "buy_amt", "buy_quote", "sell_amt", "sell_quote", "net_amt", "net_quote"]
    tot_buy_q = tot_sell_q = 0.0
    with out_path.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader()
        for symbol in sorted(data):
            b, s = data[symbol]["buy"], data[symbol]["sell"]
            net_amt, net_q = b["amount"] - s["amount"], b["quote"] - s["quote"]
            tot_buy_q += b["quote"]
            tot_sell_q += s["quote"]
            w.writerow({
                "symbol": symbol,
                "buy_amt": b["amount"],
                "buy_quote": b["quote"],
                "sell_amt": s["amount"],
                "sell_quote": s["quote"],
                "net_amt": net_amt,
                "net_quote": net_q,
            })

    print(f"时间范围: [{TIME_START}, {TIME_END})  symbol数: {len(data)}")
    print(
        f"成交金额合计: buy_quote={tot_buy_q:,.4f}  sell_quote={tot_sell_q:,.4f}  "
        f"净quote(buy-sell)={tot_buy_q - tot_sell_q:,.4f}"
    )
    print("总手续费(按 feecoin):")
    if not fee_rows:
        print("  无")
    else:
        for r in fee_rows:
            print(f"  {r['feecoin']}: {f(r['sum_fee']):,.8f}")
    print(f"已保存: {out_path}")


if __name__ == "__main__":
    main()

