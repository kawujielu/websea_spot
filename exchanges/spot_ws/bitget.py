import base64
import hmac
import time
from many_configs.account_config import EXTERNAL_ACCOUNTS
from many_configs.exchange_config import EXCHANGE_CONFIG

BITGET_WS_PRIVATE_URL = EXCHANGE_CONFIG['bitget']['private_ws']


class BitgetWs:
    exchange_name = 'bitget'

    def __init__(self, api_key=None, secret_key=None, passphrase=None):
        self.__apiKey = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]['apiKey']
        self.__secretKey = secret_key if secret_key else EXTERNAL_ACCOUNTS[self.exchange_name]['secret']
        self.__passphrase = passphrase if passphrase else EXTERNAL_ACCOUNTS[self.exchange_name]['password']

    def sign(self, message, secret_key):
        mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
        d = mac.digest()
        return str(base64.b64encode(d), 'utf8')

    def pre_hash(self, timestamp, method, request_path):
        return str(timestamp) + str.upper(method) + str(request_path)

    def check_none(self, value, msg=""):
        if not value:
            raise Exception(msg + " Invalid params!")

    def get_ws_header(self):
        self.check_none(self.__apiKey, "api key")
        self.check_none(self.__secretKey, "api secret key")
        self.check_none(self.__passphrase, "passphrase")
        timestamp = int(round(time.time()))
        sign = self.sign(self.pre_hash(timestamp, 'GET', '/user/verify'), self.__secretKey)
        header = dict()
        header["apiKey"] = self.__apiKey
        header["sign"] = sign
        header["timestamp"] = timestamp
        header["passphrase"] = self.__passphrase
        return header


bitget_ws = BitgetWs()
