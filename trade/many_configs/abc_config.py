from abcapi_plus import AbcApi
from libs import libs_config, libs_account

if libs_config.DEBUG:
    host = "https://exq.wbstests.net"
    contract_host = "https://coq.wbstests.net"
    contract_ws_host = "wss://coqws.wbstests.net"
    spot_depth_ws_host = "wss://exqws.wbstests.net"
    contract_depth_ws_host = "wss://coqws.wbstests.net"
    abc_accounts = [
        AbcApi(token=libs_account["volume_first"]["token"], secret_key=libs_account["volume_first"]["sk"], ),

    ]
else:
    host = "https://exqv.websea.work"
    contract_host = "https://coqv.websea.work"  # 8.210.120.220 对应的IP
    contract_ws_host = "wss://coqvws.websea.work"
    spot_depth_ws_host = "wss://exqvws.websea.work"
    contract_depth_ws_host = "wss://coqvws.websea.work"
    abc_accounts = [
        AbcApi(token=libs_account["volume_first"]["token"], secret_key=libs_account["volume_first"]["sk"], ),
        # AbcApi(token=libs_account["volume_second"]["token"], secret_key=libs_account["volume_second"]["sk"],),
    ]

contract_ask = AbcApi(token=libs_account["contract_volume"]["token"],
                      secret_key=libs_account["contract_volume"]["sk"], )
contract_bid = AbcApi(token=libs_account["contract_volume"]["token"],
                      secret_key=libs_account["contract_volume"]["sk"], )

contract_volume_flash1 = AbcApi(token=libs_account["contract_volume_flash1"]["token"],
                                secret_key=libs_account["contract_volume_flash1"]["sk"], )
contract_volume_flash2 = AbcApi(token=libs_account["contract_volume_flash2"]["token"],
                                secret_key=libs_account["contract_volume_flash2"]["sk"], )

contract_volume_accounts = [contract_ask, contract_bid]
contract_flash_accounts = [contract_volume_flash1, contract_volume_flash2]
contract_close_accounts = [AbcApi(token=acc_token["token"], secret_key=acc_token["sk"], ) for acc_name, acc_token in
                           libs_account.items() if acc_name.startswith("contract_") and acc_token["token"]]  # "contract_" in acc_name

contract_delisting_accounts = [AbcApi(token=acc_token["token"], secret_key=acc_token["sk"], ) for acc_name, acc_token in
                               libs_account.items() if acc_name in ["contract_volume", "contract_near", "contract_defense", "contract_depth"]]

all_contract_accounts = contract_close_accounts
