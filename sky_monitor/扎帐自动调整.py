#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扎帐：查询 fund.hedge 表两个时间点「dc当前值」差值，并更新 monitor infor.py 的 CORRECT_AMOUNT。

  dc_diff = T2 时刻 dc当前值 - T1 时刻 dc当前值（按 currency）

CORRECT_AMOUNT 更新规则（仅 dc_diff != 0 的币种）：
  1. 读取 infor.py 中 CORRECT_AMOUNT 为 dict
  2. 对有变动的 currency：CORRECT_AMOUNT[currency] = 原值 - dc_diff（无 key 则原值按 0）
  3. 写回 infor.py（原 value 保留在行尾注释中）

直接运行（无命令行参数，修改下方配置区即可）：

  python 扎帐自动调整.py

依赖: pip install pymysql
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

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

TABLE_NAME = "hedge"
DC_COLUMN = "dc当前值"

TIME_T1 = "2026-06-02 13:40:05"
TIME_T2 = "2026-06-02 13:50:05"

# monitor infor.py（本地调试路径；服务器上可改为 /home/ubuntu/monitor/config/infor.py）
INFOR_PY_PATH = Path(r"C:\Users\linji\OneDrive\websea\现货项目\monitor\config\infor.py")

# True：写回 CORRECT_AMOUNT；False：仅查询并打印拟更新内容
AUTO_UPDATE_INFOR = True

# ---------------------------------------------------------------------------

RE_TIME_MINUTE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
RE_TIME_SECOND = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
RE_CORRECT_AMOUNT_ENTRY = re.compile(
    r"^(\s+)(['\"])([A-Za-z0-9]+)\2(\s*:\s*)"
    r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)(\s*,?\s*)(#.*)?$",
)


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
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt_num(v: float) -> float:
    if v == 0.0:
        return 0.0
    return round(v, 8)


def _fmt_display(v: Any) -> str:
    if isinstance(v, float):
        if v == 0.0:
            return "0"
        s = f"{v:.8f}".rstrip("0").rstrip(".")
        return s if s else "0"
    return str(v)


def _find_correct_amount_block(text: str) -> tuple[int, int]:
    marker = "CORRECT_AMOUNT = {"
    start = text.find(marker)
    if start < 0:
        raise ValueError("未找到 CORRECT_AMOUNT = {")
    block_start = start + len(marker)
    depth = 1
    idx = block_start
    while idx < len(text) and depth > 0:
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
        idx += 1
    return block_start, idx - 1


def load_correct_amount_dict(path: Path) -> tuple[dict[str, float], dict[str, str]]:
    """
    读取 CORRECT_AMOUNT 为 dict。
    返回 (values, raw_keys)：
      values[currency.upper()] = 数值
      raw_keys[currency.upper()] = 文件中原始 key 写法（如 'ETH'）
    """
    text = path.read_text(encoding="utf-8")
    block_start, block_end = _find_correct_amount_block(text)
    block = text[block_start:block_end]

    values: dict[str, float] = {}
    raw_keys: dict[str, str] = {}
    for line in block.splitlines():
        m = RE_CORRECT_AMOUNT_ENTRY.match(line)
        if not m:
            continue
        raw_key = m.group(3)
        upper = raw_key.upper()
        values[upper] = _to_float(m.group(5))
        raw_keys[upper] = raw_key
    return values, raw_keys


