#!/usr/bin/env python
# -*- coding: utf-8 -*-
import urllib3
import pandas as pd
import time, datetime
from loguru import logger
import asyncio
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs import heartbeat, sendmessage
from spot.spot_setting import get_trade, get_symbols, get_precision
from config import infor

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

Offline = infor.SYMBOLS_OUT
sleep_timeout = 24 * 60 * 60 * 1
DIGIT = {1: 4,
         10: 3,
         100: 2,
         1000: 1,
         10000: 0
         }
DIGIT_PRICE = 6


def price_digit():
    mess, mess1 = "", ""
    symbols = get_symbols()
    rate = get_trade(symbols)
    precisions = get_precision()
    for symbol, price in rate.items():
        first, second = symbol.split('-')
        if first in infor.SYMBOLS_LIST:
            try:
                int_price, decimal_price = price.split('.')
                if int(int_price) == 0:
                    # price_len = len(str(int(decimal_price)))  # 数字长度
                    # price_len = len(decimal_price.lstrip('0'))  # 数字长度，保留前导0（只去除全部为0的情况）
                    price_len = len(decimal_price)
                    price_precision = len(decimal_price)  # 价格当前精度
                    price_len_all = price_len
                else:
                    price_len = len(decimal_price)  # 数字长度
                    price_precision = len(decimal_price)  # 价格当前精度
                    price_len_all = price_len + len(int_price)
                print(f"{symbol} {price=} {price_len=} {len(int_price)=} {price_precision=} {price_len_all=}")
            except:
                int_price = len(price)
                price_len = 0
                price_precision = 0
                price_len_all = price_len + int_price
            precision = int(precisions[symbol]['price'])  # 价格默认精度
            if float(price) < 1:
                if DIGIT[1] - price_len > precision - price_precision:
                    coef_digit = (DIGIT[1] - price_len) - (precision - price_precision)
                    mess += f"【{symbol}】:{price} 默认价格精度:{precision} 页面精度:{price_precision}=>需要多调整{coef_digit}位精度\n"
            elif float(price) < 10:
                coef_digit = (DIGIT[10] - price_len) - (precision - price_precision)
                if DIGIT[10] - price_len > precision - price_precision:
                    mess += f"【{symbol}】:{price} 默认价格精度:{precision} 页面精度:{price_precision}=>需要多调整{coef_digit}位精度\n"
            elif float(price) < 100:
                coef_digit = (DIGIT[100] - price_len) - (precision - price_precision)
                if DIGIT[100] - price_len > precision - price_precision:
                    mess += f"【{symbol}】:{price} 默认价格精度:{precision} 页面精度:{price_precision}=>需要多调整{coef_digit}位精度\n"
            elif float(price) < 1000:
                coef_digit = (DIGIT[1000] - price_len) - (precision - price_precision)
                if DIGIT[1000] - price_len > precision - price_precision:
                    mess += f"【{symbol}】:{price} 默认价格精度:{precision} 页面精度:{price_precision}=>需要多调整{coef_digit}位精度\n"
            elif float(price) < 10000:
                coef_digit = (DIGIT[10000] - price_len) - (precision - price_precision)
                if DIGIT[10000] - price_len > precision - price_precision:
                    mess += f"【{symbol}】:{price} 默认价格精度:{precision} 页面精度:{price_precision}=>需要多调整{coef_digit}位精度\n"
            # if price_len_all >= DIGIT_PRICE and symbol not in ['BTC-USDT', 'ETH-USDT']:
            #     mess1 += f"【{symbol}】:{price} 默认价格精度:{precision} 页面精度:{price_precision} 价格有效位数:{price_len_all}\n"

    message = ""
    if mess:
        message = f'【现货】值班人员需要确认信息无误后，登陆后台管理调整价格精度 ({int(sleep_timeout / 60)}min/次)\n{mess}\n'
    if mess1:
        message = f'【现货】有效价格位数 ≥ {DIGIT_PRICE} ({int(sleep_timeout / 60)}min/次)\n{mess1}'
    return message


async def spot_run():
    while True:
        try:
            mess = price_digit()
            if mess != "":
                sendmessage.send_telegram_msg(message=mess, ser='precision')
            await heartbeat.i_live_well(server='现货价格精度监控', frequency=sleep_timeout + 60 * 5, index=30)
            print('价格精度监控', 'ok')
        except BaseException as e:
            mess = f'error：价格精度监控-spot_acc_precision_price-->{e}'
            sendmessage.send_telegram_msg(mess, ser='Alarm')
        finally:
            await asyncio.sleep(sleep_timeout)


if __name__ == '__main__':
    asyncio.run(spot_run())
