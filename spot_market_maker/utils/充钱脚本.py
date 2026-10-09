import requests
import time
from pprint import pprint
from abcapi_plus import AbcApi

DEBUG = True
demoUrl = "http://bapi.q.abc.com"

market_near_ask = {"token": 'b9a11ccf1ffa8f2fd024601221c950a5', "secret_key": 's82rsstogtsz6vqwexrm'}
market_defense_ask = {"token": '3a9a5850adaa0dd2b3d94f386a921875', "secret_key": 'cafqmikm4fdifelqsnq6'}
market_depth_ask = {"token": '9ba4eb3ff2913ca3502af507e2f1d4c2', "secret_key": 'gg6h6p5gj0hgtaa33veu'}
market_near_bid = {"token": '9acfad6be33e2e9ecb2fe48abb65de00', "secret_key": 'fmxd4pdpj85z23j4dfp8'}
market_defense_bid = {"token": '85dc1ed738e7cc8c0c079c64d9de4eab', "secret_key": 'c9d5kb2m53h1c7z1ocjs'}
market_depth_bid = {"token": 'e05aaa4490e8f2235d08c1494678f970', "secret_key": 'cqm18tj3l5dhlyi9fl3p'}
volume_ask = {"token": '6a856529edcf0bdfaa59099d34ead53c', "secret_key": 'mmpd48bi35sfseir8chj'}
volume_bid = {"token": '0c55adcd8b340634a076e166a727e819', "secret_key": 'fqws8qure80i4yw402st'}

accounts = [market_near_ask, market_defense_ask, market_depth_ask, market_near_bid, market_defense_bid, market_depth_bid,
            volume_ask, volume_bid]


def get_token():
    url = demoUrl+"/api/manager/login"
    json = {
        "name": "abc_user",
        "password": "123456",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36"}
    res = requests.post(url, data=json, headers=headers)
    content = res.json()
    token = content.get("result").get("token")
    if token:
        return token
    else:
        raise NotADirectoryError


# 获取币种id信息
def get_currency_ids():
    url = demoUrl+'/api/currency/list?page=1&page_size=1000&token=%s&language=1' % get_token()
    res = requests.get(url)
    currency_ids = res.json().get("result").get("data")
    currency_id_mapping = {x["name"]: x["id"] for x in currency_ids}
    return currency_id_mapping


# 充值金币
def manage_money_2_accounts(direct="add"):
    url = demoUrl+"/api/transfer/%s" % direct

    user_ids = {
        12: market_near_ask,
        13: market_defense_ask,
        14: market_depth_ask,
        15: market_near_bid,
        16: market_defense_bid,
        17: market_depth_bid,
        18: volume_ask,
        19: volume_bid,

    }

    new_currency = ["BTC", "ETH", "USDT"]
    currency_ids = get_currency_ids()
    currency_ids = {c: currency_ids[c] for c in currency_ids if c in new_currency}

    params = {"token": get_token(),
              "language": "1",
              }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36"}

    for user_id, token in user_ids.items():
        for currency, currency_id in currency_ids.items():
            data = {
                "status": "1",
                "type": "1",
                "user_id": user_id,
                "currency_name": currency,
                "currency": currency_id,
                "amount": "200000000"
            }
            res = requests.post(url, params=params, data=data, headers=headers)
            print(user_id, currency, res.json())
            time.sleep(0.8)


def check_accounts():
    for token in accounts:
        abc = AbcApi(**token)
        res = abc.wallet(1)
        pprint(res)
        # pprint(res.get("result"))


if __name__ == '__main__':
    # check_accounts()
    manage_money_2_accounts(direct="add")
    # manage_money_2_accounts(direct="reduce")
