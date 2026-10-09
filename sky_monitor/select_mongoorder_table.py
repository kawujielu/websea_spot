#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询 fund.mongoorders 指定时间范围内的已实现盈亏（USDT）。

口径:
- SYMBOL 为空：查全部交易对；非空则只查该交易对
- 按「交易对」均价持仓：平仓盈亏 = (成交价-均价)×数量（USDT）
- 手续费优先用 feeQuote（已是 USDT）；否则买 fee×price、卖 fee
- 时间闭区间 [TS_START, TS_END]

运行:
  python select_mongoorder_table.py
依赖: pip install pymysql
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Tuple

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


def _fee_usdt(side: str, fee: float, fee_quote: float, price: float) -> float:
    """手续费折 USDT：有 feeQuote 优先用；否则买 fee×price，卖 fee。"""
    if abs(fee_quote) > 1e-18:
        return abs(fee_quote)
    if side == "buy":
        return abs(fee) * price
    return abs(fee)


def _apply_fill(
    pos: float,
    avg: float,
    side: str,
    qty: float,
    price: float,
) -> Tuple[float, float, float]:
    """均价持仓：返回 (new_pos, new_avg, realized_pnl_usdt)。"""
    realized = 0.0
    if side == "buy":
        if pos < -1e-12:
            cover = min(qty, -pos)
            realized += (avg - price) * cover
            pos += cover
            qty -= cover
            if abs(pos) < 1e-12:
                pos, avg = 0.0, 0.0
            if qty > 1e-12:
                pos = qty
                avg = price
        else:
            new_pos = pos + qty
            avg = (avg * pos + price * qty) / new_pos if new_pos else 0.0
            pos = new_pos
    else:  # sell
        if pos > 1e-12:
            close = min(qty, pos)
            realized += (price - avg) * close
            pos -= close
            qty -= close
            if abs(pos) < 1e-12:
                pos, avg = 0.0, 0.0
            if qty > 1e-12:
                pos = -qty
                avg = price
        else:
            new_pos = pos - qty
            if pos < -1e-12:
                avg = (avg * (-pos) + price * qty) / (-new_pos) if new_pos else 0.0
            else:
                avg = price
            pos = new_pos
    return pos, avg, realized


def fetch_trades(conn) -> List[dict[str, Any]]:
    """按时间拉取成交；SYMBOL 为空则不限制交易对。"""
    where = ["`ts` >= %s", "`ts` <= %s"]
    params: list[Any] = [TS_START, TS_END]
    sym = (SYMBOL or "").strip()
    if sym:
        where.append("`symbol` = %s")
        params.append(sym)

    sql = f"""
        SELECT
            `ts`, `symbol`, `side`, `amount`, `price`,
            `amountQuote`, `fee`, `feeQuote`
        FROM mongoorders
        WHERE {' AND '.join(where)}
        ORDER BY `ts` ASC
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall() or [])


def calc_realized_pnl(rows: List[dict[str, Any]]) -> dict[str, Any]:
    """按交易对均价持仓，汇总已实现盈亏（USDT）。"""
    book: Dict[str, Tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))
    by_symbol: Dict[str, float] = defaultdict(float)
    by_symbol_n: Dict[str, int] = defaultdict(int)
    total_pnl = 0.0
    trade_count = 0

    for r in rows:
        side = str(r.get("side") or "").strip().lower()
        if side not in ("buy", "sell"):
            continue
        symbol = str(r.get("symbol") or "")
        if not symbol:
            continue
        qty = abs(_to_float(r.get("amount")))
        price = _to_float(r.get("price"))
        if qty <= 0 or price <= 0:
            continue
        fee_usdt = _fee_usdt(
            side,
            _to_float(r.get("fee")),
            _to_float(r.get("feeQuote")),
            price,
        )
        trade_count += 1
        pos, avg = book[symbol]
        pos, avg, realized = _apply_fill(pos, avg, side, qty, price)
        book[symbol] = (pos, avg)
        realized -= fee_usdt
        if abs(realized) < 1e-12:
            continue
        total_pnl += realized
        by_symbol[symbol] += realized
        by_symbol_n[symbol] += 1

    symbol_rows = sorted(
        (
            {"symbol": s, "pnl": p, "n": by_symbol_n[s]}
            for s, p in by_symbol.items()
        ),
        key=lambda x: x["pnl"],
        reverse=True,
    )
    first_ts = rows[0].get("ts") if rows else None
    last_ts = rows[-1].get("ts") if rows else None
    return {
        "trade_count": trade_count,
        "row_count": len(rows),
        "total_pnl": total_pnl,
        "by_symbol": symbol_rows,
        "first_ts": first_ts,
        "last_ts": last_ts,
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
    print()

    conn = connect_mysql()
    try:
        rows = fetch_trades(conn)
    finally:
        conn.close()

    if not rows:
        print("【结论】该时间范围内无成交记录。")
        return

    r = calc_realized_pnl(rows)
    print("【结论】")
    print(
        f"  拉取行数={r['row_count']} 计入买卖笔数={r['trade_count']} "
        f"成交时间={_format_ts(r['first_ts'])} ~ {_format_ts(r['last_ts'])}"
    )
    print(f"  已实现盈亏总和={r['total_pnl']:,.4f} USDT")
    print()

    print("—— 按交易对盈亏(USDT) ——")
    print(f"{'交易对':<16} {'盈亏USDT':>14} {'计入笔数':>10}")
    for row in r["by_symbol"]:
        print(
            f"{str(row['symbol']):<16} {float(row['pnl']):>14.4f} {int(row['n']):>10}"
        )
    if not r["by_symbol"]:
        print("(无产生已实现盈亏的平仓)")


if __name__ == "__main__":
    main()

