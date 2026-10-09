import mysql.connector

db = mysql.connector.connect(
    host="abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    user="admin",
    password="A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    database="fund", # 'hedge'
    port=3306  # 默认端口
)
cursor = db.cursor()

# db2 = mysql.connector.connect(
#     host="abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
#     user="admin",
#     password="A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
#     database="fund", # 'hedge'
#     port=3306  # 默认端口
# )
# cursor2 = db2.cursor()


try:
    if db.is_connected():
        print("成功连接数据库")
        # cursor.execute("SHOW TABLES")       # 查看库里有哪些表
        # cursor.execute("SHOW DATABASES")    # 查看所有数据库        
        # cursor.execute("DESCRIBE mongoorders")  # 查表有哪些字段
        # cursor.execute("SHOW STATUS LIKE 'Threads_connected'")  # 查看当前 MySQL 总连接数
        # cursor.execute("SHOW VARIABLES LIKE 'max_connections'")  # 查看最大连接数
        # cursor.execute("SHOW FULL PROCESSLIST")  # 查看活跃连接详情
        # cursor.execute("SHOW VARIABLES LIKE 'wait_timeout'")  # 查看超时连接配置
        cursor.execute("SET GLOBAL wait_timeout = 300")     # 设置连接超时
        data = cursor.fetchall()
        for i in data:
            print(i)
        cursor.execute("SET GLOBAL interactive_timeout = 300")  # 超过 5 分钟没用，MySQL 自动断开
        data = cursor.fetchall()
        for i in data:
            print(i)
        
        
except Exception as e:
    print("数据库操作错误:", e)
finally:
    cursor.close()
    db.close()
    # cursor2.close()
    # db2.close()
