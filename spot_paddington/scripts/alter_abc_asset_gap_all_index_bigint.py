"""一次性：将 hedge.abc_asset_gap_all.`index` 改为 BIGINT AUTO_INCREMENT。

用法: python scripts/alter_abc_asset_gap_all_index_bigint.py
依赖: pip install pymysql
"""
import pymysql

MYSQL = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "database": "hedge",
    "charset": "utf8mb4",
}

SQL = "ALTER TABLE abc_asset_gap_all MODIFY COLUMN `index` BIGINT NOT NULL AUTO_INCREMENT"


def main():
    conn = pymysql.connect(**MYSQL)
    try:
        with conn.cursor() as cur:
            print(f"执行: {SQL}")
            cur.execute(SQL)
            conn.commit()
            cur.execute("SHOW TABLE STATUS LIKE 'abc_asset_gap_all'")
            row = cur.fetchone()
            # Auto_increment 一般在第11列 (1-based Index=11 -> 0-based 10)
            print("完成. Auto_increment=", row[10] if row else None)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
