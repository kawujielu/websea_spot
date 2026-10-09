# -*- coding: utf-8 -*-
"""对比 hedge 表两个时间点，找出 dc当前值 有差异的 currency"""
import pymysql

# ========== 参数 ==========
HOST = "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com"
USER = "admin"
PASSWORD = "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2"
DB = "fund"
PORT = 3306
T1 = "2026-08-01 00:05:14"
T2 = "2026-08-01 00:10:05"
# ==========================

conn = pymysql.connect(host=HOST, user=USER, password=PASSWORD, database=DB, port=PORT, charset="utf8mb4")
cur = conn.cursor()
cur.execute(
    "SELECT currency, time, `dc当前值` FROM hedge WHERE time IN (%s, %s) ORDER BY currency, time",
    (T1, T2),
)
rows = cur.fetchall()
cur.close()
conn.close()

# currency -> {time: dc}
data = {}
for currency, tm, dc in rows:
    data.setdefault(str(currency), {})[str(tm)] = dc

print(f"{'currency':<12} {'time':<22} {'dc当前值'}")
print("-" * 50)
n = 0
for cur_name in sorted(data):
    m = data[cur_name]
    if T1 not in m or T2 not in m:
        continue
    if m[T1] != m[T2]:
        n += 1
        print(f"{cur_name:<12} {T1:<22} {m[T1]}")
        print(f"{cur_name:<12} {T2:<22} {m[T2]}")
        print()
print(f"共 {n} 个 currency 的 dc当前值 不同")
