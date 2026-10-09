# pip3 install python-telegram-bot --upgrade
import copy
import datetime
import time
import ujson
import requests
from loguru import logger
import asyncio
import telegram

# from telegram import MessageEntity
# 5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw
tgtalk = {
    # "EmerWarning": {  # 紧急情况预警
    #     "token":x "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
    #     "chat_id": '-990404523'},
    "spot_contract_profitLoss": {
        "token": "6499319278:AAHxz0KPvrpGhsNHk3zzj_xG6QXCBbYnjTg",
        "chat_id": '-1001908814686'
    },
    "EmerWarning1": {  # 紧急情况预警-all
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-1001973998142'},
    "EmerWarning": {  # 紧急情况预警
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-5287616263'},
    "Alarm": {
        "token": "6431006677:AAFPjHsu3ZiowA8vyKYPmK8-b-XSPnBUu3Q", #"5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-4879856945' #'6876856110'  # '5612428231'
    },
    "spot_hedge": {  # 紧急情况预警
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-5287616263'
    },
    "spot_ProfitLoss": {
        # "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        # "chat_id": '-931210697'
        "token": "6499319278:AAHxz0KPvrpGhsNHk3zzj_xG6QXCBbYnjTg",
        "chat_id": '-1001525061586'
    },
    "spot_info": {
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-1002166252975'
    },
    "contract_info": {
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-1001968975396'
    },
    "contract_info_user": {
        # "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        # "chat_id": '-1001803986391'
        "token": "6499319278:AAHxz0KPvrpGhsNHk3zzj_xG6QXCBbYnjTg",
        "chat_id": '-1001803986391'
    },
    "contract_ProfitLoss": {
        # "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        # "chat_id": '-931210697'
        "token": "6499319278:AAHxz0KPvrpGhsNHk3zzj_xG6QXCBbYnjTg",
        "chat_id": '-1001525061586'
    },
    "dex_info": {
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-963846427'
    },
    "redis_price": {  # 紧急情况预警
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-1002100756716'},
    "fund_rate": {  # 紧急情况预警
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-1001978511156'},
    "depth": {
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-1001898787256'},
    "precision": {
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-1001898787256'},
    "kline": {
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-1001928203806'},
    "updata_currency": {
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-1002199981877'},
    # "chat_id": '-1002023163046'},
    "mongo_and_abc": {
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-1001976578125'
    },
    "depth5_abc_bitget": {
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-1002156559872'
    },
    "hedge_contract": {
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-1002223712599'
    },
    "quant_deal_history": {
        "token": "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw",
        "chat_id": '-1002230923883'
    },
}
TG_MSG_TIMEOUT = 2


class TelegramBot:
    def __init__(self, token):
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.url_chatId = f'https://api.telegram.org/bot{token}/getUpdates'  # 获取chat_id
        self.times = 0
        self.start_time = 0

    def post(self, data):
        self.times += 1
        self.times = 0 if self.times == 200000 else self.times  # 防止溢出
        if self.times % 20 == 0:
            if time.time() - self.start_time < 60:
                print(
                    f'{datetime.datetime.now()}, 当前消息发送频率已达到限制条件，休眠一分钟, data:{data}')
                self.times = 19
                return
        self.start_time = time.time()

        message = copy.deepcopy(data['text'])
        for i in range(int(len(message) / 4000) + 1):
            data['text'] = message[i * 4000:(i + 1) * 4000]
            res = requests.post(self.url, data=data, timeout=TG_MSG_TIMEOUT)
            print(res.json())
            time.sleep(0.2)

    def chat_id(self):
        res = requests.get(self.url_chatId, timeout=TG_MSG_TIMEOUT)
        print(res.json())


def send_telegram_msg(message, ser):
    try:
        # logger.info(message)
        data = {
            'chat_id': tgtalk[ser]['chat_id'],
            'text': message
        }
        TelegramBot(token=tgtalk[ser]['token']).post(data)
    except BaseException as e:
        logger.error(f"send_telegram_msg {message} {e}")


def send_telegram_msg_mdv2(message, ser):
    try:
        # logger.info(message)
        message = message.replace('(', '\\(').replace(')', '\\)').replace('-', '\\-').replace('.', '\\.').replace('>', '\\>').replace('_', '\\_').replace('{', '\\{').replace('}', '\\}')
        data = {
            'chat_id': tgtalk[ser]['chat_id'],
            'text': message,
            'parse_mode': 'MarkdownV2'
        }
        TelegramBot(token=tgtalk[ser]['token']).post(data)
    except BaseException as e:
        logger.error(f"send_telegram_msg {message} {e}")


def send_telegram_msg_html(message, ser):
    try:
        # logger.info(message)
        data = {
            'chat_id': tgtalk[ser]['chat_id'],
            'text': message,
            'parse_mode': 'HTML'
        }
        TelegramBot(token=tgtalk[ser]['token']).post(data)
    except BaseException as e:
        logger.error(f"send_telegram_msg {message} {e}")


if __name__ == '__main__':
    data = """hahah"""
    send_telegram_msg(message='updata_currency', ser='updata_currency')
