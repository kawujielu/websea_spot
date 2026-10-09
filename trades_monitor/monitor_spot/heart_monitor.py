import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs import libs_price_async
import time
import json
import asyncio
from libs.send_tglegram_msg import send_telegram_async, push_msg
from collections import defaultdict
from libs import heartbeat
import datetime

redis_db_heart_beat = libs_price_async.redis_db_heart_beat


async def handel_market_maker(key_type):
    heart_maps = await redis_db_heart_beat.async_connection.hgetall(key_type)
    server_name = "现货做市" if key_type == "HEART_BEAT_TRADE" else "合约做市"
    now_ts = time.time()
    mm_data = {'index': 0, 'name': server_name, 'pingRate': '-', 'timeout': '-', 'status': True, 'sos': '', 'note': ''}
    i = 1
    pingRates = set()
    error_list = []
    for k, v in heart_maps.items():
        v_obj = json.loads(v)
        if i == 1:
            mm_data['index'] = v_obj['index']
        timeout = now_ts - v_obj['send_time']
        pingRate = v_obj['frequency']
        pingRates.add(pingRate)
        if timeout > pingRate:
            mm_data['status'] = False
            mm_data['sos'] = v_obj['sos']
            error_list.append(k)
        i += 1
    mm_data['note'] = "#".join(error_list)
    mm_data['pingRate'] = sorted(list(pingRates))
    return mm_data


async def get_heart_info():
    heart_list = []
    # keys = ['HEART_BEAT', "HEART_BEAT_CONTRACT_TRADE", "HEART_BEAT_TRADE"]
    keys = ['HEART_BEAT', "HEART_BEAT_TRADE"]
    for db_key in keys:
        if db_key == 'HEART_BEAT':
            heart_maps = await redis_db_heart_beat.async_connection.hgetall('HEART_BEAT')
            now_ts = time.time()
            heart_dict = {}
            for k, v in heart_maps.items():
                name = k.split('#')[0]
                v_obj = json.loads(v)
                timeout = now_ts - v_obj['send_time']
                pingRate = v_obj['frequency']
                mm_data = heart_dict.get(name, {'index': v_obj['index'], 'name': name, 'pingRate': v_obj['frequency'],
                                                'timeout': timeout.__round__(2),
                                                'status': True, 'sos': v_obj['sos'], 'note': ''})
                if timeout > pingRate:
                    mm_data['status'] = False
                    mm_data['sos'] = v_obj['sos']
                    mm_data['note'] = v_obj.get('note', '') + mm_data['note']
                heart_dict[name] = mm_data
                heart_list = list(heart_dict.values())
            continue
        mm_data = await handel_market_maker(db_key)
        heart_list.append(mm_data)
    heart_list.sort(key=lambda x: x['index'])
    return {'data': heart_list, 'cur_time': time.strftime('%Y年%m月%d日 %H:%M:%S', time.localtime(int(time.time())))}


# 心跳除了这三个，如果有其他的报警， 或者着三个中任何有len(错误信息) > N ， 并且20秒检测一次 连续三次都发生报警， 就在t'g
# '刷量_下单','价格服务_去中心化','合约对标合约价格_数据库'
async def send_tg(heart_dict, old_heart_dict):
    heart_li = ['刷量_下单', '价格服务_中心化', '合约对标合约价格_数据库', '合约对标合约价格_获取价格']
    msg = '心跳长时间预警，及时通知相关人员（检测为20s/次，并连续三次)，如果心跳界面已恢复正常不用通知:\n'
    heart_info = await get_heart_info()
    for info in heart_info['data']:
        name = info['name']
        if info['status']:
            old_heart_dict[name] = None
        else:
            if name not in heart_li:
                if not old_heart_dict.get(name):
                    heart_dict[name] = []
                heart_dict[name].append(info)
                old_heart_dict[name] = info
            else:
                li_len = 10
                if name == '合约对标合约价格_获取价格':
                    li_len = 6
                note = info['note']
                if note:
                    note_li = note.split('|、')
                    note_li = [info for info in note_li if info.strip()]
                    if len(note_li) > li_len:
                        if not old_heart_dict.get(name):
                            heart_dict[name] = []
                        heart_dict[name].append(info)
                        old_heart_dict[name] = info
                    else:
                        old_heart_dict[name] = None
    for key, value in heart_dict.items():
        if len(value) >= 3:
            print(f'{key}已经持续3次报警', value)
            info = value[-1]
            if info['note']:
                if info["sos"] and info["sos"] != "**":
                    msg += f'{key} -> {info["note"]}, 超时: {info["timeout"]}s, sos: {info["sos"]}\n'
                else:
                    msg += f'{key} -> {info["note"]}, 超时: {info["timeout"]}s\n'
            else:
                if info["sos"] and info["sos"] != "**":
                    msg += f'{key} -> 超时: {info["timeout"]}s, sos: {info["sos"]}\n'
                else:
                    msg += f'{key} -> 超时: {info["timeout"]}s\n'
            heart_dict[key] = []
    print(msg)
    if msg != '心跳长时间预警，及时通知相关人员（检测为20s/次，并连续三次)，如果心跳界面已恢复正常不用通知:\n':
        msg_li = [msg[i:i + 4000] for i in range(0, len(msg), 4000)]
        for send_msg in msg_li:
            await send_telegram_async(send_msg, 'heart_warning')
            await push_msg('heart', send_msg)
    else:
        await push_msg('heart', '')
    await heartbeat.i_live_well("心跳监控", 60 * 10, 66)


async def main():
    send_msgs = {}
    heart_dict = defaultdict(list)
    old_heart_dict = {}
    while True:
        try:
            await send_tg(heart_dict, old_heart_dict)
            current_time = datetime.datetime.now().hour
            if current_time == 10 or current_time == 22:
                print(f'send heart msg is normal {send_msgs}')
                if not send_msgs.get(current_time, None):
                    await send_telegram_async('heart monitor is normal', 'heart_warning')
                    send_msgs[current_time] = True
            if current_time == 1:
                send_msgs = {}
            await asyncio.sleep(20)
        except Exception as error:
            error_msg = f'heart error:  {str(error)}'
            await send_telegram_async(error_msg[:4000], 'heart_warning')
            await asyncio.sleep(5)


if __name__ == '__main__':
    asyncio.run(main())
