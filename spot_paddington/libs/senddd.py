# pip3 install python-telegram-bot --upgrade
import datetime
import time
import ujson
from ujson import JSONDecodeError
import requests
import logging
import asyncio

import traceback
import uvloop
from aiohttp import ClientSession, TCPConnector
from loguru import logger

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

try:
    JSONDecodeError = JSONDecodeError
except AttributeError:
    JSONDecodeError = ValueError

'''
例子：
from telegram import MessageEntity
# await bot.send_message(text='test', chat_id=-876344682)  # 三二一
# await bot.send_contact(phone_number='85253467312', first_name='w', last_name='lynne', chat_id=5078399772)
# markdown = """*bold text*
#            _italic text_
#            [text](https://www.baidu.com)
#            `code`
#            ![RUNOOB 图标](http://static.runoob.com/images/runoob-logo.png)
#            """
# await bot.send_message(text=markdown, parse_mode='markdown', chat_id=chat_id)
# msg = 'Test for @lynne_w link http://www.baidu.com/\n\ntest1'
# test_entities = [
#     {
#         "length": 8,
#         "offset": 10,
#         "type": "mention",
#     },
#     {"length": 4, "offset": 18, "type": "text_link", "url": "http://www.baidu.com/"},
#     {"length": 18, "offset": 19, "type": "url"},
# ]
# await bot.send_message(text=msg,
#                        entities=[MessageEntity(**e) for e in test_entities], chat_id=chat_id)
'''

tgtalk = {
    "price": {
        "token": '5644593013:AAFvM7U2fltPTueKyNz7ie_A9LXgk9vghcI',
        "chat_id": '-1002103557007'
    },
    "volume": {
        "token": '5644593013:AAFvM7U2fltPTueKyNz7ie_A9LXgk9vghcI',
        "chat_id": '-1002103557007'
    },
    "depth_price": {
        "token": '5644593013:AAFvM7U2fltPTueKyNz7ie_A9LXgk9vghcI',
        "chat_id": '-1002103557007'
    },
    "price_check": {
        "token": '5644593013:AAFvM7U2fltPTueKyNz7ie_A9LXgk9vghcI',
        "chat_id": '-1002103557007'
    },
    "monitor": {
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
    },
    "contract_offset": {
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
    },
    "contract_close": {
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
    },
    "abc_contract_price": {
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
    },
    "": {
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
    },
    "send_telegram_msg_url": {
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
    },
    "send_telegram_important_msg_url": {
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
    },
    "async_abc_contract_ask_bid_price_ws": {
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
    },
    "async_abc_ask_bid_price_ws": {
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
    },
    "contract_price_by_contract_ask_bid": {
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
    },
    "dex_hedge": {
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-5287616263'
    },
    "spot_hedge": {
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-5287616263'
    },
    "spot_hedge_order": {
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-4892746316'
    },
}

TG_MSG_TIMEOUT = 10


class TelegramBot:
    def __init__(self, token):
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.times = 0
        self.start_time = 0

    def post(self, data):
        self.times += 1
        self.times = 0 if self.times == 200000 else self.times  # 防止溢出
        if self.times % 20 == 0:
            if time.time() - self.start_time < 60:
                logger.error(f"钉钉官方限制每个机器人每分钟最多发送20条，当前消息发送频率已达到限制条件，休眠一分钟")
                self.times = 19
                return
        self.start_time = time.time()
        requests.post(self.url, data=data, timeout=TG_MSG_TIMEOUT)


syncbot = {ser: TelegramBot(tgtalk[ser]['token']) for ser in tgtalk}


def send_telegram_msg(message, ser="send_telegram_msg_url", debug=False):
    if debug:
        return
    try:
        data = {
            'chat_id': tgtalk[ser]['chat_id'],
            'text': message
        }
        syncbot[ser].post(data)
    except BaseException as e:
        logger.error(f"send_telegram_msg {traceback.format_exc()}")


def send_telegram_important_msg(message, ser="send_telegram_important_msg_url", debug=False):
    if debug:
        return
    try:
        data = {
            'chat_id': tgtalk[ser]['chat_id'],
            'text': message
        }
        syncbot[ser].post(data)
    except BaseException as e:
        logger.error(f"send_telegram_important_msg {traceback.format_exc()}")


