"""
按 coin 汇总 hedge 库三张 gap 表的 amount，并可按规则回写 fee_asset_gap。

  exposure_sum = abc_asset_gap.amount + external_asset_gap.amount
  fee_amount     = fee_asset_gap.amount

  sync-fee：将 fee_asset_gap.amount 设为 (abc + external) * -1

用法:

  # 仅查看汇总
  python scripts/hedge_gap_summary.py
  python scripts/hedge_gap_summary.py summary --coins BTC,ETH
  python scripts/hedge_gap_summary.py summary -o summary.csv

  # 预览 fee 将改成的值（不写库）
  python scripts/hedge_gap_summary.py sync-fee

  # 确认后写入 fee_asset_gap
  python scripts/hedge_gap_summary.py sync-fee --apply
  python scripts/hedge_gap_summary.py sync-fee --apply --coins BTC,ETH

连接配置见本文件 MYSQL_CONFIG；USE_TEST_DB=True 时使用 hedge_test 库。

依赖: pip install pymysql
"""
from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# MySQL（与 scripts/hedge_gap_backup.py、scaffold/mysql 一致）
# ---------------------------------------------------------------------------
USE_TEST_DB = False

_MYSQL_PROD = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "database": "hedge",
}

_MYSQL_TEST = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "database": "hedge_test",
}

MYSQL_CONFIG: dict[str, Any] = _MYSQL_TEST if USE_TEST_DB else _MYSQL_PROD

FIELDNAMES = (
    "coin",
    "abc_amount",
    "external_amount",
    "exposure_sum",
    "fee_amount",
    "total_with_fee",
)

FEE_UPDATE_FIELDNAMES = (
    "coin",
    "abc_amount",
    "external_amount",
    "exposure_sum",
    "fee_old",
    "fee_new",
)


def connect_mysql(*, autocommit: bool = True):
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
        autocommit=autocommit,
    )


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def fetch_amounts(conn, table: str, coins: list[str] | None) -> dict[str, float]:
    with conn.cursor() as cur:
        if coins:
            placeholders = ",".join(["%s"] * len(coins))
            sql = f"SELECT `coin`, `amount` FROM `{table}` WHERE `coin` IN ({placeholders})"
            cur.execute(sql, coins)
        else:
            cur.execute(f"SELECT `coin`, `amount` FROM `{table}`")
        rows = cur.fetchall()
    return {row["coin"]: _to_float(row["amount"]) for row in rows}


def load_gap_amounts(conn, coins: list[str] | None) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    abc = fetch_amounts(conn, "abc_asset_gap", coins)
    external = fetch_amounts(conn, "external_asset_gap", coins)
    fee = fetch_amounts(conn, "fee_asset_gap", coins)
    return abc, external, fee


def build_summary(
    abc: dict[str, float],
    external: dict[str, float],
    fee: dict[str, float],
) -> list[dict[str, Any]]:
    all_coins = sorted(set(abc) | set(external) | set(fee))
    rows: list[dict[str, Any]] = []
    for coin in all_coins:
        abc_amt = abc.get(coin, 0.0)
        ext_amt = external.get(coin, 0.0)
        fee_amt = fee.get(coin, 0.0)
        exposure = abc_amt + ext_amt
        rows.append({
            "coin": coin,
            "abc_amount": abc_amt,
            "external_amount": ext_amt,
            "exposure_sum": exposure,
            "fee_amount": fee_amt,
            "total_with_fee": exposure + fee_amt,
        })
    return rows


def build_fee_update_plan(
    abc: dict[str, float],
    external: dict[str, float],
    fee: dict[str, float],
    coins: list[str] | None,
) -> list[dict[str, Any]]:
    """fee_new = (abc + external) * -1；处理的 coin 为 abc|external 的并集（可被 --coins 限制）。"""
    if coins is not None:
        coin_set = set(coins)
        universe = sorted(coin_set)
    else:
        universe = sorted(set(abc) | set(external))

    rows: list[dict[str, Any]] = []
    for coin in universe:
        abc_amt = abc.get(coin, 0.0)
        ext_amt = external.get(coin, 0.0)
        exposure = abc_amt + ext_amt
        fee_new = -exposure
        rows.append({
            "coin": coin,
            "abc_amount": abc_amt,
            "external_amount": ext_amt,
            "exposure_sum": exposure,
            "fee_old": fee.get(coin, 0.0),
            "fee_new": fee_new,
        })
    return rows


