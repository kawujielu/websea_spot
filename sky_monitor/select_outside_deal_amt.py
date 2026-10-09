#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计 hedge.orders 指定时间范围内的成交金额净额（USDT）。

口径:
- 排除 status = CANCELED（大小写不敏感；CANCELLED 一并排除）
- 成交数量用 fillsz（已成交量）；金额 USDT = |fillsz| × price
- buy 记为正，sell 记为负，最后加总净额
- SYMBOL 为空：全部交易对；非空则只查该交易对
- 时间闭区间 [TS_START, TS_END]，字段 `time`

运行:
  python hedge_orders_notional_sum.py
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
    "database": "hedge",
}

# 交易对；空字符串 = 全部
SYMBOL = ""

# 与 mongoorders_notional_sum.py 相同时间范围
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


def fetch_orders(conn) -> List[dict[str, Any]]:
    where = [
        "`time` >= %s",
        "`time` <= %s",
        "UPPER(TRIM(`status`)) NOT IN ('CANCELED', 'CANCELLED')",
    ]
    params: list[Any] = [TS_START, TS_END]
    sym = (SYMBOL or "").strip()
    if sym:
        where.append("`symbol` = %s")
        params.append(sym)

    sql = f"""
        SELECT
            `time`, `symbol`, `side`, `price`,
            `amount`, `fillsz`, `status`, `exchange`
        FROM orders
        WHERE {' AND '.join(where)}
        ORDER BY `time` ASC
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall() or [])


def calc_notional(rows: List[dict[str, Any]]) -> dict[str, Any]:
    """buy 为正、sell 为负；金额 = |fillsz| × price（USDT）。"""
    by_symbol: Dict[str, float] = defaultdict(float)
    buy_usdt = 0.0
    sell_usdt = 0.0
    net = 0.0
    n_buy = n_sell = 0
    n_skip_zero_fill = 0

    for r in rows:
        side = str(r.get("side") or "").strip().lower()
        if side not in ("buy", "sell"):
            continue
        symbol = str(r.get("symbol") or "")
        qty = abs(_to_float(r.get("fillsz")))
        if qty <= 1e-18:
            n_skip_zero_fill += 1
            continue
        px = _to_float(r.get("price"))
        if px <= 0:
            continue
        quote = qty * px

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
        "n_skip_zero_fill": n_skip_zero_fill,
        "buy_usdt": buy_usdt,
        "sell_usdt": sell_usdt,
        "net": net,
        "by_symbol": symbol_rows,
        "first_ts": rows[0].get("time") if rows else None,
        "last_ts": rows[-1].get("time") if rows else None,
        "row_count": len(rows),
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    sym_label = (SYMBOL or "").strip() or "ALL"
    print(f"查询条件: hedge.orders symbol={sym_label} status≠CANCELED")
    print(f"时间范围: [{TS_START}, {TS_END}]")
    print("口径: 成交额USDT=|fillsz|×price；buy=+，sell=-")
    print()

    conn = connect_mysql()
    try:
        rows = fetch_orders(conn)
    finally:
        conn.close()

    if not rows:
        print("【结论】该时间范围内无符合条件的订单。")
        return

    r = calc_notional(rows)
    print("【结论】")
    print(
        f"  订单行数={r['row_count']}（fillsz=0跳过={r['n_skip_zero_fill']}） "
        f"buy笔数={r['n_buy']} sell笔数={r['n_sell']} "
        f"时间={_format_ts(r['first_ts'])} ~ {_format_ts(r['last_ts'])}"
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

