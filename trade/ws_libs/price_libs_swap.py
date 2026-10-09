import traceback
import math
from web3 import Web3
from config import WS_FREQUENCY
from many_configs import global_variable
from many_configs.base_config import ExchangeCode
from libs import libs_price_async
from libs.heartbeat import i_live_transit_station
from ws_libs.mdex_libs import MdexSwap
from ws_libs.mdex_libs.v3 import uniswapV3
from libs import (decorator, s_dex_mappers, eth_node_pools, bsc_node_pools, heco_node_pools, matic_node_pools,
                  price_dex_price_ex_symbols, price_dex_price_ex_transfer_symbols, recode_msg)
import asyncio
from loguru import logger
from libs.config_update_ser import update_node


@decorator.monitor_handler
async def uniswap_restful(symbol, node, exchange_name):
    try:
        currency = symbol.split("-")[0]
        bsc_symbols = list(price_dex_price_ex_symbols.get(ExchangeCode.pancake.value, []))
        ex_symbols_mappers = s_dex_mappers[exchange_name]
        use_node = MdexSwap(node)
        all_symbols_mappers = ex_symbols_mappers[currency]
        pair_symbol = all_symbols_mappers["pair_name"]
        pair_address = all_symbols_mappers["pair_address"]
        first_address = all_symbols_mappers["first_address"]
        second_address = all_symbols_mappers["second_address"]
        pool_token_first = await use_node.erc20_contract(Web3.to_checksum_address(first_address))
        pool_token_second = await use_node.erc20_contract(Web3.to_checksum_address(second_address))

        first_decimal = int(all_symbols_mappers["first_decimal"])
        second_decimal = int(all_symbols_mappers["second_decimal"])
    except BaseException as e:
        logger.error(f"uniswap_restful  {e}{traceback.format_exc()}")
        await recode_msg.recode_error_msg(f"去中心化交易所{symbol}获取价格 Error 很重要！！！", 'price')
        raise e
    while True:
        try:
            # bsc有时候有的节点落后，所以需要及时选择最优节点
            if pair_symbol in bsc_symbols:
                await update_node()
                if set(global_variable.BLOCK_NODE_LAST.get("BSC", {})) != set(global_variable.BLOCK_NODE.get("BSC", {})):
                    nodes_len = len(global_variable.BLOCK_NODE["BSC"])
                    node_index = bsc_symbols.index(pair_symbol) % nodes_len
                    use_node = MdexSwap(global_variable.BLOCK_NODE["BSC"][node_index])
                    pool_token_first = await use_node.erc20_contract(Web3.to_checksum_address(first_address))
                    pool_token_second = await use_node.erc20_contract(Web3.to_checksum_address(second_address))

            base_currency, quote_currency = pair_symbol.split("-")
            abc_symbols = price_dex_price_ex_transfer_symbols[exchange_name][symbol]
            save_symbol = abc_symbols
            abc_base_currency, abc_quote_currency = abc_symbols.split("-")
            if abc_base_currency == base_currency:
                trans_symbol = f"{quote_currency}-USDT"
            else:
                trans_symbol = f"{base_currency}-USDT"

            if "USDT" in pair_symbol:
                trans_price = 1
            else:
                trans_price = await libs_price_async.get_weight_price(trans_symbol)

            if pair_symbol in price_dex_price_ex_symbols.get(ExchangeCode.uniswapv3.value, []):
                fee = all_symbols_mappers["fee"]
                uni_wrapper = uniswapV3.Uniswap(provider=node)  # pass version=2 to use Uniswap v2
                eth = Web3.to_checksum_address("0x0000000000000000000000000000000000000000")

                async def v3_get_price(_currency_address, _currency_decimal, _quote_address, _quote_decimal):
                    currency = Web3.to_checksum_address(_currency_address)

                    amount = math.ceil(3000 / trans_price * 10**_quote_decimal)
                    t1 = asyncio.create_task(  # 卖1个eth
                        uni_wrapper.get_exacted_input_single(_quote_address, currency, amount, int(fee)))
                    t2 = asyncio.create_task(  # 得到1个eth
                        uni_wrapper.get_exacted_output_single(currency, _quote_address, amount, int(fee)))
                    a = await t1
                    b = await t2
                    a = 3000 / (a / math.pow(10, _currency_decimal))
                    b = 3000 / (b / math.pow(10, _currency_decimal))
                    return (a + b) / 2

                if abc_base_currency == base_currency:  # 币在交易对前面
                    currency_address = Web3.to_checksum_address(first_address)
                    decimal = first_decimal
                    quote_address = Web3.to_checksum_address(second_address)
                    quote_decimal = second_decimal
                else:
                    currency_address = Web3.to_checksum_address(second_address)
                    decimal = second_decimal
                    quote_address = Web3.to_checksum_address(first_address)
                    quote_decimal = first_decimal

                price = await v3_get_price(currency_address, decimal, quote_address, quote_decimal)
                logger.info(f"{pair_symbol} {price}")

            else:
                t1 = asyncio.create_task(pool_token_first.functions.balanceOf(Web3.to_checksum_address(pair_address)).call())
                t2 = asyncio.create_task(pool_token_second.functions.balanceOf(Web3.to_checksum_address(pair_address)).call())
                volume_first = await t1
                volume_second = await t2
                volume_first /= math.pow(10, first_decimal)
                volume_second /= math.pow(10, second_decimal)
                logger.info(f"volume amount {pair_symbol} volume_first: {volume_first} volume_second: {volume_second}")
                if abc_base_currency == base_currency:  # 币在交易对前面
                    price = (trans_price * volume_second) / volume_first
                else:
                    price = (trans_price * volume_first) / volume_second

                logger.info(f"{exchange_name =} {save_symbol =} {price =} {volume_first =} {volume_second =} {first_decimal =} {second_decimal =}")
            await libs_price_async.rs_update_price([{"symbol": save_symbol, "exchange": exchange_name, "price": price}])
            i_live_transit_station("item_instance", f"{exchange_name} {pair_symbol}", frequency=WS_FREQUENCY + 5)
            i_live_transit_station("main_instance", frequency=WS_FREQUENCY + 5)
        except BaseException as e:
            logger.error(f"uniswap_restful_{pair_symbol}_{exchange_name} {e}{traceback.format_exc()}")
            # await recode_msg.recode_error_msg(f"去中心化交易所{pair_symbol}获取价格 Error 很重要！！！", 'send_telegram_important_msg_url')
        await asyncio.sleep(3)


if __name__ == "__main__":
    pass
