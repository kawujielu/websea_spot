#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计 fund.mongoorders 指定时间范围内的成交金额（折 USDT）。

口径:
- SYMBOL 为空：全部交易对；非空则只查该交易对
- 每笔成交金额(USDT) = |amount| × price（也可用 |amountQuote|）
- buy 记为正，sell 记为负（方向相反），最后加总得到净额
- 时间闭区间 [TS_START, TS_END]

运行:
  python mongoorders_notional_sum.py
依赖: pip install pymysql
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# 配置区（按需修改）
# ---------------------------------------------------------------------------

MYSQL_CONFIG: dict[str, Any] = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "database": "fund",
}

# 现货交易对；空字符串 = 全部交易对
SYMBOL = ""

# 时间范围（闭区间，与库内 ts 格式一致）
TS_START = "2026-05-07 16:11:00"
TS_END = "2026-09-22 21:45:58"

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


def fetch_trades(conn) -> List[dict[str, Any]]:
    where = ["`ts` >= %s", "`ts` <= %s"]
    params: list[Any] = [TS_START, TS_END]
    sym = (SYMBOL or "").strip()
    if sym:
        where.append("`symbol` = %s")
        params.append(sym)

    sql = f"""
        SELECT `ts`, `symbol`, `side`, `amount`, `price`, `amountQuote`
        FROM mongoorders
        WHERE {' AND '.join(where)}
        ORDER BY `ts` ASC
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall() or [])


def calc_notional(rows: List[dict[str, Any]]) -> dict[str, Any]:
    """buy 为正、sell 为负，金额 = |amount|×price（USDT）。"""
    by_symbol: Dict[str, float] = defaultdict(float)
    buy_usdt = 0.0
    sell_usdt = 0.0
    net = 0.0
    n_buy = n_sell = 0

    for r in rows:
        side = str(r.get("side") or "").strip().lower()
        if side not in ("buy", "sell"):
            continue
        symbol = str(r.get("symbol") or "")
        qty = abs(_to_float(r.get("amount")))
        price = _to_float(r.get("price"))
        # 优先 amountQuote；否则 price×数量
        quote = abs(_to_float(r.get("amountQuote")))
        if quote <= 1e-18:
            if qty <= 0 or price <= 0:
                continue
            quote = qty * price
        if quote <= 0:
            continue

        if side == "buy":
            signed = quote
            buy_usdt += quote
            n_buy += 1
        else:
            signed = -quote
            sell_usdt += quote
            n_sell += 1

        net += signed
        by_symbol[symbol] += signed

    symbol_rows = sorted(
        ({"symbol": s, "net": v} for s, v in by_symbol.items()),
        key=lambda x: abs(x["net"]),
        reverse=True,
    )
    return {
        "n_buy": n_buy,
        "n_sell": n_sell,
        "buy_usdt": buy_usdt,
        "sell_usdt": sell_usdt,
        "net": net,
        "by_symbol": symbol_rows,
        "first_ts": rows[0].get("ts") if rows else None,
        "last_ts": rows[-1].get("ts") if rows else None,
        "row_count": len(rows),
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    sym_label = (SYMBOL or "").strip() or "ALL"
    print(f"查询条件: symbol={sym_label}")
    print(f"时间范围: [{TS_START}, {TS_END}]")
    print("口径: 成交额USDT=|amount|×price；buy=+，sell=-")
    print()

    conn = connect_mysql()
    try:
        rows = fetch_trades(conn)
    finally:
        conn.close()

    if not rows:
        print("【结论】该时间范围内无成交记录。")
        return

    r = calc_notional(rows)
    print("【结论】")
    print(
        f"  拉取行数={r['row_count']} buy笔数={r['n_buy']} sell笔数={r['n_sell']} "
        f"成交时间={_format_ts(r['first_ts'])} ~ {_format_ts(r['last_ts'])}"
    )
    print(f"  buy 成交额合计:  +{r['buy_usdt']:,.4f} USDT")
    print(f"  sell 成交额合计: -{r['sell_usdt']:,.4f} USDT")
    print(f"  净额加总:         {r['net']:,.4f} USDT")
    print()

    print("—— 按交易对净额(USDT，buy+ / sell-) ——")
    print(f"{'交易对':<16} {'净额USDT':>16}")
    for row in r["by_symbol"]:
        print(f"{str(row['symbol']):<16} {float(row['net']):>16.4f}")


if __name__ == "__main__":
    main()

