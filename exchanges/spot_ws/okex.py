import base64
import hmac
import time
from many_configs.account_config import EXTERNAL_ACCOUNTS
from many_configs.exchange_config import EXCHANGE_CONFIG

OKEX_WS_PRIVATE_URL = EXCHANGE_CONFIG['okex']['private_ws']


class OkexWs:
    exchange_name = 'okex'
    method = "GET"
    body = ""

    def __init__(self, api_key=None, secret_key=None, passphrase=None):
        self.__apiKey = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]['apiKey']
        self.__secretKey = secret_key if secret_key else EXTERNAL_ACCOUNTS[self.exchange_name]['secret']
        self.__passphrase = passphrase if passphrase else EXTERNAL_ACCOUNTS[self.exchange_name]['password']

    @staticmethod
    def get_unix_timestamp():
        return str(round(time.time()))

    @staticmethod
    def pre_hash(timestamp, method, request_path, body):
        return str(timestamp) + str.upper(method) + request_path + body

    @staticmethod
    def sign_encode(message, secret_key):
        mac = hmac.new(
            bytes(secret_key, encoding="utf8"),
            bytes(message, encoding="utf-8"),
            digestmod="sha256",
        )
        d = mac.digest()
        return base64.b64encode(d)

    def get_ws_sign(self, request_path="/users/self/verify"):
        timestamp = self.get_unix_timestamp()
        sign = self.sign_encode(
            self.pre_hash(timestamp, self.method, request_path, str(self.body)),
            self.__secretKey,
        )  # 签名
        return str(sign, encoding="utf8")

    def get_ws_header(self, request_path="/users/self/verify"):
        timestamp = self.get_unix_timestamp()
        sign = self.sign_encode(
            self.pre_hash(timestamp, self.method, request_path, str(self.body)),
            self.__secretKey,
        )  # 签名
        header = dict()
        header["apiKey"] = self.__apiKey
        header["sign"] = str(sign, encoding="utf-8")
        header["timestamp"] = timestamp
        header["passphrase"] = self.__passphrase
        return header


okex_ws = OkexWs()
