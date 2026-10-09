import mysql.connector

db = mysql.connector.connect(
    host="abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    user="admin",
    password="A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    database="fund",
    port=3306  # 默认端口
)
cursor = db.cursor()

try:
    if db.is_connected():
        print("成功连接数据库")
        #cursor.execute("SHOW TABLES")       # 查看库里有哪些表
        # cursor.execute("SHOW DATABASES")    # 查看所有数据库
        #print("当前数据库包含的表：")
        #cursor.execute("KILL 1219596")
        #cursor.execute("SHOW STATUS LIKE 'Threads_connected'")  # 连接数
        #cursor.execute("SHOW VARIABLES LIKE 'max_connections'") # 最大连接数
        #cursor.execute("SHOW PROCESSLIST") # 详细连接信息
        #cursor.execute("SELECT Id, User, Host, db, Time FROM information_schema.PROCESSLIST WHERE Command = 'Sleep' AND Time > 900")
        cursor.execute("SELECT * from hedge WHERE currency = 'SPCX'")
        for table in cursor.fetchall():
            print(table)
        
        #cursor.execute(f"SELECT * FROM withdraw_deposit")
        #data = cursor.fetchall()
        #for i in data:
        #    if i[0] in ['ALCH', 'FARTCOIN', 'DYDX','H','XCO','ZEREBRO','SSBT','SEND','PIIN']:
        #        print(i)
        #print('=========='*10)
        #cursor.execute(f"SELECT * FROM exchange_symbols_referrence")
        #data = cursor.fetchall()
        #for i in data:
        #    if i[0] in ['ALCH', 'FARTCOIN', 'DYDX','H','XCO','ZEREBRO','SSBT','SEND','PIIN']:
        #        print(i)
        
except Exception as e:
    print("数据库操作错误:", e)
finally:
    cursor.close()
    db.close()

