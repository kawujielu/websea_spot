#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询 fund.mongoorders：2026-07-01 ~ 2026-08-01，按 symbol 汇总 buy/sell 的 amount / amountQuote，并计算净交易量。

  python mongoorders_all_symbols_summary_202607.py

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
    "database": "fund",
}

TS_START = "2026-08-15 00:00:00"
TS_END = "2026-09-15 00:00:00"  # 不含


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
    sql = """
        SELECT
            `symbol`,
            LOWER(TRIM(`side`)) AS side_key,
            COALESCE(SUM(ABS(`amount`)), 0) AS sum_amount,
            COALESCE(SUM(ABS(`amountQuote`)), 0) AS sum_quote
        FROM mongoorders
        WHERE `ts` >= %s AND `ts` < %s
          AND LOWER(TRIM(`side`)) IN ('buy', 'sell')
        GROUP BY `symbol`, LOWER(TRIM(`side`))
        ORDER BY `symbol`, side_key
    """
    conn = connect_mysql()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (TS_START, TS_END))
            rows = list(cur.fetchall() or [])
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

    out_path = Path(__file__).with_name("mongoorders_all_symbols_summary_202607.csv")
    fields = [
        "symbol", "buy_amt", "buy_quote", "sell_amt", "sell_quote", "net_amt", "net_quote",
    ]
    records: list[dict[str, Any]] = []
    tot_buy_q = tot_sell_q = tot_net_q = 0.0
    for symbol in sorted(data):
        b, s = data[symbol]["buy"], data[symbol]["sell"]
        net_amt, net_q = b["amount"] - s["amount"], b["quote"] - s["quote"]
        tot_buy_q += b["quote"]
        tot_sell_q += s["quote"]
        tot_net_q += net_q
        records.append({
            "symbol": symbol,
            "buy_amt": b["amount"],
            "buy_quote": b["quote"],
            "sell_amt": s["amount"],
            "sell_quote": s["quote"],
            "net_amt": net_amt,
            "net_quote": net_q,
        })

    print(f"时间范围: [{TS_START}, {TS_END})  symbol数: {len(data)}")
    print("-" * 100)
    hdr = (
        f"{'symbol':<20} {'buy_amt':>16} {'buy_quote':>16} "
        f"{'sell_amt':>16} {'sell_quote':>16} {'net_amt':>16} {'net_quote':>16}"
    )
    print(hdr)
    print("-" * 100)
    for r in records:
        print(
            f"{r['symbol']:<20} {r['buy_amt']:>16,.4f} {r['buy_quote']:>16,.4f} "
            f"{r['sell_amt']:>16,.4f} {r['sell_quote']:>16,.4f} "
            f"{r['net_amt']:>16,.4f} {r['net_quote']:>16,.4f}"
        )
    print("-" * 100)
    print(
        f"全市场合计: buy_quote={tot_buy_q:,.4f}  sell_quote={tot_sell_q:,.4f}  "
        f"net_quote总和={tot_net_q:,.4f}"
    )

    with out_path.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader()
        w.writerows(records)
    print(f"已保存: {out_path}")


if __name__ == "__main__":
    main()

