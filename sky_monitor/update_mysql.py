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
        
        cursor.execute(f"SELECT * FROM mongoorders")
        # cursor.execute(f"SELECT DATE(ts) AS trade_date, SUM(amountQuote) AS total_amount FROM mongoorders GROUP BY trade_date ORDER BY trade_date DESC")
        #cursor.execute(f"SELECT id, currency, wd_id, quantity, send_ts from auto_wd WHERE wd_id = '634092'")
        #cursor.execute(f"DELETE FROM auto_wd WHERE wd_id='314'")
        #db.commit()

        data = cursor.fetchall()
        print(len(data), type(data))
        for i in data[-10:]:
            print(i)
        # print('=========='*10)
        # cursor.execute(f"SELECT * FROM exchange_symbols_referrence")
        # data = cursor.fetchall()
        # for i in data:
        #     if i[0] in ['ALCH', 'FARTCOIN', 'DYDX','H','XCO','ZEREBRO','SSBT','SEND','PIIN']:
        #         print(i)
        
except Exception as e:
    print("数据库操作错误:", e)
finally:
    cursor.close()
    db.close()