def apply_dc_diff_to_correct_amount(
    correct_amount: dict[str, float],
    dc_diff_by_coin: dict[str, float],
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """
    对有 dc 变动的 currency，在 CORRECT_AMOUNT dict 上减去 dc_diff。
    new_value = old_value - dc_diff
    """
    updated_dict = correct_amount.copy()
    change_log: list[dict[str, Any]] = []

    for coin, dc_diff in sorted(dc_diff_by_coin.items()):
        old_val = updated_dict.get(coin, 0.0)
        new_val = _fmt_num(old_val - dc_diff)
        updated_dict[coin] = new_val
        change_log.append({
            "currency": coin,
            "old_value": old_val,
            "new_value": new_val,
            "dc_diff": dc_diff,
            "action": "update" if coin in correct_amount else "insert",
        })
    return updated_dict, change_log


def _comment_suffix(old_val: float, trailing: str) -> str:
    """原 value 写入注释，并保留该行原有注释链。"""
    old_s = _fmt_display(old_val)
    if trailing and trailing.strip():
        rest = trailing.strip()
        if rest.startswith("#"):
            rest = rest[1:].lstrip()
        return f", #{old_s}, #{rest}"
    return f", #{old_s},"


def _entry_line(indent: str, quote: str, key: str, new_val: float, old_val: float, trailing: str = "") -> str:
    return f"{indent}{quote}{key}{quote}: {_fmt_display(new_val)}{_comment_suffix(old_val, trailing)}"


def write_correct_amount_to_infor(
    path: Path,
    dc_diff_by_coin: dict[str, float],
    correct_amount_before: dict[str, float],
    raw_keys: dict[str, str],
) -> list[dict[str, Any]]:
    """将 apply 后的 CORRECT_AMOUNT 写回 infor.py。"""
    _, change_log = apply_dc_diff_to_correct_amount(correct_amount_before, dc_diff_by_coin)

    text = path.read_text(encoding="utf-8")
    block_start, block_end = _find_correct_amount_block(text)
    block = text[block_start:block_end]
    lines = block.splitlines(keepends=True)

    pending = dict(dc_diff_by_coin)
    default_indent = "                    "
    default_quote = "'"

    for line_idx, line in enumerate(lines):
        stripped = line.rstrip("\n\r")
        m = RE_CORRECT_AMOUNT_ENTRY.match(stripped)
        if not m:
            continue
        raw_key = m.group(3)
        upper = raw_key.upper()
        if upper not in pending:
            continue

        dc_diff = pending[upper]
        old_val = correct_amount_before.get(upper, 0.0)
        new_val = _fmt_num(old_val - dc_diff)
        trailing = m.group(7) or ""
        indent, quote = m.group(1), m.group(2)
        default_indent, default_quote = indent, quote

        new_line = _entry_line(indent, quote, raw_key, new_val, old_val, trailing)
        eol = "\n" if line.endswith("\n") else ""
        lines[line_idx] = new_line + eol
        del pending[upper]

    for coin in sorted(pending):
        dc_diff = pending[coin]
        old_val = 0.0
        raw_key = raw_keys.get(coin, coin)
        new_val = _fmt_num(old_val - dc_diff)
        lines.append(_entry_line(default_indent, default_quote, raw_key, new_val, old_val) + "\n")

    new_text = text[:block_start] + "".join(lines) + text[block_end:]
    path.write_text(new_text, encoding="utf-8")
    return change_log


def _time_match_clause(snapshot: str) -> tuple[str, tuple[Any, ...]]:
    snapshot = snapshot.strip()
    if RE_TIME_MINUTE.match(snapshot):
        return "`time` LIKE %s", (f"{snapshot}%",)
    if RE_TIME_SECOND.match(snapshot):
        return "`time` = %s", (snapshot,)
    raise ValueError(
        f"time 格式无效: {snapshot!r}，请用 'YYYY-MM-DD HH:MM' 或 'YYYY-MM-DD HH:MM:SS'"
    )


def fetch_matched_time(conn, snapshot: str) -> str | None:
    clause, params = _time_match_clause(snapshot)
    sql = f"SELECT MAX(`time`) AS matched_time FROM `{TABLE_NAME}` WHERE {clause}"
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    if not row or row.get("matched_time") is None:
        return None
    return _format_ts(row["matched_time"])


def fetch_dc_at_snapshot(conn, snapshot: str) -> dict[str, float]:
    clause, params = _time_match_clause(snapshot)
    sql = f"""
        SELECT h.`currency`, h.`{DC_COLUMN}` AS dc_val
        FROM `{TABLE_NAME}` h
        INNER JOIN (
            SELECT `currency`, MAX(`id`) AS max_id
            FROM `{TABLE_NAME}`
            WHERE {clause}
            GROUP BY `currency`
        ) t ON h.`id` = t.max_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall() or []

    result: dict[str, float] = {}
    for row in rows:
        currency = str(row.get("currency") or "").strip().upper()
        if currency:
            result[currency] = _to_float(row.get("dc_val"))
    return result


def build_rows(t1_map: dict[str, float], t2_map: dict[str, float]) -> list[dict[str, Any]]:
    all_coins = sorted(set(t1_map) | set(t2_map))
    rows: list[dict[str, Any]] = []
    for coin in all_coins:
        t1_dc = _fmt_num(t1_map.get(coin, 0.0))
        t2_dc = _fmt_num(t2_map.get(coin, 0.0))
        dc_diff = _fmt_num(t2_dc - t1_dc)
        rows.append({
            "currency": coin,
            "t1_dc": t1_dc,
            "t2_dc": t2_dc,
            "dc_diff": dc_diff,
            "changed": dc_diff != 0.0,
        })
    return rows


def print_table(rows: list[dict[str, Any]]) -> None:
    headers = ("currency", "t1_dc", "t2_dc", "dc_diff")
    labels = {
        "currency": "currency",
        "t1_dc": f"T1[{DC_COLUMN}]",
        "t2_dc": f"T2[{DC_COLUMN}]",
        "dc_diff": "dc_diff(T2-T1)",
    }
    widths = {k: len(labels[k]) for k in headers}
    for row in rows:
        for k in headers:
            val = row[k] if k == "currency" else _fmt_display(row[k])
            widths[k] = max(widths[k], len(str(val)))

    def fmt_line(parts: dict[str, str]) -> str:
        return "  ".join(parts[k].ljust(widths[k]) for k in headers)

    print(fmt_line({k: labels[k] for k in headers}))
    print(fmt_line({k: "-" * widths[k] for k in headers}))
    for row in rows:
        print(fmt_line({
            "currency": row["currency"],
            "t1_dc": _fmt_display(row["t1_dc"]),
            "t2_dc": _fmt_display(row["t2_dc"]),
            "dc_diff": _fmt_display(row["dc_diff"]),
        }))


def preview_correct_amount_updates(
    correct_amount: dict[str, float],
    changed_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    dc_diff_by_coin = {r["currency"]: r["dc_diff"] for r in changed_rows}
    _, change_log = apply_dc_diff_to_correct_amount(correct_amount, dc_diff_by_coin)
    return change_log


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("【扎帐 dc当前值 差值查询】")
    print(f"库: {MYSQL_CONFIG['database']}.{TABLE_NAME}")
    print(f"TIME_T1={TIME_T1}  TIME_T2={TIME_T2}  （对应 hedge.time 字段）")
    print(f"dc_diff = T2[{DC_COLUMN}] - T1[{DC_COLUMN}]（按 currency）")
    print(f"CORRECT_AMOUNT 路径: {INFOR_PY_PATH}")
    print(f"AUTO_UPDATE_INFOR = {AUTO_UPDATE_INFOR}")
    print()

    try:
        _time_match_clause(TIME_T1)
        _time_match_clause(TIME_T2)
    except ValueError as exc:
        print(f"配置错误: {exc}", file=sys.stderr)
        sys.exit(1)

    conn = connect_mysql()
    try:
        matched_t1 = fetch_matched_time(conn, TIME_T1)
        matched_t2 = fetch_matched_time(conn, TIME_T2)
        t1_map = fetch_dc_at_snapshot(conn, TIME_T1)
        t2_map = fetch_dc_at_snapshot(conn, TIME_T2)
    finally:
        conn.close()

    print(f"hedge.time 实际匹配: T1 -> {matched_t1 or '未命中'}  T2 -> {matched_t2 or '未命中'}")
    print()

    if not t1_map and not t2_map:
        print(f"未查到 hedge 数据（hedge.time）: {TIME_T1!r} / {TIME_T2!r}")
        sys.exit(1)

    rows = build_rows(t1_map, t2_map)
    changed_rows = [r for r in rows if r["changed"]]

    print(f"T1 快照币种数: {len(t1_map)}  T2 快照币种数: {len(t2_map)}")
    print(f"dc_diff 非零币种: {len(changed_rows)} / {len(rows)}")
    print()

    if not changed_rows:
        print("【结论】两个时间点之间 dc当前值 无变动。")
        return

    print("【变动币种明细】")
    print_table(changed_rows)

    if not INFOR_PY_PATH.is_file():
        print(f"\n警告: 未找到 infor.py: {INFOR_PY_PATH}，跳过 CORRECT_AMOUNT 更新。")
        return

    correct_amount, raw_keys = load_correct_amount_dict(INFOR_PY_PATH)
    previews = preview_correct_amount_updates(correct_amount, changed_rows)

    print()
    print("【CORRECT_AMOUNT 拟更新】CORRECT_AMOUNT[currency] = 原值 - dc_diff")
    print(f"  当前 dict 共 {len(correct_amount)} 个币种，本次变动 {len(previews)} 个")
    for p in previews:
        print(
            f"  [{p['action']}] {p['currency']}: "
            f"CORRECT_AMOUNT[{p['currency']}] "
            f"{_fmt_display(p['old_value'])} - {_fmt_display(p['dc_diff'])} "
            f"= {_fmt_display(p['new_value'])}"
        )

    if not AUTO_UPDATE_INFOR:
        print()
        print("提示: 确认无误后将 AUTO_UPDATE_INFOR 设为 True 再运行以写回 infor.py。")
        return

    dc_diff_by_coin = {r["currency"]: r["dc_diff"] for r in changed_rows}
    applied = write_correct_amount_to_infor(
        INFOR_PY_PATH, dc_diff_by_coin, correct_amount, raw_keys
    )
    print()
    print(f"已写回 {INFOR_PY_PATH}，共更新 {len(applied)} 个币种。")


if __name__ == "__main__":
    main()
