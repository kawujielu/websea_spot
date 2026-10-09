# pip3 install python-telegram-bot --upgrade
import datetime
import time
import json
import requests
import logging
from dingtalkchatbot.chatbot import DingtalkChatbot
import asyncio
import telegram
import loguru
from telegram import MessageEntity

try:
    JSONDecodeError = json.decoder.JSONDecodeError
except AttributeError:
    JSONDecodeError = ValueError


def post(self, data):
    """
    发送消息（内容UTF-8编码）
    :param data: 消息数据（字典）
    :return: 返回发送结果
    """
    self.times += 1
    self.times = 0 if self.times == 200000 else self.times  # 防止溢出
    if self.times % 20 == 0:
        if time.time() - self.start_time < 60:
            print(f'{datetime.datetime.now()}, 钉钉官方限制每个机器人每分钟最多发送20条，当前消息发送频率已达到限制条件，休眠一分钟, data:{data}')
            self.times = 19
            return
    self.start_time = time.time()

    post_data = json.dumps(data)
    try:
        response = requests.post(self.webhook, headers=self.headers, data=post_data, timeout=2)
    except requests.exceptions.HTTPError as exc:
        logging.error("消息发送失败， HTTP error: %d, reason: %s" % (exc.response.status_code, exc.response.reason))
        print("消息发送失败， HTTP error: %d, reason: %s" % (exc.response.status_code, exc.response.reason))
    except requests.exceptions.ConnectionError:
        logging.error("消息发送失败，HTTP connection error!")
        print("消息发送失败，HTTP connection error!")
    except requests.exceptions.Timeout:
        logging.error("消息发送失败，Timeout error!")
        print("消息发送失败，Timeout error!")
    except requests.exceptions.RequestException:
        logging.error("消息发送失败, Request Exception!")
        print("消息发送失败, Request Exception!")
    else:
        try:
            result = response.json()
        except JSONDecodeError:
            logging.error("服务器响应异常，状态码：%s，响应内容：%s" % (response.status_code, response.text))
            print("服务器响应异常，状态码：%s，响应内容：%s" % (response.status_code, response.text))
            return {'errcode': 500, 'errmsg': '服务器响应异常'}
        else:
            logging.debug('发送结果：%s' % result)
            print('发送结果：%s' % result)
            if result['errcode']:
                error_data = {"msgtype": "text", "text": {"content": "钉钉机器人消息发送失败，原因：%s" % result['errmsg']},
                              "at": {"isAtAll": True}}
                logging.error("消息发送失败，自动通知：%s" % error_data)
                if int(result['errcode']) == 130101:
                    print(f"发送超频， res:{result}")
                    self.start_time = time.time() + 10
                    self.times = 19
                else:
                    print("消息发送失败，自动通知：%s" % result)
                    requests.post(self.webhook, headers=self.headers, data=json.dumps(error_data), timeout=2)
            return result


DingtalkChatbot.post = post

dingtalk = {
    "price": {
        "url": "https://oapi.dingtalk.com/robot/send?access_token=628cd0bd63763a9c61b48a9bd2ac9824b607ac9c64b704c0422d40f779695cab"
    },
    "volume": {
        "url": "https://oapi.dingtalk.com/robot/send?access_token=628cd0bd63763a9c61b48a9bd2ac9824b607ac9c64b704c0422d40f779695cab"
    },
    "depth_price": {
        "url": "https://oapi.dingtalk.com/robot/send?access_token=628cd0bd63763a9c61b48a9bd2ac9824b607ac9c64b704c0422d40f779695cab"
    },
    # "price_check": {
    #     "url": "https://oapi.dingtalk.com/robot/send?access_token=628cd0bd63763a9c61b48a9bd2ac9824b607ac9c64b704c0422d40f779695cab"
    #     },
    "price_check": {
        "url": "https://oapi.dingtalk.com/robot/send?access_token=f47fd6b2481740353365b0c7fb8f776fd5c1d3e834b694f4bd73c0cc498a04a3"
    },
    "monitor": {
        "url": "https://oapi.dingtalk.com/robot/send?access_token=628cd0bd63763a9c61b48a9bd2ac9824b607ac9c64b704c0422d40f779695cab"
    },
    "contract_offset": {
        "url": "https://oapi.dingtalk.com/robot/send?access_token=28d98f1e333ad4a2d594d985cc64dbeb4a3e8e795f36fe0339af3d27c732c2cb"
    },
    "contract_close": {
        "url": "https://oapi.dingtalk.com/robot/send?access_token=628cd0bd63763a9c61b48a9bd2ac9824b607ac9c64b704c0422d40f779695cab"
    },
    "abc_contract_price": {
        "url": "https://oapi.dingtalk.com/robot/send?access_token=61bca7be5dc716588186018d1d73d165b5b4e6059114a9050a3263d8cd5b2fbb"
    },
    "": {
        "url": "https://oapi.dingtalk.com/robot/send?access_token=978fa6af04e42eeaa26c82be44b886c966f0cd0a551d4d1472da53beed8160c1"
    },
    "send_dingtalk_msg_url": {
        "url": 'https://oapi.dingtalk.com/robot/send?access_token=0a2d59e604aae978393d67fc2d0fbe67cf433d39af5c79952bc23ead0c54f18c'
    },
    "send_dingtalk_important_msg_url": {
        "url": 'https://oapi.dingtalk.com/robot/send?access_token=6cf72a4b64ae4e658dbc3cbe6ca78665e06e3234ef2199b9a99a4ef46d944610'
    }

}

