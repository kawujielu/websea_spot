#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询 fund.hedge 表，按 currency 计算两个时间点「dc当前值」的差值，
并与 CORRECT_AMOUNT（写死在脚本内，与 monitor/config/infor.py 同步）合并输出。

  mysql_diff = T1 时刻 dc当前值 - T2 时刻 dc当前值
  merged     = mysql_diff + CORRECT_AMOUNT

直接运行: python hedge_dc_diff.py
依赖: pip install pymysql
兼容: Python 3.9+
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List

# ======================== 写死配置 ========================
MYSQL_CONFIG = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "database": "fund",
    "charset": "utf8mb4",
}

TABLE_NAME = "hedge"
DC_COLUMN = "dc当前值"

TIME_T1 = "2026-08-31 23:50"
TIME_T2 = "2026-09-01 00:05"

# 与 monitor/config/infor.py 中 CORRECT_AMOUNT 保持一致；更新时请同步修改
CORRECT_AMOUNT = {
    "SKY": -1778.9256,
    "NEWT": 2275.979,
    "BMT": 13187.909214567266,
    "MEME": 323439.0,
    "GLM": 1999.4,
    "BAT": 2580.8,
    "LDO": 982.764734,
    "BOME": 775304.550548,
    "NXPC": 497.1,
    "1INCH": 4497.3,
    "XAUT": 0.086822,
    "DOGS": 18345814.34,
    "IOTX": 128560.19,
    "PEPE": -74011576,
    "CFX": 16454.718,
    "ASTER": 5948.5,
    "ETHFI": 2491.31,
    "GALA": 391196.5009,
    "FET": 8987.6944915518,
    "SAND": 16749.228974,
    "POL": 13780.96,
    "WLD": 4896.66,
    "ACT": 168079.1,
    "OKB": 53.15755733,
    "ENS": 485.973109,
    "CHZ": 178945.27,
    "SUI": 4260.46,
    "APE": 41189.703206,
    "BEAMX": 2470790.31,
    "NEAR": 4160.359,
    "PENDLE": 3764.614,
    "JASMY": 995200.0,
    "OM": 89792.809,
    "TIA": 22474.7,
    "WLFI": 61447.69,
    "DOGE": 144630,
    "TON": 7716,
    "ONDO": 52785.03,
    "LTC": 293.213,
    "PUMP": 9515235.22363,
    "UNI": 5646.5,
    "WIF": 100930.26,
    "ARB": 293467.47,
    "XRP": 21901.2108,
    "LINK": 7539.626951,
    "PEOPLE": 13626335.3056,
    "USDC": 117864,
    "CAKE": 70883.171,
    "COMP": 7998.704803,
    "ETH": 409.6367,
    "SOL": 7909.4268545,
    "BTC": 149.9539,
    "TRX": 2709743,
    "BNB": 1509.822,
    "SHIB": 200714622855,
    "USDT": 12768376,
    "MOVE": 381.83,
    "HOME": 2520.28,
    "FTT": 235.7,
    "YGG": 158.2,
    "RENDER": 15.7,
    "SUSHI": 930,
    "ANKR": 17629.6,
    "EGLD": 14,
    "FLOKI": -2616001490,
    "TRB": 4.129,
    "INJ": 22,
    "C": 4000,
    "ENA": 28.5,
    "APT": 164.79,
    "NEIRO": 461662,
    "PENGU": -142224,
}
# ==========================================================


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
        charset=cfg["charset"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt_num(v: float) -> float:
    if v == 0.0:
        return 0.0
    return round(v, 8)


def get_correct_amount() -> Dict[str, float]:
    return {str(k).upper(): _to_float(v) for k, v in CORRECT_AMOUNT.items()}


def fetch_dc_at_snapshot(conn, snapshot: str) -> Dict[str, float]:
    """按分钟匹配 time，同一 currency 取 id 最大的一条。"""
    sql = f"""
        SELECT h.`currency`, h.`{DC_COLUMN}` AS dc_val
        FROM `{TABLE_NAME}` h
        INNER JOIN (
            SELECT `currency`, MAX(`id`) AS max_id
            FROM `{TABLE_NAME}`
            WHERE DATE_FORMAT(`time`, '%%Y-%%m-%%d %%H:%%i') = %s
            GROUP BY `currency`
        ) t ON h.`id` = t.max_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (snapshot,))
        rows = cur.fetchall()

    result: Dict[str, float] = {}
    for row in rows:
        currency = str(row.get("currency") or "").strip().upper()
        if currency:
            result[currency] = _to_float(row.get("dc_val"))
    return result


def build_mysql_diff(t1_values: Dict[str, float], t2_values: Dict[str, float]) -> Dict[str, float]:
    all_coins = set(t1_values) | set(t2_values)
    return {coin: _fmt_num(t1_values.get(coin, 0.0) - t2_values.get(coin, 0.0)) for coin in all_coins}


def build_merged_rows(
    mysql_diff: Dict[str, float],
    correct_amount: Dict[str, float],
) -> List[Dict[str, Any]]:
    all_coins = sorted(set(mysql_diff) | set(correct_amount))
    rows: List[Dict[str, Any]] = []
    for coin in all_coins:
        md = _fmt_num(mysql_diff.get(coin, 0.0))
        ca = _fmt_num(correct_amount.get(coin, 0.0))
        rows.append({
            "currency": coin,
            "mysql_diff": md,
            "correct_amount": ca,
            "merged": _fmt_num(md + ca),
        })
    return rows


def _fmt_num_for_display(v: Any) -> str:
    if isinstance(v, float):
        if v == 0.0:
            return "0"
        s = f"{v:.8f}".rstrip("0").rstrip(".")
        return s if s else "0"
    return str(v)


def print_table(rows: List[Dict[str, Any]]) -> None:
    headers = ("currency", "mysql_diff", "correct_amount", "merged")
    labels = {
        "currency": "currency",
        "mysql_diff": "mysql_diff",
        "correct_amount": "CORRECT_AMOUNT",
        "merged": "merged",
    }
    widths = {k: len(labels[k]) for k in headers}
    for row in rows:
        for k in headers:
            val = row[k] if k == "currency" else _fmt_num_for_display(row[k])
            widths[k] = max(widths[k], len(str(val)))

    def fmt_line(parts: Dict[str, str]) -> str:
        return "  ".join(parts[k].ljust(widths[k]) for k in headers)

    print(fmt_line({k: labels[k] for k in headers}))
    print(fmt_line({k: "-" * widths[k] for k in headers}))
    for row in rows:
        print(fmt_line({
            "currency": row["currency"],
            "mysql_diff": _fmt_num_for_display(row["mysql_diff"]),
            "correct_amount": _fmt_num_for_display(row["correct_amount"]),
            "merged": _fmt_num_for_display(row["merged"]),
        }))


def main() -> int:
    correct_amount = get_correct_amount()

    conn = None
    try:
        conn = connect_mysql()
        t1_map = fetch_dc_at_snapshot(conn, TIME_T1)
        t2_map = fetch_dc_at_snapshot(conn, TIME_T2)
    except Exception as exc:
        print(f"MySQL 查询失败: {exc}", file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            conn.close()

    if not t1_map and not t2_map:
        print(f"未查到 hedge 数据: {TIME_T1!r} / {TIME_T2!r}", file=sys.stderr)
        return 1

    mysql_diff = build_mysql_diff(t1_map, t2_map)
    rows = build_merged_rows(mysql_diff, correct_amount)

    print(f"库: {MYSQL_CONFIG['database']}.{TABLE_NAME}")
    print(f"T1={TIME_T1}  T2={TIME_T2}  mysql_diff = T1[{DC_COLUMN}] - T2[{DC_COLUMN}]")
    print(f"merged = mysql_diff + CORRECT_AMOUNT")
    print(f"共 {len(rows)} 个 currency\n")
    print_table(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())

