# import os
# import asyncio
# import traceback
# import aiomysql
# from aiomysql import utils
# from motor.motor_asyncio import AsyncIOMotorClient
# import traceback
#
# SPOT_MYSQL_CONFIG = {
#     "host": "8.218.83.109",
#     "port": 3306,
#     "user": "fund",
#     "password": "!c0x0kapc9j%zkoenm%!(17u1@wu8j5dp#*0_*$*2#h&+n^m1!",
#     "db": "spot",
# }
#
# HEDGE_MYSQL_CONFIG = {
#     "host": "8.218.83.109",
#     "port": 3306,
#     "user": "hedge_plus",
#     "password": "!c0x0kapc9j%zkoenm%!(17u1@wu8j5dp#*0_*$*2#h&+n^m1!",
#     "db": "spot_hedge",
# }
#
# mongodb_url = "mongodb+srv://mongo-user:mongo-user@cluster0.7qe7ox5.mongodb.net/?retryWrites=true&w=majority"
#
#
# def exception_handler(func):
#     async def wrap(*args, **kwargs):
#         try:
#             result = await func(*args, **kwargs)
#             return result
#         except Exception as e:
#             print(f"{traceback.format_exc()}")
#             return False
#
#     return wrap
#
#
# class _MPoolAcquireContextManager(utils._ContextManager):
#     __slots__ = ('_coro', '_conn', '_pool')
#
#     def __init__(self, coro, pool):
#         self._coro = coro
#         self._conn = None
#         self._pool = pool
#
#     async def __aenter__(self):
#         self._conn = await self._coro
#         return self._conn
#
#     async def __aexit__(self, exc_type, exc, tb):
#         try:
#             await self._pool.release(self._conn)
#         finally:
#             pass
#
#
# utils._PoolAcquireContextManager = _MPoolAcquireContextManager
#
#
# class MysqlSession:
#     def __init__(self, mysql_config):
#         self.client = None
#         self.MYSQL_CONFIG = mysql_config
#
#     async def create_session(self):
#         if self.client is None:
#             self.client = await aiomysql.create_pool(host=self.MYSQL_CONFIG["host"],
#                                                      port=self.MYSQL_CONFIG["port"],
#                                                      user=self.MYSQL_CONFIG["user"],
#                                                      password=self.MYSQL_CONFIG["password"],
#                                                      db=self.MYSQL_CONFIG["db"],
#                                                      autocommit=True)
#         return self.client
#
#     @exception_handler
#     async def fetch_one(self, sql):
#         pool = await self.create_session()
#
#         async with pool.acquire() as conn:
#             cur = await conn.cursor()
#             await cur.execute(sql)
#             res = await cur.fetchone()
#             print(res)
#
#     @exception_handler
#     async def fetch_all(self, sql):
#         pool = await self.create_session()
#
#         async with pool.acquire() as conn:
#             cur = await conn.cursor()
#             await cur.execute(sql)
#             res = await cur.fetchall()
#             title = [i[0] for i in cur.description]
#             return res, title
#
#     @exception_handler
#     async def insert(self, sql):
#         pool = await self.create_session()
#
#         async with pool.acquire() as conn:
#             cur = await conn.cursor()
#             # number of rows that has been produced of affected
#             res = await cur.execute(sql)
#             return res
#
#     async def insert_sql(self, sql):
#         pool = await self.create_session()
#
#         async with pool.acquire() as conn:
#             await conn.begin()
#             cur = await conn.cursor()
#             try:
#                 await cur.execute(sql)
#                 await conn.commit()
#             except Exception as e:
#                 await conn.rollback()
#                 raise e
#
#
# class MongodbSession:
#
#     def __init__(self, _mongodb_url=""):
#         self.client = None
#         self._mongodb_url = mongodb_url
#
#     @property
#     def async_motor_session(self):
#         if self.client is None:
#             self.client = AsyncIOMotorClient(self._mongodb_url).abc_quant.deal
#         return self.client
#
#
# G_MysqlSession = MysqlSession(SPOT_MYSQL_CONFIG)
# Hedge_MysqlSession = MysqlSession(HEDGE_MYSQL_CONFIG)
# G_MongodbSession = MongodbSession(mongodb_url)
#
# if __name__ == '__main__':
#     sql = 'select * from reference_fund;'
#     mm, title = asyncio.run(G_MysqlSession.fetch_all(sql))
#     print(mm, title)
#
#     # loop = asyncio.new_event_loop()
#     # asyncio.set_event_loop(loop)
#     # # for i in range(1, 10000):
#     # # while True:
#     # mm, title = loop.run_until_complete(G_MysqlSession.fetch_all(sql))
#     # print(mm, title)
