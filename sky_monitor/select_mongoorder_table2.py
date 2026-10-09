#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询 fund.mongoorders 中 6月5日之后用户成交，逐笔打印并汇总买卖金额。"""
import mysql.connector

MYSQL = dict(
    host="abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    user="admin",
    password="A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    database="fund",
    port=3306,
)
TS_START = "2026-08-15 00:00:00"  # 6月5日（含）之后

SQL = """
SELECT ts, symbol, side, amount, price, amountQuote
FROM mongoorders
WHERE ts >= %s
ORDER BY ts
"""

db = mysql.connector.connect(**MYSQL)
cur = db.cursor(dictionary=True)
cur.execute(SQL, (TS_START,))
rows = cur.fetchall()
cur.close()
db.close()

buy_quote = sell_quote = 0.0
print(f"共 {len(rows)} 笔（ts >= {TS_START}）\n")
for r in rows:
    side = (r["side"] or "").strip().lower()
    quote = abs(float(r["amountQuote"] or 0))
    if side == "buy":
        buy_quote += quote
    elif side == "sell":
        sell_quote += quote
    print(r)

print(f"\n汇总 amountQuote（绝对值）:")
print(f"  buy:  {buy_quote:,.8f}")
print(f"  sell: {sell_quote:,.8f}")
print(f"  合计: {buy_quote + sell_quote:,.8f}")

