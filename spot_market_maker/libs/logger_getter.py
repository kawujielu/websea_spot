
import time
import sentry_sdk
from config import DEBUG

import logging
from logging import handlers
from logging.handlers import RotatingFileHandler

from dingtalkchatbot.chatbot import DingtalkChatbot

# WebHook地址
webhook = "https://oapi.dingtalk.com/robot/send?access_token=a4a882c7cae53c869342712a748cca681b0db447e719c2641ff1e30fcf89a1ae"  # 座市商后端服务异常监控

# 初始化机器人小丁
xiaoding = DingtalkChatbot(webhook)


def send_dingtalk(message):
    return

    res = xiaoding.send_text(msg=message, is_at_all=True)
    print("Dingding:%s" % res)


def get_logger(filename):
    # 第一步，创建一个logger
    logger = logging.getLogger(filename)
    logger.setLevel(logging.INFO)  # Log等级总开关

    # 将root logger的权限级别设置到最高
    # logger.setLevel(logging.CRITICAL)
    # 或者移除root logger
    logger.handlers = []

    # 第二步，创建一个handler，用于写入日志文件
    # fh = RotatingFileHandler(filename, maxBytes=1024 * 1024 * 100, backupCount=10)
    # fh.setLevel(logging.INFO)

    # fh = logging.FileHandler(filename, mode='a')  # open的打开模式这里可以进行参考
    # fh.setLevel(logging.DEBUG)  # 输出到file的log等级的开关

    # 第三步，再创建一个handler，用于输出到控制台
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)  # 输出到console的log等级的开关

    fh = handlers.TimedRotatingFileHandler(filename=filename, when="D", interval=1,
                                           backupCount=2)  # filename定义将信息输入到指定的文件，
    fh.setLevel(logging.INFO)
    # when指定单位是s(秒),interval是时间间隔的频率,单位是when所指定的哟（所以，你可以理解频率是5s）；backupCount表示备份的文件个数，我这里是指定的3个文件。

    # formatter = logging.Formatter('%(asctime)s %(module)s:%(lineno)d %(message)s')  #定义输出格式

    # 第四步，定义handler的输出格式
    formatter = logging.Formatter("%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s")
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # 第五步，将logger添加到handler里面
    logger.addHandler(fh)
    logger.addHandler(ch)

    # # 日志
    # # logger.debug('这是 logger debug message')
    # # logger.info('这是 logger info message')
    # # logger.warning('这是 logger warning message')
    # # logger.error('这是 logger error message')
    # # logger.critical('这是 logger critical message')

    return logger


class LoggerSentry(object):
    def __init__(self):
        if DEBUG:
            sentry_sdk.init("http://bc06d6daf27641ce8349bf1e3c6d536e@172.31.194.84:9000/2", debug=False, sample_rate=1,
                            max_breadcrumbs=100)
            # sentry_sdk.init("http://445b2cb4729b403983c15299ec9d19aa@172.31.194.83:9000/5",debug=True,sample_rate=1,max_breadcrumbs=100)
        else:
            sentry_sdk.init("http://93ed1252f6e34683b897876a8a5fc3db@172.31.194.83:9000/36", debug=False, sample_rate=1,
                            max_breadcrumbs=100)

    def __call__(self, e):
        sentry_sdk.capture_exception(Exception(e))
        time.sleep(0.3)


logger_sentry = LoggerSentry()


if __name__ == '__main__':
    for i in range(1000):
        logger_sentry("123456------------654321%s" % i)
