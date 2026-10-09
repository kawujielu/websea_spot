import mysql.connector

db = mysql.connector.connect(
    host="abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    user="admin",
    password="A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    database="fund", # 'hedge'
    port=3306  # 默认端口
)
cursor = db.cursor()

try:
    if db.is_connected():
        print("成功连接数据库")
        # cursor.execute("SHOW TABLES")       # 查看库里有哪些表
        # cursor.execute("SHOW DATABASES")    # 查看所有数据库
        # print("当前数据库包含的表：")
        # for table in cursor.fetchall():
        #     print(table[0])
        # cursor.execute("DESCRIBE mongoorders")  # 查表有哪些字段
        # data = cursor.fetchall()
        # for i in data:
        #     print(i)
        
        # cursor.execute(f"SELECT * FROM mongoorders")
        # 算每日总成交金额
        # cursor.execute(f"SELECT DATE(ts) AS trade_date, SUM(abs(amountQuote)) AS total_amount FROM mongoorders GROUP BY trade_date ORDER BY trade_date DESC")
        # 算近1个月按交易对成交金额从小到大排序,包含交易人数和交易人次
        cursor.execute(f"SELECT symbol, "
                        "SUM(ABS(amountQuote)) AS total_amount, "
                        "COUNT(DISTINCT id) AS trader_count, "
                        "COUNT(*) AS trade_count "
                        "FROM mongoorders "
                        "WHERE ts >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH) "
                        "GROUP BY symbol "
                        "ORDER BY total_amount ASC "
                        "LIMIT 1000;")
        # 只统计每日所有交易对的交易人数和人次,成交金额
        # cursor.execute(f"SELECT DATE(ts) AS trade_date, SUM(ABS(amountQuote)) AS total_amount, COUNT(DISTINCT id) AS trader_count, COUNT(*) AS trade_count FROM mongoorders WHERE ts >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH) GROUP BY trade_date ORDER BY trade_date;")
        data = cursor.fetchall()
        print(len(data), type(data))
        for i in data:
            print(i)

        
except Exception as e:
    print("数据库操作错误:", e)
finally:
    cursor.close()
    db.close()



