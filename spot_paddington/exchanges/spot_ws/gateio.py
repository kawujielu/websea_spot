import hmac
import hashlib
from many_configs.account_config import EXTERNAL_ACCOUNTS
from many_configs.exchange_config import EXCHANGE_CONFIG

GATE_WS_PRIVATE_URL = EXCHANGE_CONFIG['gate']['private_ws']


class GateWs:
    exchange_name = 'gate'

    def __init__(self, api_key=None, secret_key=None):
        self.__url = GATE_WS_PRIVATE_URL
        self.__apiKey = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]['apiKey']
        self.__secretKey = secret_key if secret_key else EXTERNAL_ACCOUNTS[self.exchange_name]['secret']

    def gen_sign(self, channel, event, timestamp):
        s = 'channel=%s&event=%s&time=%d' % (channel, event, timestamp)
        sign = hmac.new(self.__secretKey.encode('utf-8'), s.encode('utf-8'), hashlib.sha512).hexdigest()
        return {'method': 'api_key', 'KEY': self.__apiKey, 'SIGN': sign}


gate_ws = GateWs()

if __name__ == '__main__':
    pass
