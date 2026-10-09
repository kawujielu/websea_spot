from load import load_remote

REMOTE_INTERNAL_IP = "10.0.209.181"
REMOTE_IP = "10.0.209.181"

libs_config = load_remote.urllib_model("server@{}".format(REMOTE_IP), "/home/server/abclibs/config.py")
libs_price = load_remote.urllib_model("server@{}".format(REMOTE_IP, ), "/home/server/abclibs/price.py")
libs_price_async = load_remote.urllib_model("server@{}".format(REMOTE_IP, ), "/home/server/abclibs/price_async.py")
libs_account = load_remote.urllib_model("server@{}".format(REMOTE_IP, ), "/home/server/abclibs/account.py")
libs_dex_config = load_remote.urllib_model("server@{}".format(REMOTE_IP, ), "/home/server/abclibs/dex_config.py")

if libs_config.DEBUG:
    libs_account = libs_account.account_test
else:
    libs_account = libs_account.account


s_dex_mappers = libs_dex_config.s_dex_mappers

eth_node_pools = libs_dex_config.eth_node_pools
bsc_node_pools = libs_dex_config.bsc_node_pools
heco_node_pools = libs_dex_config.heco_node_pools
matic_node_pools = libs_dex_config.matic_node_pools

price_dex_price_ex_symbols = libs_config.price_dex_price_ex_symbols
price_dex_price_ex_transfer_symbols = libs_config.price_dex_price_ex_transfer_symbols
