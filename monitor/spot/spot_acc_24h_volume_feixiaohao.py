# coding=utf-8
import requests
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs import heartbeat, sendmessage


def volumn_feixiaohao():
    url = 'https://dncapi.fxhapp.com/api/v2/exchange/web-exchange?webp=1&page=1&pagesize=100&sort_type=exrank&asc=1&type=all&area='
    res = requests.get(url, timeout=10).json()['data']
    exchange = ['gate.io', 'KuCoin', 'ABC']
    exchange_dict = {}
    for i in res:
        if i['name'] in exchange:
            exchange_dict[i['name']] = i['volumn_cny'] / 100000000
    coef_gete = round(exchange_dict['gate.io'] / exchange_dict['ABC'], 2)
    coef_kucoin = round(exchange_dict['KuCoin'] / exchange_dict['ABC'], 2)
    print(exchange_dict)
    if exchange_dict['KuCoin'] * 0.93 < exchange_dict['ABC'] < exchange_dict['gate.io'] * 1.07 or exchange_dict[
        'gate.io'] * 0.93 < exchange_dict['ABC'] < exchange_dict['KuCoin'] * 1.07:
        pass
    else:
        mess = f"非小号-ER全球交易所排名-24H额(¥)\n成交量相差较大,请调整一下量\n报警频率2h一次\n" \
               f"A : {int(exchange_dict['ABC'])}亿\n" \
               f"GATEIO : {int(exchange_dict['gate.io'])}亿 [{coef_gete}倍]\n" \
               f"KUCOIN : {int(exchange_dict['KuCoin'])}亿 [{coef_kucoin}倍]\n"
        print(mess)
        sendmessage.send_telegram_msg(mess, ser='spot_info')


if __name__ == '__main__':
    try:
        volumn_feixiaohao()
    except Exception as e:
        mess = f'error：acc_24h_volume_feixiaohao-->{e}'
        sendmessage.send_telegram_msg(mess, ser='Alarm')
