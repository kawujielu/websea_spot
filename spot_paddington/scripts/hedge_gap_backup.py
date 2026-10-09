"""
导出 / 恢复 hedge 库中三张敞口 gap 表（用于清零前备份与事后还原）。

表:
  - abc_asset_gap
  - external_asset_gap
  - fee_asset_gap

导出为 JSON，内含列名、行数据、元信息，restore 时可原样写回。

用法:

  python scripts/hedge_gap_backup.py export
  python scripts/hedge_gap_backup.py export -o D:/backup/hedge_gap.json
  python scripts/hedge_gap_backup.py export --coins BTC,ETH
  python scripts/hedge_gap_backup.py restore -i D:/backup/hedge_gap.json
  python scripts/hedge_gap_backup.py restore -i hedge_gap.json --mode upsert
  python scripts/hedge_gap_backup.py restore -i hedge_gap.json --dry-run

连接配置见本文件 MYSQL_CONFIG；USE_TEST_DB=True 时使用 hedge_test 库。

依赖: pip install pymysql
"""
from __future__ import annotations

import argparse
import decimal
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# MySQL（与 scaffold/mysql/__init__.py 中 HEDGE_MYSQL_CONFIG 一致）
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

TABLES = ("abc_asset_gap", "external_asset_gap", "fee_asset_gap")
FORMAT_VERSION = 1


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


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
        autocommit=False,
    )


class BackupEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return {"__type__": "datetime", "value": obj.isoformat(sep=" ")}
        if isinstance(obj, decimal.Decimal):
            return {"__type__": "decimal", "value": str(obj)}
        if isinstance(obj, bytes):
            return {"__type__": "bytes", "value": obj.decode("utf-8", errors="replace")}
        return super().default(obj)


def decode_value(obj: Any) -> Any:
    if isinstance(obj, dict) and "__type__" in obj:
        t = obj["__type__"]
        v = obj["value"]
        if t == "datetime":
            return v
        if t == "decimal":
            return v
        if t == "bytes":
            return v
    return obj


def decode_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: decode_value(v) for k, v in row.items()}


def fetch_table(conn, table: str, coins: list[str] | None) -> tuple[list[str], list[dict[str, Any]]]:
    with conn.cursor() as cur:
        if coins and table in TABLES:
            placeholders = ",".join(["%s"] * len(coins))
            sql = f"SELECT * FROM `{table}` WHERE `coin` IN ({placeholders})"
            cur.execute(sql, coins)
        else:
            cur.execute(f"SELECT * FROM `{table}`")
        rows = list(cur.fetchall())
        columns = [d[0] for d in cur.description] if cur.description else []
    return columns, rows


def cmd_export(args: argparse.Namespace) -> None:
    coins = [c.strip() for c in args.coins.split(",") if c.strip()] if args.coins else None

    out_path = Path(args.output) if args.output else (
        _project_root() / "backups" / f"hedge_gap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = connect_mysql()
    try:
        payload: dict[str, Any] = {
            "format_version": FORMAT_VERSION,
            "exported_at": datetime.now().isoformat(sep=" "),
            "database": MYSQL_CONFIG["database"],
            "tables": {},
            "filter_coins": coins,
        }
        for table in TABLES:
            columns, rows = fetch_table(conn, table, coins)
            payload["tables"][table] = {
                "columns": columns,
                "row_count": len(rows),
                "rows": rows,
            }
            print(f"  {table}: {len(rows)} rows")

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, cls=BackupEncoder)

        print(f"库: {MYSQL_CONFIG['database']} @ {MYSQL_CONFIG['host']}")
        print(f"已导出 -> {out_path.resolve()}")
    finally:
        conn.close()


def build_upsert_sql(table: str, columns: list[str]) -> str:
    cols = ", ".join(f"`{c}`" for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in columns if c != "coin")
    if updates:
        return (
            f"INSERT INTO `{table}` ({cols}) VALUES ({placeholders}) "
            f"ON DUPLICATE KEY UPDATE {updates}"
        )
    return f"INSERT INTO `{table}` ({cols}) VALUES ({placeholders})"


def cmd_restore(args: argparse.Namespace) -> None:
    in_path = Path(args.input)
    if not in_path.is_file():
        raise SystemExit(f"文件不存在: {in_path}")

    with open(in_path, encoding="utf-8") as f:
        payload = json.load(f, object_hook=decode_value)

    if payload.get("format_version") != FORMAT_VERSION:
        print(f"[warn] format_version={payload.get('format_version')}，仍尝试恢复")

    backup_db = payload.get("database")
    if backup_db and backup_db != MYSQL_CONFIG["database"]:
        print(
            f"[warn] 备份库名={backup_db}，当前脚本连接库={MYSQL_CONFIG['database']}"
        )

    conn = connect_mysql()
    try:
        for table in TABLES:
            block = payload.get("tables", {}).get(table)
            if not block:
                print(f"[skip] 备份中无表 {table}")
                continue

            columns = block["columns"]
            rows = [decode_row(r) for r in block["rows"]]
            print(f"  {table}: {len(rows)} rows -> mode={args.mode}")

            if args.dry_run:
                continue

            with conn.cursor() as cur:
                if args.mode == "replace":
                    cur.execute(f"DELETE FROM `{table}`")
                if not rows:
                    continue
                if args.mode == "upsert":
                    sql = build_upsert_sql(table, columns)
                else:
                    cols = ", ".join(f"`{c}`" for c in columns)
                    ph = ", ".join(["%s"] * len(columns))
                    sql = f"INSERT INTO `{table}` ({cols}) VALUES ({ph})"

                values = [tuple(row.get(c) for c in columns) for row in rows]
                cur.executemany(sql, values)

        if args.dry_run:
            print("dry-run：未写入数据库")
        else:
            conn.commit()
            print(f"库: {MYSQL_CONFIG['database']} @ {MYSQL_CONFIG['host']}")
            print(f"已从 {in_path} 恢复完成")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="hedge 库 gap 表导出 / 恢复")
    sub = parser.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser("export", help="导出三张 gap 表到 JSON")
    p_export.add_argument("-o", "--output", help="输出 JSON 路径")
    p_export.add_argument(
        "--coins",
        help="仅导出指定币种，逗号分隔，如 BTC,ETH（按 coin 列过滤）",
    )
    p_export.set_defaults(func=cmd_export)

    p_restore = sub.add_parser("restore", help="从 JSON 恢复三张 gap 表")
    p_restore.add_argument("-i", "--input", required=True, help="备份 JSON 路径")
    p_restore.add_argument(
        "--mode",
        choices=("replace", "upsert"),
        default="replace",
        help="replace=先 DELETE 全表再 INSERT；upsert=INSERT ON DUPLICATE KEY UPDATE",
    )
    p_restore.add_argument("--dry-run", action="store_true", help="只统计，不写库")
    p_restore.set_defaults(func=cmd_restore)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
