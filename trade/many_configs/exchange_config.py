from many_configs.base_config import ExchangeCode

EXCHANGE_CONFIG = {
    ExchangeCode.bn.value: {
        "spot_ws": "wss://stream.binance.com:9443/stream", "spot_restful": "https://api.binance.com",
        "contract_ws": "wss://fstream.binance.com/stream", "contract_restful": "https://fapi.binance.com"
    },
    # ExchangeCode.hb.value: {
    #     "spot_ws": "wss://api.huobi.com/ws", "spot_restful": "https://api.huobi.pro",
    #     "contract_ws": "wss://api.hbdm.com/linear-swap-ws", "contract_restful": "https://api.hbdm.com"
    # },
    ExchangeCode.hb.value: {
        "spot_ws": "wss://api-aws.huobi.pro/ws", "spot_restful": "https://api-aws.huobi.pro",
        "contract_ws": "wss://api.hbdm.com/linear-swap-ws", "contract_restful": "https://api.hbdm.vn"
    },
    # ExchangeCode.okex.value: {
    #     "spot_ws": "wss://ws.okx.com:8443/ws/v5/public", "spot_restful": "https://www.okx.com",
    #     "contract_ws": "wss://ws.okx.com:8443/ws/v5/public", "contract_restful": "https://www.okx.com"
    # },
    ExchangeCode.okex.value: {
        "spot_ws": "wss://ws.okx.com:8443/ws/v5/public", "spot_restful": "https://www.okx.com",
        "contract_ws": "wss://ws.okx.com:8443/ws/v5/public", "contract_restful": "https://www.okx.com"
    },
    ExchangeCode.gate.value: {
        "spot_ws": "wss://api.gateio.ws/ws/v4/", "spot_restful": "https://api.gateio.ws",
        "contract_ws": "wss://fx-ws.gateio.ws/v4/ws/usdt",  # [usdt] 区
        "contract_restful": "https://api.gateio.ws/api/v4"
    },
    ExchangeCode.bitfinex.value: {
        "spot_ws": "wss://api-pub.bitfinex.com/ws/2", "spot_restful": "", "contract_ws": "", "contract_restful": ""
    },
    ExchangeCode.mxc.value: {
        "spot_ws": "wss://wbs-api.mexc.com/ws", "spot_restful": "https://www.mxc.com", "contract_ws": "",
        "contract_restful": ""
    },
    ExchangeCode.kucoin.value: {
        "spot_ws": "", "spot_restful": "https://api.kucoin.com", "contract_ws": "", "contract_restful": ""
    },
    ExchangeCode.bkex.value: {
        "spot_ws": "wss://www.bkex.co/socket.io/?EIO=3&transport=websocket", "spot_restful": "", "contract_ws": "",
        "contract_restful": ""
    },
    ExchangeCode.bitget.value: {
        "spot_ws": "wss://ws.bitget.com/spot/v1/stream", "spot_restful": "https://api.bitget.com", "contract_ws": "",
        "contract_restful": ""
    },
    ExchangeCode.kraken.value: {
        "spot_ws": "wss://ws.kraken.com/v2", "spot_restful": "https://api.kraken.com", "contract_ws": "",
        "contract_restful": ""
    },
}
