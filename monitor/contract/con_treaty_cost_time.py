import json
import time
import traceback
import asyncio
from loguru import logger
import sys, os

file = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(file)
from libs import heartbeat, sendmessage
from config.infor_contract import SYMBOLS_CONTRACT_PAIR
from contract.contract_exchange_precision import BinanceApi, OkexApi, GateioApi, AbcApi, ADJUSTED_FUNDING_RATE_CAP_FLOOR, filename

exchanges = {
    'bn': BinanceApi(),
    'okex': OkexApi(),
    'gate': GateioApi(),
    'abc': AbcApi(),

}


async def get_intervalHours():
    try:
        exchange_symbols = json.load(open(filename))
        exchange_symbols.pop("time", "")

        exchange_symbols = {ex: list(set(v.keys()) & set(SYMBOLS_CONTRACT_PAIR)) for ex, v in exchange_symbols.items()}

    except:
        mm = traceback.format_exc()
        exchange_symbols = {i: {} for i in exchanges}

    for ex in exchanges:
        await exchanges[ex].interval_hours(symbols=exchange_symbols[ex])
        if ex in ['bn']:
            ADJUSTED_FUNDING_RATE_CAP_FLOOR[ex].update({s: {'fundingIntervalHours': 8} for s in set(exchange_symbols[ex]) - set(ADJUSTED_FUNDING_RATE_CAP_FLOOR[ex].keys())})

    exs = sorted(exchanges.keys())
    data = []
    msg = ""
    msg1 = ""
    for s in sorted(SYMBOLS_CONTRACT_PAIR):
        d = {'symbol': s}
        intervalHours = []
        for ex in exs:
            fundingIntervalHours = ADJUSTED_FUNDING_RATE_CAP_FLOOR.get(ex, {}).get(s, {}).get('fundingIntervalHours')
            if fundingIntervalHours:
                intervalHours.append(fundingIntervalHours)
            else:
                fundingIntervalHours = '-'
            d[ex] = fundingIntervalHours
        if len(set(intervalHours)) > 1:
            data.append(d)
            coin = s.replace('-USDT', '')
            msg += f"""`{coin.center(8, " ")} {str(d['abc']).center(3, " ")}  {str(d['bn']).center(3, " ")} {str(d['okex']).center(3, " ")} {str(d['gate']).center(3, " ")}`\n"""

    if msg:
        message = f"""`{"coin".center(8, " ")} {"abc".center(3, " ")} {"bn".center(3, " ")}{"ok".center(3, " ")} {"gate".center(3, " ")}` \n{msg}"""
        sendmessage.send_telegram_msg_mdv2(message=message, ser='fund_rate')


async def contract_run():
    try:
        await get_intervalHours()
        await heartbeat.i_live_well(server='资金费率结算时间', frequency=60 * 60 * 24 * 2.1, index=35)
        logger.info(f"资金费率结算时间 ok")
    except:
        mm = traceback.format_exc()
        sendmessage.send_telegram_msg(f'资金费率结算时间\n{mm}', ser='Alarm')
        logger.error(f" error:资金费率结算时间")


if __name__ == "__main__":
    asyncio.run(contract_run())
