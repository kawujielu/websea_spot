# pip3 install python-telegram-bot --upgrade
import datetime
import time
import json
import requests
import asyncio
import telegram
from aiohttp import ClientSession, TCPConnector

tgtalk = {
    "error": {
        "token": '5644593013:AAFvM7U2fltPTueKyNz7ie_A9LXgk9vghcI',
        "chat_id": '5078399772'
    },
    'dw_info': {
        'token': '5644593013:AAFvM7U2fltPTueKyNz7ie_A9LXgk9vghcI',
        'chat_id': '-4613687595'
    },
    'ec2Warn': {
        'token': '5644593013:AAFvM7U2fltPTueKyNz7ie_A9LXgk9vghcI',
        'chat_id': '-1002013047053'
    },
    'AnnouncementWarn': {  # 暂停
        'token': '5644593013:AAFvM7U2fltPTueKyNz7ie_A9LXgk9vghcI',
        'chat_id': '-844795142'
    },
    'warning': {
        'token': '5644593013:AAFvM7U2fltPTueKyNz7ie_A9LXgk9vghcI',
        'chat_id': '-1002057792311'
    },
    'error_warning': {
        "token": '5644593013:AAFvM7U2fltPTueKyNz7ie_A9LXgk9vghcI',
        "chat_id": '-1002103557007'
    },
    'heart_warning': {
        "token": '5644593013:AAFvM7U2fltPTueKyNz7ie_A9LXgk9vghcI',
        "chat_id": '-1002161912773'
    },
    'yk_warning': {
        "token": "6499319278:AAHxz0KPvrpGhsNHk3zzj_xG6QXCBbYnjTg",
        "chat_id": '-1001525061586'
    },
    "send_telegram_important_msg_url": {
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
    },
}

tgbot = {ser: telegram.Bot(tgtalk[ser]['token']) for ser in tgtalk}
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
                print(
                    f'{datetime.datetime.now()}, 钉钉官方限制每个机器人每分钟最多发送20条，当前消息发送频率已达到限制条件，休眠一分钟, data:{data}')
                self.times = 19
                return
        self.start_time = time.time()
        requests.post(self.url, data=data, timeout=TG_MSG_TIMEOUT)


syncbot = {ser: TelegramBot(tgtalk[ser]['token']) for ser in tgtalk}


def send_telegram(message, ser):
    try:
        data = {
            'chat_id': tgtalk[ser]['chat_id'],
            'text': message
        }
        syncbot[ser].post(data)
    except BaseException as e:
        print("send_telegram", e)


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
        async with self.request.post(f"/bot{self.token}/sendMessage", data=json.dumps(data),
                                     timeout=10) as response:
            res = await response.json()
            if not res.get("ok"):
                print(f"{res}")
                raise Exception(f"{res}")


tgbot_async = {ser: TelegramBotAsync(tgtalk[ser]['token']) for ser in tgtalk}


async def send_telegram_async(message, ser):
    try:
        data = {
            'chat_id': tgtalk[ser]['chat_id'],
            'text': f"{message}"
        }
        await tgbot_async[ser].post(data)
    except BaseException as e:
        print("send_telegram_async", e)


async def send_telegram_markdown_async(message, ser):
    try:
        data = {
            'chat_id': tgtalk[ser]['chat_id'],
            'text': f"{message}",
            'parse_mode': 'Markdown'
        }
        await tgbot_async[ser].post(data)
    except BaseException as e:
        print("send_telegram_async", e)


async def push_msg(name, msg):
    url = 'http://52.74.21.180:8813/push'
    data = {'event_name': name, 'msg': msg, 'level': 'warning'}
    re = requests.post(url, data=data)
    print(re.text)


if __name__ == '__main__':
    asyncio.run(send_telegram_markdown_async(f"test msg", "error"))