dings = {ser: DingtalkChatbot(dingtalk[ser]['url']) for ser in dingtalk}


def send_dingtalk_msg(message, ser="send_dingtalk_msg_url", debug=False):
    if debug:
        return
    try:
        # webhook = 'https://oapi.dingtalk.com/robot/send?access_token=0a2d59e604aae978393d67fc2d0fbe67cf433d39af5c79952bc23ead0c54f18c'
        xiaoding = dings[ser]
        print("send_dingtalk", message)
        xiaoding.send_text(msg=message, is_at_all=False)
    except BaseException as e:
        print("send_dingtalk_msg", repr(e))


def send_dingtalk_important_msg(message, ser="send_dingtalk_important_msg_url", debug=False):
    if debug:
        return
    try:
        # webhook = 'https://oapi.dingtalk.com/robot/send?access_token=6cf72a4b64ae4e658dbc3cbe6ca78665e06e3234ef2199b9a99a4ef46d944610'
        xiaoding = dings[ser]
        print("send_dingtalk", message)
        xiaoding.send_text(msg=message, is_at_all=False)
    except BaseException as e:
        print("send_dingtalk_msg", repr(e))


def send_dingtalk(message, ser, debug=False):
    if debug:
        return
    try:
        xiaoding = dings[ser]
        message = "{} 频率很高的情况请报警，比如某个交易所持续断开连接 {} {}".format(datetime.datetime.now(), ser, message)
        print("send_dingtalk", message)
        xiaoding.send_text(msg=message, is_at_all=False)
    except BaseException as e:
        print("send_dingtalk", repr(e))


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
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
    },
    "volume": {
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
    },
    "depth_price": {
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
    },
    "price_check": {
        "token": '5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw',
        "chat_id": '-1001973998142'
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
    }

}

tgbot = {ser: telegram.Bot(tgtalk[ser]['token']) for ser in tgtalk}
TG_MSG_TIMEOUT = 2


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
        print("send_telegram_msg", repr(e))


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
        print("send_telegram_important_msg", repr(e))


def send_telegram(message, ser, debug=False):
    if debug:
        return
    try:
        message = f"{datetime.datetime.now()} 频率很高的情况请报警，比如某个交易所持续断开连接 {ser} {message}"
        print("send_telegram", message)
        data = {
            'chat_id': tgtalk[ser]['chat_id'],
            'text': message
        }
        syncbot[ser].post(data)
    except BaseException as e:
        print("send_telegram", repr(e))


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


async def send_telegram_msg_async(message, ser="send_telegram_msg_url", debug=False):
    if debug:
        return
    try:
        bot = tgbot[ser]
        async with bot:
            # print(await bot.get_me()) # 获取当前机器人
            # print(await bot.get_updates())  # 获取chat_id
            await send_tg_msg_async(bot, message, tgtalk[ser]['chat_id'])
    except BaseException as e:
        loguru.logger.info(f'send_telegram_msg_async ERROR {repr(e) = }')


async def send_telegram_important_msg_async(message, ser="send_telegram_important_msg_url", debug=False):
    if debug:
        return
    try:
        bot = tgbot[ser]
        async with bot:
            # print(await bot.get_me()) # 获取当前机器人
            # print(await bot.get_updates())  # 获取chat_id
            await send_tg_msg_async(bot, message, tgtalk[ser]['chat_id'])
    except BaseException as e:
        loguru.logger.info(f'send_telegram_important_msg_async ERROR {repr(e) = }')


async def send_telegram_async(message, ser, debug=False):
    if debug:
        return
    try:
        bot = tgbot[ser]
        async with bot:
            # print(await bot.get_me()) # 获取当前机器人
            # print(await bot.get_updates())  # 获取chat_id
            message = f"{datetime.datetime.now()} 频率很高的情况请报警，比如某个交易所持续断开连接 {ser} {message}"
            print("send_telegram_async", message)
            await send_tg_msg_async(bot, message, tgtalk[ser]['chat_id'])
    except BaseException as e:
        loguru.logger.info(f'send_telegram_async ERROR {repr(e) = }')


if __name__ == '__main__':
    # times = 0
    # while 1:
    #     times += 1
    #     data = datetime.datetime.now()
    #     send_dingtalk(f"{data}-{times}", "test")
    #     time.sleep(0.1)
    # msg = 'trade test message'
    # send_telegram_msg(msg, "send_telegram_msg_url")
    msg = 'async trade test message hb'
    asyncio.run(send_telegram_important_msg_async(msg))