def print_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("(无数据)")
        return

    headers = {
        "coin": "coin",
        "abc_amount": "abc",
        "external_amount": "external",
        "exposure_sum": "abc+ext",
        "fee_amount": "fee",
        "total_with_fee": "abc+ext+fee",
    }
    col_widths = {k: len(headers[k]) for k in headers}
    for row in rows:
        for k in headers:
            col_widths[k] = max(col_widths[k], len(_fmt_num(row[k])) if k != "coin" else len(row[k]))

    def line(parts: dict[str, str]) -> str:
        return "  ".join(parts[k].ljust(col_widths[k]) for k in headers)

    print(line({k: headers[k] for k in headers}))
    print(line({k: "-" * col_widths[k] for k in headers}))
    for row in rows:
        print(line({
            "coin": row["coin"],
            "abc_amount": _fmt_num(row["abc_amount"]),
            "external_amount": _fmt_num(row["external_amount"]),
            "exposure_sum": _fmt_num(row["exposure_sum"]),
            "fee_amount": _fmt_num(row["fee_amount"]),
            "total_with_fee": _fmt_num(row["total_with_fee"]),
        }))


def build_offset(plan: list[dict[str, Any]]) -> dict[str, float]:
    """coin -> fee_new - fee_old，供 monitor FEE_BASELINE_OFFSET 等使用。"""
    return {row["coin"]: row["fee_new"] - row["fee_old"] for row in plan}


def print_offset(offset: dict[str, float]) -> None:
    if not offset:
        print("\noffset = {}")
        return
    print("\noffset (fee_new - fee_old):")
    print(offset)


def print_fee_update_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("(无待更新 coin)")
        return

    headers = {
        "coin": "coin",
        "abc_amount": "abc",
        "external_amount": "external",
        "exposure_sum": "abc+ext",
        "fee_old": "fee_old",
        "fee_new": "fee_new",
    }
    col_widths = {k: len(headers[k]) for k in headers}
    for row in rows:
        for k in headers:
            val = row[k]
            col_widths[k] = max(col_widths[k], len(_fmt_num(val)) if k != "coin" else len(val))

    def line(parts: dict[str, str]) -> str:
        return "  ".join(parts[k].ljust(col_widths[k]) for k in headers)

    print("fee_asset_gap 将修改为: fee_new = (abc + external) * -1\n")
    print(line({k: headers[k] for k in headers}))
    print(line({k: "-" * col_widths[k] for k in headers}))
    for row in rows:
        print(line({
            "coin": row["coin"],
            "abc_amount": _fmt_num(row["abc_amount"]),
            "external_amount": _fmt_num(row["external_amount"]),
            "exposure_sum": _fmt_num(row["exposure_sum"]),
            "fee_old": _fmt_num(row["fee_old"]),
            "fee_new": _fmt_num(row["fee_new"]),
        }))


def _fmt_num(v: Any) -> str:
    if isinstance(v, float):
        if v == 0.0:
            return "0"
        s = f"{v:.8f}".rstrip("0").rstrip(".")
        return s if s else "0"
    return str(v)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, rows: list[dict[str, Any]], label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "database": MYSQL_CONFIG["database"],
        "label": label,
        "row_count": len(rows),
        "rows": rows,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def apply_fee_updates(conn, plan: list[dict[str, Any]]) -> tuple[int, int]:
    """返回 (update_count, insert_count)。"""
    updated = 0
    inserted = 0
    with conn.cursor() as cur:
        for row in plan:
            coin = row["coin"]
            new_amount = row["fee_new"]
            cur.execute("SELECT 1 FROM `fee_asset_gap` WHERE `coin`=%s LIMIT 1", (coin,))
            exists = cur.fetchone()
            if exists:
                cur.execute(
                    "UPDATE `fee_asset_gap` SET `amount`=%s WHERE `coin`=%s",
                    (new_amount, coin),
                )
                updated += 1
            else:
                cur.execute(
                    "INSERT INTO `fee_asset_gap` (`coin`, `amount`) VALUES (%s, %s)",
                    (coin, new_amount),
                )
                inserted += 1
    return updated, inserted


