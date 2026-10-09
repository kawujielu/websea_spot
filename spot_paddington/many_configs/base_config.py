from enum import Enum

SANIC_HOST = "0.0.0.0"  # TODO 127.0.0.1
SANIC_PORT = 17468


class ExchangeCode(Enum):
    """
    使用：
    ExchangeCode.bn.value

    """
    bn = "bn"
    okex = "okex"
    hb = "hb"
    bitfinex = "bitfinex"
    gate = "gate"
    bkex = "bkex"
    uniswap = "uniswap"
    mxc = "mxc"
    abc = "abc"
    pancake = "pancake"
    mdex = "mdex"
    kucoin = "kucoin"
    sushi = "sushi"


class SwapCode(Enum):
    FAIL = 0
    SUCCESS = 1
    AFTER_SWAP = 2
    BEFORE_SWAP = 4
    NONCE_OCCUPY = -10000