def send_telegram(message, ser, debug=False):
    if debug:
        return
    try:
        message = f"{datetime.datetime.now()} {ser} {message}"
        logger.info(f"send_telegram {message}")
        data = {
            'chat_id': tgtalk[ser]['chat_id'],
            'text': message
        }
        syncbot[ser].post(data)
    except BaseException as e:
        print("send_telegram", e)


async def send_tg_msg_async(bot, message, chat_id):
    if hasattr(bot, "_times"):
        bot._times += 1
    else:
        bot._times = 0
    if not hasattr(bot, "_start_time"):
        bot._start_time = 0

    bot._times = 0 if bot._times == 10 ** 10 else bot._times  # 防止溢出
    if bot._times % 20 == 0:
        if time.time() - bot._start_time < 60:
            print(f'{datetime.datetime.now()}, 钉钉官方限制每个机器人每分钟最多发送20条，当前消息发送频率已达到限制条件，休眠一分钟, data:{message}')
            bot._times = 19
            return
    bot._start_time = time.time()

    return await bot.send_message(text=message, chat_id=chat_id,
                                  pool_timeout=TG_MSG_TIMEOUT,
                                  read_timeout=TG_MSG_TIMEOUT,
                                  write_timeout=TG_MSG_TIMEOUT,
                                  connect_timeout=TG_MSG_TIMEOUT)


class TelegramBotAsync:
    def __init__(self, token):
        self.token = token
        self.session = None
        self.times = 0
        self.start_time = 0

    def __del__(self):
        if self.session:
            asyncio.run(self.session.close())

    @property
    def request(self):
        if not self.session:
            self.session = ClientSession(base_url=f"https://api.telegram.org",
                                         loop=asyncio.get_running_loop(),
                                         headers={'Content-Type': 'application/json'},
                                         timeout=0.5,
                                         connector=TCPConnector(limit=100)
                                         )
        return self.session

    async def post(self, data):
        # return
        self.times += 1
        self.times = 0 if self.times == 200000 else self.times  # 防止溢出
        if self.times % 20 == 0:
            if time.time() - self.start_time < 60:
                print(
                    f'{datetime.datetime.now()}, TG官方限制每个机器人每分钟最多发送20条，当前消息发送频率已达到限制条件，休眠一分钟, data:{data}')
                self.times = 19
                return
        self.start_time = time.time()
        async with self.request.post(f"/bot{self.token}/sendMessage", data=ujson.dumps(data),
                                     timeout=10) as response:
            res = await response.json()
            # {'ok': True, 'result': {'message_id': 3992, 'from': {'id': 5644593013, 'is_bot': True, 'first_name': 'monitor', 'username': 'TTMonitorBot'}, 'chat': {'id': -808739426, 'title': '12345', 'type': 'group', 'all_members_are_administrators': True}, 'date': 1679848881, 'text': 'async trade test message hb'}}
            if not res.get("ok"):
                logger.info(f"{res}")


tgbot_async = {ser: TelegramBotAsync(tgtalk[ser]['token']) for ser in tgtalk}


async def send_telegram_msg_async(message, ser="send_telegram_msg_url", debug=False):
    if debug:
        return
    try:
        data = {
            'chat_id': tgtalk[ser]['chat_id'],
            'text': message
        }
        await tgbot_async[ser].post(data)
    except BaseException as e:
        print("send_telegram_msg_async", e)


async def send_telegram_important_msg_async(message, ser="send_telegram_important_msg_url", debug=False):
    if debug:
        return
    try:
        data = {
            'chat_id': tgtalk[ser]['chat_id'],
            'text': message
        }
        await tgbot_async[ser].post(data)
    except BaseException as e:
        print("send_telegram_important_msg_async", e)


async def send_telegram_async(message, ser, debug=False):
    if debug:
        return
    try:
        data = {
            'chat_id': tgtalk[ser]['chat_id'],
            'text': f"{datetime.datetime.now()} {ser} {message}"
        }
        await tgbot_async[ser].post(data)
    except BaseException as e:
        print("send_telegram_async", e)


if __name__ == '__main__':
    # times = 0
    # while 1:
    #     times += 1
    #     data = datetime.datetime.now()
    #     send_dingtalk(f"{data}-{times}", "test")
    #     time.sleep(0.1)
    # msg = 'trade test message'
    # send_telegram_msg(msg, "send_telegram_msg_url")
    async def test():
        t = []
        for i in range(10):
            t.append(asyncio.create_task(
                send_telegram_msg_async(f"async trade test message hb {i}", "send_telegram_msg_url")))
        for i in t:
            await i


    asyncio.run(test())
