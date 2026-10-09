from libs import libs_price
symbols_info = [('APE-USDT', None), ('APT-USDT', None), ('ATOM-USDT', None), ('AVAX-USDT', None), ('BCH-USDT', None), ('BNB-USDT', None), ('CFX-USDT', None), ('DOGE-USDT', None), ('DOT-USDT', None), ('ENS-USDT', None), ('ETC-USDT', None), ('FIL-USDT', None), ('LINK-USDT', None), ('LTC-USDT', None), ('OP-USDT', None), ('TRX-USDT', None), ('XRP-USDT', None), ('SOL-USDT', None), ('ARB-USDT', None), ('DYDX-USDT', None), ('SUI-USDT', None), ('SHIB-USDT', None), ('XEC-USDT', None), ('XMR-USDT', None), ('UNI-USDT', None), ('AAVE-USDT', None), ('AXS-USDT', None), ('GMT-USDT', None), ('LDO-USDT', None), ('XLM-USDT', None)]
symbols_info =  [('BTC-USDT', None), ('ETH-USDT', None), ('ADA-USDT', None)]
for symbol, price in symbols_info:
    libs_price.redis_db_contract_price.delete(symbol)