def cmd_summary(args: argparse.Namespace) -> None:
    coins = _parse_coins(args.coins)

    conn = connect_mysql()
    try:
        abc, external, fee = load_gap_amounts(conn, coins)
    finally:
        conn.close()

    rows = build_summary(abc, external, fee)

    print(f"库: {MYSQL_CONFIG['database']} @ {MYSQL_CONFIG['host']}")
    print(f"共 {len(rows)} 个 coin\n")
    print_table(rows)

    if args.output:
        out = Path(args.output)
        suffix = out.suffix.lower()
        if suffix == ".json":
            write_json(out, rows, "summary")
        elif suffix == ".csv":
            write_csv(out, rows, FIELDNAMES)
        else:
            raise SystemExit("输出文件请使用 .csv 或 .json 后缀")
        print(f"\n已写入 -> {out.resolve()}")


def cmd_sync_fee(args: argparse.Namespace) -> None:
    coins = _parse_coins(args.coins)

    conn = connect_mysql(autocommit=False)
    try:
        abc, external, fee = load_gap_amounts(conn, coins)
        plan = build_fee_update_plan(abc, external, fee, coins)

        print(f"库: {MYSQL_CONFIG['database']} @ {MYSQL_CONFIG['host']}")
        print(f"待处理 {len(plan)} 个 coin\n")
        print_fee_update_table(plan)
        if not args.apply:
            print_offset(build_offset(plan))

        if args.output:
            out = Path(args.output)
            suffix = out.suffix.lower()
            if suffix == ".json":
                write_json(out, plan, "fee_sync_plan")
            elif suffix == ".csv":
                write_csv(out, plan, FEE_UPDATE_FIELDNAMES)
            else:
                raise SystemExit("输出文件请使用 .csv 或 .json 后缀")
            print(f"\n计划已写入 -> {out.resolve()}")

        if not args.apply:
            print("\n未加 --apply，未修改数据库。确认后执行:")
            print("  python scripts/hedge_gap_summary.py sync-fee --apply")
            return

        if not plan:
            print("\n无数据可更新。")
            return

        if not args.yes:
            try:
                answer = input("\n确认写入 fee_asset_gap？(yes/no): ").strip().lower()
            except EOFError:
                answer = "no"
            if answer not in ("yes", "y"):
                print("已取消。")
                conn.rollback()
                return

        offset = build_offset(plan)
        print_offset(offset)

        updated, inserted = apply_fee_updates(conn, plan)
        conn.commit()
        print(f"\n已提交: UPDATE {updated} 行, INSERT {inserted} 行")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _parse_coins(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [c.strip() for c in raw.split(",") if c.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="gap 表汇总 / 同步 fee_asset_gap")
    sub = parser.add_subparsers(dest="command")

    p_summary = sub.add_parser("summary", help="查看 abc+external 与 fee 汇总（默认）")
    p_summary.add_argument("--coins", help="仅指定币种，逗号分隔")
    p_summary.add_argument("-o", "--output", help="另存 .csv 或 .json")
    p_summary.set_defaults(func=cmd_summary)

    p_fee = sub.add_parser(
        "sync-fee",
        help="将 fee_asset_gap.amount 设为 (abc+external)*-1；默认仅预览",
    )
    p_fee.add_argument("--coins", help="仅处理指定币种，逗号分隔")
    p_fee.add_argument(
        "--apply",
        action="store_true",
        help="预览后写入数据库（建议先不加此参数查看）",
    )
    p_fee.add_argument(
        "-y", "--yes",
        action="store_true",
        help="与 --apply 联用：跳过交互确认",
    )
    p_fee.add_argument("-o", "--output", help="将变更计划另存 .csv 或 .json")
    p_fee.set_defaults(func=cmd_sync_fee)

    args = parser.parse_args()
    if args.command is None:
        args.command = "summary"
        args.func = cmd_summary
        args.apply = False
        args.yes = False

    args.func(args)


if __name__ == "__main__":
    main()
