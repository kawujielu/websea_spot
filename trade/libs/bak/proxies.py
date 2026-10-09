import base64
import hmac
import hashlib
import time
import uuid
import requests

api_key = '08t3cae7vq2dzrdt2a7shalqiwdszplw'
orderid = "977292244937753"
endpoint = '/api/getdps'


# 生成签名原文字符串
def get_string_to_sign(method, endpoint, params):
    s = method + endpoint + '?'
    query_str = '&'.join("%s=%s" % (k, params[k]) for k in sorted(params))
    return s + query_str


# 生成签名串
def sign_str(key, s, method):
    hmac_str = hmac.new(key.encode('utf8'), s.encode('utf8'), method).digest()
    return base64.b64encode(hmac_str)


def get_ip(num):
    data = {"timestamp": int(time.time()), "nonce": uuid.uuid4().hex[:8], "sign_type": "hmacsha1", "num": num,
            "orderid": orderid}
    s = get_string_to_sign("GET", endpoint, data)
    data["signature"] = sign_str(api_key, s, hashlib.sha1)
    r = requests.get("http://dps.kdlapi.com" + endpoint, params=data, timeout=6)
    try:
        ip = r.text
    except:
        ip = ''
    return ip


def get_ip_plus(num=1):
    for i in range(5):
        ip = get_ip(num)
        if ip:
            return ip
        else:
            continue
    return ""


def get_balance():
    data = {"timestamp": int(time.time()),  "sign_type": "hmacsha1", "nonce": uuid.uuid4().hex[:8],
            "orderid": orderid}
    s = get_string_to_sign("GET", "/api/getipbalance", data)
    data["signature"] = sign_str(api_key, s, hashlib.sha1)
    r = requests.get("http://dps.kdlapi.com/api/getipbalance", params=data)
    print(r.text)

