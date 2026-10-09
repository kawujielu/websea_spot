#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mongoorders：2026-09-26 起按交易对统计 buy/sell 均价，对比 BN/Gate 现货最新价算跟单盈亏。"""
import csv
import os

import mysql.connector
import requests

OUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mongoorders_buy_sell_stats.csv")

MYSQL = dict(
    host="abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    user="admin",
    password="A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    database="fund",
    port=3306,
)
TS_START = "2026-09-26 00:00:00"
BN_TICKER = "https://api.binance.com/api/v3/ticker/price"
GATE_TICKER = "https://api.gateio.ws/api/v4/spot/tickers"

SQL = """
SELECT symbol,
       LOWER(TRIM(side)) AS side,
       SUM(ABS(amount) * price) / NULLIF(SUM(ABS(amount)), 0) AS avg_price,
       COALESCE(SUM(ABS(amount)), 0) AS total_base,
       COALESCE(SUM(ABS(amountQuote)), 0) AS total_quote
FROM mongoorders
WHERE ts >= %s AND LOWER(TRIM(side)) IN ('buy', 'sell')
GROUP BY symbol, LOWER(TRIM(side))
ORDER BY symbol, side
"""


def bn_prices():
    r = requests.get(BN_TICKER, timeout=15)
    r.raise_for_status()
    return {i["symbol"]: float(i["price"]) for i in r.json()}


def gate_prices():
    r = requests.get(GATE_TICKER, timeout=15)
    r.raise_for_status()
    # Gate: BTC_USDT -> BTC-USDT
    return {i["currency_pair"].replace("_", "-"): float(i["last"]) for i in r.json()}


def to_bn_symbol(sym: str) -> str:
    return str(sym).replace("-", "").upper()


def main():
    conn = mysql.connector.connect(**MYSQL)
    try:
        cur = conn.cursor()
        cur.execute(SQL, (TS_START,))
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    if not rows:
        print("无数据")
        return

    data = {}
    for sym, side, avg_p, base, quote in rows:
        data.setdefault(sym, {})[side] = (
            float(avg_p or 0), float(base or 0), float(quote or 0)
        )

    bn_map = bn_prices()
    gate_map = None  # 懒加载，仅 BN 缺失时拉取

    print("ts >= {}  |  跟单价=BN现货，缺失则用Gate".format(TS_START))
    print("buy盈亏=(buy均价-跟单价)*buy数量  |  sell盈亏=(跟单价-sell均价)*sell数量\n")
    hdr = "{:<18} {:>6} {:>12} {:>14} {:>14} {:>12} {:>14} {:>14} {:>12}"
    print(hdr.format(
        "symbol", "来源", "跟单价", "buy均价", "buy金额", "buy盈亏",
        "sell均价", "sell金额", "sell盈亏",
    ))
    print("-" * 128)

    csv_rows = []
    sum_buy_pnl = sum_sell_pnl = 0.0
    for sym in sorted(data):
        b_avg, b_base, b_q = data[sym].get("buy", (0.0, 0.0, 0.0))
        s_avg, s_base, s_q = data[sym].get("sell", (0.0, 0.0, 0.0))

        px = bn_map.get(to_bn_symbol(sym))
        src = "BN"
        if px is None:
            if gate_map is None:
                gate_map = gate_prices()
            px = gate_map.get(str(sym).upper()) or gate_map.get(str(sym))
            src = "Gate"
        if px is None:
            print("{:<18} {:>6} {:>12}  (BN/Gate均无此交易对)".format(sym, "-", "-"))
            csv_rows.append({
                "symbol": sym, "来源": "", "跟单价": "",
                "buy均价": b_avg if b_base else "", "buy金额": b_q if b_base else "",
                "buy盈亏": "", "sell均价": s_avg if s_base else "",
                "sell金额": s_q if s_base else "", "sell盈亏": "",
            })
            continue

        buy_pnl = (b_avg - px) * b_base if b_base else 0.0
        sell_pnl = (px - s_avg) * s_base if s_base else 0.0
        sum_buy_pnl += buy_pnl
        sum_sell_pnl += sell_pnl
        print(hdr.format(
            sym, src,
            "{:.6g}".format(px),
            "{:.6g}".format(b_avg) if b_base else "-",
            "{:.2f}".format(b_q) if b_base else "-",
            "{:.2f}".format(buy_pnl) if b_base else "-",
            "{:.6g}".format(s_avg) if s_base else "-",
            "{:.2f}".format(s_q) if s_base else "-",
            "{:.2f}".format(sell_pnl) if s_base else "-",
        ))
        csv_rows.append({
            "symbol": sym, "来源": src, "跟单价": px,
            "buy均价": b_avg if b_base else "", "buy金额": b_q if b_base else "",
            "buy盈亏": buy_pnl if b_base else "",
            "sell均价": s_avg if s_base else "", "sell金额": s_q if s_base else "",
            "sell盈亏": sell_pnl if s_base else "",
        })

    total_pnl = sum_buy_pnl + sum_sell_pnl
    csv_rows.append({
        "symbol": "汇总", "来源": "", "跟单价": "",
        "buy均价": "", "buy金额": "", "buy盈亏": sum_buy_pnl,
        "sell均价": "", "sell金额": "", "sell盈亏": sum_sell_pnl,
    })
    csv_rows.append({
        "symbol": "全部总盈亏", "来源": "", "跟单价": "",
        "buy均价": "", "buy金额": "", "buy盈亏": "",
        "sell均价": "", "sell金额": "", "sell盈亏": total_pnl,
    })

    fields = ["symbol", "来源", "跟单价", "buy均价", "buy金额", "buy盈亏",
              "sell均价", "sell金额", "sell盈亏"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(csv_rows)

    print("-" * 128)
    print("【汇总】")
    print("  buy 总盈亏:  {:.2f}".format(sum_buy_pnl))
    print("  sell 总盈亏: {:.2f}".format(sum_sell_pnl))
    print("  全部总盈亏:  {:.2f}".format(total_pnl))
    print("已保存: {}".format(OUT_CSV))


if __name__ == "__main__":
    main()

