import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from selenium import webdriver
import time
import requests
from libs import heartbeat
import datetime
import asyncio
from libs.send_tglegram_msg import send_telegram_markdown_async
from many_configs import global_variable
from many_configs.initializer import init_share_memory
import json

NOTICE, heart = {}, {}

from selenium.webdriver.chrome.options import Options

keys = ["停机", "维护", "充值", "提币", "充提", "停止", "暂停", "关闭", "升级", "下架", "上线", "开放", "更新", "上市",
        "下线", "主网", "移除", "变更", '更名', '置换', '调整']


async def push_msg(name, msg):
    url = 'http://52.74.21.180:8813/push'
    data = {'event_name': name, 'msg': msg}
    re = requests.post(url, data=data)
    print(re.text)


async def push_msg1(name, msg):
    url = 'http://52.74.21.180:8813/push'
    data = {'event_name': name, 'msg': msg, 'level': 'warning'}
    re = requests.post(url, data=data)
    print(re.text)


def get_chrome_options():
    chrome_opt = Options()  # 创建参数设置对象.

    chrome_opt.add_argument('--headless')
    chrome_opt.add_argument('--no-sandbox')
    chrome_opt.add_argument('--disable-gpu')
    chrome_opt.add_argument('--disable-dev-shm-usage')
    chrome_opt.add_argument('lang=zh_CN.UTF-8')
    # chrome_opt.add_experimental_option('excludeSwitches', ['enable-automation'])
    # chrome_opt.add_argument(
    #     'user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36"')
    return chrome_opt


option = get_chrome_options()
notice_is_null = []


async def huobi(huobi_exs, url):
    # 火币
    exs = huobi_exs
    driver = webdriver.Chrome(options=option)
    driver.get(url)
    lists = driver.find_elements_by_xpath('//*[@class="link-dealpair"]/a')
    lists_time = driver.find_elements_by_xpath('//*[@class="date"]')
    time_now = datetime.datetime.now().strftime("%m/%d")
    if len(lists) == 0:
        notice_is_null.append('huobi')
    for i, info in enumerate(lists):
        print('huobi ---- ' + info.text)
        for k in keys:
            if k in info.text:
                link = info.get_attribute("href")
                title = info.text
                time_n = lists_time[i]
                msgs = title + '(' + time_n.text + ')'
                if '昨天' in time_n.text:
                    msg['huobi'].append(msgs)
                    print(msgs)
                    exs.append({'msg': msgs, 'link': link})
                elif '小时' in time_n.text and int(time_n.text.split('小时')[0]) <= 24:
                    msg['huobi'].append(msgs)
                    print(msgs)
                    exs.append({'msg': msgs, 'link': link})
                elif '分钟' in time_n.text and int(time_n.text.split('分钟')[0]) <= 60:
                    msg['huobi'].append(msgs)
                    print(msgs)
                    exs.append({'msg': msgs, 'link': link})
                elif time_now in time_n.text:
                    msg['huobi'].append(msgs)
                    print(msgs)
                    exs.append({'msg': msgs, 'link': link})
                elif time_now not in time_n.text:
                    break
    driver.quit()


async def huobi_notice():
    huobi_exs = []
    url_li = ['https://www.htx.com/support/zh-cn/list/360000039481',
              'https://www.htx.com/support/zh-cn/list/360000039942',
              'https://www.htx.com/support/zh-cn/list/360000039982',
              'https://www.htx.com/support/zh-cn/list/360000061481']
    for url in url_li:
        await huobi(huobi_exs, url)
    pnl_msgs = []
    for i in huobi_exs:
        if i not in pnl_msgs:
            await recode_notice_msg(i['msg'], 'huobi')
            pnl_msgs.append(i)
    await push_msg1('huobi', json.dumps(pnl_msgs))
    cu_time = int(time.time())
    heart['huobi'] = cu_time


async def okex():
    exs = []
    cur_time = time.time() * 1000
    headers = {'Accept-Language': 'zh-CN,zh;q=0.9', 'cookie': 'locale=zh_CN; preferLocale=zh_CN;','X-Site-Info':'==QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOiUGZvNmIsIyUVJiOi42bpdWZyJye'}
    url = f'https://www.okx.com/v2/support/home/web?t={cur_time}'
    res = requests.get(url, headers=headers)
    notices = res.json()['data']['notices']
    if len(notices) == 0:
        notice_is_null.append('okex')
    for info in notices:
        print('okex ---- ', info['title'])
        for k in keys:
            if k in info['title']:
                timeStamp = datetime.date.today()
                link = 'https://www.okx.com' + info['link']
                time_n = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(info['startTime'] / 1000))
                msgs = info['title'] + '(' + time_n + ')'
                if time_n >= str(timeStamp):
                    msg['okex'].append(msgs)
                    print(msgs)
                    exs.append({'msg': msgs, 'link': link})
                else:
                    break
    exs1 = await okex_status()
    exs = exs + exs1
    pnl_msgs = []
    for i in exs:
        if i not in pnl_msgs:
            await recode_notice_msg(f"[{i['msg']}]({i['link']})", 'okex')
            pnl_msgs.append(i)
    await push_msg1('okex', json.dumps(pnl_msgs))
    cu_time = int(time.time())
    heart['okex'] = cu_time


async def okex_status_V5():
    re = requests.get('https://www.okx.com/api/v5/system/status').json()
    news = re['data']
    return news


async def okex_status():
    exs = []
    result = []
    news = await okex_status_V5()
    dict_en_zh = {
        'Spot System Upgrade': '币币系统升级',
        'WebSocket System Upgrade': 'WebSocket系统升级',
        'Futures System Upgrade': '交割合约系统升级',
        'Swap System Upgrade': '永续合约系统升级',
        'Classic Account WebSocket System Upgrade': '经典账户WebSocket系统升级',
        'Perpetual Swap System Upgrade': '永续合约系统升级',
        'Options System Upgrade': '期权合约系统升级',
        "Classic Spot System Upgrade": '经典账户币币系统升级',
        "Classic Spot system upgrade": '经典账户币币系统升级',
        "Classic WebSocket System Upgrade": '经典账户websocket系统升级',
        "Classic WebSocket system upgrade": '经典账户websocket系统升级',
        "Classic Options System Upgrade": '经典账户期权合约系统升级',
        "Classic Options system upgrade": '经典账户期权合约系统升级',
        "Classic Futures System Upgrade": '经典账户交割合约系统升级',
        "Classic Perpetual Swap system upgrade": '经典账户永续合约系统升级',
        "Unified Account system upgrade": '统一账户系统升级',
        "Unified Account WebSocket system upgrade": '统一账户WebSocket系统升级',
        "Classic Account WebSocket system upgrade": '金典账户WebSocket系统升级',
        "Trading bot scheduled maintenance": '策略交易系统计划维护',
        "Trading system WebSocket scheduled maintenance": "交易系统 WebSocket 计划维护",
        "Copy trading system scheduled maintenance": "跟单交易系统计划维护",
        "Trading system scheduled maintenance (in account batches)": "交易系统计划维护 (按账户分批次)",
        "Trading system unscheduled maintenance (in account batches)": "交易系统临时维护 (按账户分批次)",
        "Trading system WebSocket unscheduled maintenance": "交易系统 WebSocket 临时维护",
        "Copy trading system unscheduled maintenance": "跟单交易系统临时维护",
        "Trading system scheduled maintenance": "交易系统计划维护",
        "Certain products scheduled maintenance": "部分交易产品计划维护",
        "Historical data services scheduled maintenance": "历史数据查询服务计划维护",
        "Asset system scheduled maintenance": "资金系统计划维护",
        "Funding system scheduled maintenance": "资金系统计划维护",
        "Trading bot unscheduled maintenance": "策略交易系统临时维护",
        "Nitro Spread system scheduled maintenance": "价差速递系统计划维护",
        "Dip Snipe, Peak Sniper system scheduled maintenance": "抄底宝，逃顶宝系统计划维护",
    }
    for i in news:
        try:
            start_ = int(int(i["begin"]) / 1000)
            end_ = int(int(i["end"]) / 1000)
            start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_))
            end = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_))
            msgs = dict_en_zh.get(i['title'], i['title']) + f' {start}~{end} {i["state"]}' + ' --- okex status'
        except:
            start = i["begin"]
            end = i["end"]
            msgs = dict_en_zh.get(i['title'], i['title']) + f' {start}~{end} {i["state"]}' + ' --- okex status'
        msg['okex_status'].append(msgs)
        exs.append({'msg': msgs, 'link': 'https://www.okx.com/cn/status'})
    for i in result:
        try:
            start_ = datetime.datetime.strptime(i["start_time"], "%Y-%m-%dT%H:%M:%S.%fZ")
            end_ = datetime.datetime.strptime(i["end_time"], "%Y-%m-%dT%H:%M:%S.%fZ")
            start = start_ + datetime.timedelta(hours=8)
            end = end_ + datetime.timedelta(hours=8)
            msgs = dict_en_zh.get(i['title'], i['title']) + f' {start}~{end} {i["maint_type"]}' + ' --- okex status'
        except:
            start = i["start_time"]
            end = i["end_time"]
            msgs = dict_en_zh.get(i['title'], i['title']) + f' {start}~{end} {i["maint_type"]}' + ' --- okex status'
        msg['okex_status'].append(msgs)
        exs.append({'msg': msgs, 'link': 'https://www.okx.com/cn/status'})
    cu_time = int(time.time())
    heart['okex_status'] = cu_time
    return exs


async def binance():
    # 币安
    exs = []
    lists = [
        'https://www.binance.com/zh-CN/support/announcement/%E6%95%B0%E5%AD%97%E8%B4%A7%E5%B8%81%E5%8F%8A%E4%BA%A4%E6%98%93%E5%AF%B9%E4%B8%8A%E6%96%B0?c=48&navId=48',
        'https://www.binance.com/zh-CN/support/announcement/%E5%B8%81%E5%AE%89%E6%9C%80%E6%96%B0%E5%8A%A8%E6%80%81?c=49&navId=49',
        'https://www.binance.com/zh-CN/support/announcement/%E5%B8%81%E5%AE%89%E6%9C%80%E6%96%B0%E6%B4%BB%E5%8A%A8?c=93&navId=93',
        'https://www.binance.com/zh-CN/support/announcement/%E6%B3%95%E5%B8%81%E5%8F%8A%E4%BA%A4%E6%98%93%E5%AF%B9%E4%B8%8A%E6%96%B0?c=50&navId=50',
        'https://www.binance.com/zh-CN/support/announcement/%E5%B8%81%E5%AE%89api%E6%9B%B4%E6%96%B0?c=51&navId=51',
        'https://www.binance.com/zh-CN/support/announcement/%E7%A9%BA%E6%8A%95?c=128&navId=128',
        'https://www.binance.com/zh-CN/support/announcement/%E9%92%B1%E5%8C%85%E7%BB%B4%E6%8A%A4%E5%8A%A8%E6%80%81?c=157&navId=157',
        'https://www.binance.com/zh-CN/support/announcement/%E4%B8%8B%E6%9E%B6%E8%AE%AF%E6%81%AF?c=161&navId=161']
    for li in lists:
        link = li
        driver = webdriver.Chrome(options=option)
        driver.get(link)
        notice_lists = driver.find_elements_by_xpath('//*[@class="css-1tl1y3y"]/a')
        notice_title = driver.find_elements_by_xpath('//*[@class="css-1tl1y3y"]/a/div[@class="css-1yxx6id"]')
        notice_time = driver.find_elements_by_xpath('//*[@class="css-1tl1y3y"]/a//h6[@class="css-eoufru"]')
        for i, info in enumerate(notice_lists):
            if info.text:
                print('binance ---- ' + info.text)
            for k in keys:
                if k in info.text:
                    time_n = notice_time[i].text
                    title = notice_title[i].text.replace(time_n, '')
                    link = info.get_attribute("href")
                    msgs = title + '(' + time_n + ')'
                    timeStamp = datetime.date.today()
                    if time_n >= str(timeStamp):
                        msg['binance'].append(msgs)
                        print(msgs)
                        exs.append({'msg': msgs, 'link': link})
                    else:
                        break
    try:
        res = requests.get('https://api.binance.com/sapi/v1/system/status').json()
        if res['status'] == 1:
            exs.append({'msg': 'binance 系统维护中', 'link': 'https://api.binance.com//wapi/v3/systemStatus.html'})
    except:
        pass
    pnl_msgs = []
    for i in exs:
        if i not in pnl_msgs:
            await recode_notice_msg(f"[{i['msg']}]({i['link']})", 'bn')
            pnl_msgs.append(i)
    await push_msg1('binance', json.dumps(pnl_msgs))
    driver.quit()
    cu_time = int(time.time())
    heart['binance'] = cu_time


async def gate_api_notice():
    exs = []
    timeStamp = datetime.date.today()
    url = 'https://api.gateio.la/api2/1/annlist?page=1&lang=cn'
    re = requests.get(url).json()['data']
    if len(re) == 0:
        notice_is_null.append('gateio')
    for i in re:
        print('gateio ---- ', i['title'])
        times = datetime.datetime.strptime(i['updated_t'], '%Y-%m-%d %H:%M:%S')
        n_time = datetime.datetime.strptime(str(timeStamp), '%Y-%m-%d')
        if times >= n_time:
            for k in keys:
                if k in i['title']:
                    msgs = i['title'] + '(' + i['updated_t'] + ')'
                    msg['gate'].append(msgs)
                    print(msgs)
                    if msgs not in exs:
                        exs.append({'msg': msgs, 'link': 'https://www.gate.tv/zh/articlelist/ann'})
        else:
            break
    pnl_msgs = []
    for i in exs:
        if i not in pnl_msgs:
            await recode_notice_msg(i['msg'], 'gate')
            pnl_msgs.append(i)
    await push_msg1('gate', json.dumps(pnl_msgs))
    cu_time = int(time.time())
    heart['gateio'] = cu_time


async def gate_notice():
    # gateio
    exs = []
    url = 'https://www.gate.tv/zh/articlelist/ann'
    driver = webdriver.Chrome(options=option)
    driver.get(url)
    lists = driver.find_elements_by_xpath(
        '//div[@class="article-list-box"]//div[@class="article-list-item"]/div[@class="article-list-item-content"]/a')
    lists_time = driver.find_elements_by_xpath(
        '//div[@class="article-list-box"]//div[@class="article-list-item-info d-flex"]/span[@class="article-list-info-timer article-list-item-info-item"]//span')
    time_now = datetime.datetime.now().strftime("%m/%d")
    if len(lists) == 0:
        notice_is_null.append('gateio')
    for i, info in enumerate(lists):
        print('gateio ---- ' + info.text)
        for k in keys:
            if k in info.text:
                link = info.get_attribute("href")
                title = info.text
                time_n = lists_time[i]
                # msgs = title + '(' + time_n.text + ')'
                msgs = title
                if '昨天' in time_n.text:
                    msg['gate'].append(msgs)
                    print(msgs)
                    exs.append({'msg': msgs, 'link': link})
                elif '小时' in time_n.text and int(time_n.text.split('小时')[0]) <= 24:
                    msg['gate'].append(msgs)
                    print(msgs)
                    exs.append({'msg': msgs, 'link': link})
                elif '分钟' in time_n.text and int(time_n.text.split('分钟')[0]) <= 60:
                    msg['gate'].append(msgs)
                    print(msgs)
                    exs.append({'msg': msgs, 'link': link})
                elif time_now in time_n.text:
                    msg['gate'].append(msgs)
                    print(msgs)
                    exs.append({'msg': msgs, 'link': link})
                elif time_now not in time_n.text:
                    break
    pnl_msgs = []
    for i in exs:
        if i not in pnl_msgs:
            await recode_notice_msg(f"[{i['msg']}]({i['link']})", 'gate')
            pnl_msgs.append(i)
    await push_msg1('gate', json.dumps(pnl_msgs))
    driver.quit()
    cu_time = int(time.time())
    heart['gateio'] = cu_time


async def huobi_sys():
    exs_true = []
    exs_false = []
    url = 'https://status.huobigroup.com/api/v2/summary.json'
    re = requests.get(url).json()
    components = re.get('components', [])
    incidents = re.get('incidents', [])
    scheduled_maintenances = re.get('scheduled_maintenances', [])
    status = re.get('status', [])
    dict_status = {'operational': '正常', 'degraded_performance': '性能下降', 'partial_outage': '部分停电',
                   'major_outage': '大停电', 'under maintenance': '维修中',
                   'investigating': '调查', 'identified': '已识别', 'monitoring': '监控中', 'resolved': '已解决',
                   'scheduled': '维护中', 'in progress': '进行中', 'verifying': '验证', 'completed': '已完成',
                   'none': '正常', 'minor': '轻微的', 'major': '严重的', 'critical': '不稳定', 'maintenance': '维修'}
    page_url = re['page']['url']
    for i in components:
        start_ = datetime.datetime.strptime(i["updated_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
        start = str(start_ + datetime.timedelta(hours=8)).split('.')[0]
        msgs = i['name'] + '  ' + dict_status.get(i['status'], i['status']) + '  (' + start + ')'
        print(msgs)
        if i['status'] == 'operational':
            exs_true.append({'msg': msgs, 'link': page_url})
        else:
            exs_false.append({'msg': msgs, 'link': page_url})
    for i in incidents:
        start_ = datetime.datetime.strptime(i["started_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
        start = str(start_ + datetime.timedelta(hours=8)).split('.')[0]
        msgs = i['name'] + '  ' + dict_status.get(i['status'], i['status']) + '  (' + start + ')' + i['impact']
        print(msgs)
        exs_false.append({'msg': msgs, 'link': page_url})
    for i in scheduled_maintenances:
        start_ = datetime.datetime.strptime(i["scheduled_for"], "%Y-%m-%dT%H:%M:%S.%fZ")
        end_ = datetime.datetime.strptime(i["scheduled_until"], "%Y-%m-%dT%H:%M:%S.%fZ")
        start = str(start_ + datetime.timedelta(hours=8)).split('.')[0]
        end = str(end_ + datetime.timedelta(hours=8)).split('.')[0]
        msgs = i['name'] + '  ' + dict_status.get(i['status'], i['status']) + '  (' + start + '~' + end + ')' + i[
            'impact']
        print(msgs)
        exs_false.append({'msg': msgs, 'link': page_url})
    if status:
        start_ = datetime.datetime.strptime(re['page']['updated_at'], "%Y-%m-%dT%H:%M:%S.%fZ")
        start = str(start_ + datetime.timedelta(hours=8)).split('.')[0]
        msgs = status['description'] + '  ' + dict_status.get(status['indicator'],
                                                              status['indicator']) + '  (' + start + ')'
        print(msgs)
        if status['indicator'] == 'none':
            exs_true.append({'msg': msgs, 'link': page_url})
        else:
            exs_false.append({'msg': msgs, 'link': page_url})
    if exs_false:
        exs = exs_false
    else:
        exs = exs_true
    pnl_msgs = []
    for i in exs:
        if i not in pnl_msgs:
            await recode_notice_msg(i['msg'], 'huobi')
            pnl_msgs.append(i)
    await push_msg1('other', json.dumps(pnl_msgs))
    cu_time = int(time.time())
    heart['hb_status'] = cu_time


async def mexc(mxc_exs, url):
    exs = mxc_exs
    headers = {
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br, zstd'
    }
    re = requests.get(url, headers=headers, timeout=10)
    notices = re.json()
    timeStamp = datetime.date.today()
    if len(notices['data']['results']) == 0:
        notice_is_null.append('mexc')
    for info in notices['data']['results']:
        print('mexc ---- ', info['title'])
        for k in keys:
            if k in info['title']:
                msgs = info['title'] + '(' + info['createdAt'] + ')'
                start = datetime.datetime.strptime(info["createdAt"], "%Y-%m-%dT%H:%M:%S.%fZ")
                now_time = datetime.datetime.strptime(str(timeStamp), "%Y-%m-%d")
                if start > now_time:
                    msg['mexc'].append(msgs)
                    print(msgs)
                    link = 'https://www.mexc.com/zh-CN/support/articles/' + str(info['id'])
                    exs.append({'msg': msgs, 'link': link})
        else:
            break


async def mxc_notice():
    mxc_exs = []
    url_li = ['https://www.mexc.com/help/announce/api/zh-CN/section/360000254192/articles?page=1&perPage=20']
    for url in url_li:
        await mexc(mxc_exs, url)
    pnl_msgs = []
    for i in mxc_exs:
        if i not in pnl_msgs:
            await recode_notice_msg(f"[{i['msg']}]({i['link']})", 'mexc')
            pnl_msgs.append(i)
    await push_msg1('mexc', json.dumps(pnl_msgs))
    cu_time = int(time.time())
    heart['mexc'] = cu_time


async def bitget_api_notice():
    bitget_exs = []
    today = datetime.date.today()
    url = f"https://api.bitget.com/api/v2/public/annoucements?language=zh_CN&annType=maintenance_system_updates"
    re = requests.get(url).json().get('data', [])
    if len(re) == 0:
        notice_is_null.append('bitget')
    for i in re:
        print('bitget ---- ', i['annTitle'])
        c_time = datetime.datetime.fromtimestamp(int(i['cTime']) / 1000)
        times = datetime.datetime.strptime(str(c_time), '%Y-%m-%d %H:%M:%S')
        n_time = datetime.datetime.strptime(str(today), '%Y-%m-%d')
        if times >= n_time:
            for k in keys:
                if k in i['annTitle']:
                    msgs = i['annTitle'] + '(' + str(c_time) + ')'
                    msg['bitget'].append(msgs)
                    print(msgs)
                    if msgs not in bitget_exs:
                        bitget_exs.append({'msg': msgs, 'link': i['annUrl']})
        else:
            break
    pnl_msgs = []
    for i in bitget_exs:
        if i not in pnl_msgs:
            await recode_notice_msg(f"[{i['msg']}]({i['link']})", 'bitget')
            pnl_msgs.append(i)
    await push_msg1('bitget', json.dumps(pnl_msgs))
    cu_time = int(time.time())
    heart['bitget'] = cu_time


async def send_heart():
    # exchanges = ['huobi', 'binance', 'okex', 'gateio', 'mexc', 'okex_status', 'hb_status', 'bitget']
    # exchanges = ['binance', 'okex', 'gateio', 'mexc', 'okex_status', 'bitget']
    exchanges = ['binance', 'okex', 'gateio', 'okex_status', 'bitget']
    cu_time = int(time.time())
    error_msg = []
    for k, v in heart.items():
        if cu_time - int(v) > 60 * 12:
            error_msg.append(k)
    for exchange in exchanges:
        if exchange not in list(heart.keys()):
            error_msg.append(exchange)
    if error_msg:
        await heartbeat.i_live_not_well(error_msg, "外部交易所公告", 60 * 32, 66)
        await heartbeat.i_live_not_well(error_msg, "外部交易所维护状态", 60 * 32, 66)
    else:
        await heartbeat.i_live_well("外部交易所公告", 60 * 32, 66)
        await heartbeat.i_live_well("外部交易所维护状态", 60 * 32, 66)


async def recode_notice_msg(msg, server):
    NOTICE[server] = NOTICE.get(server, [])
    if msg not in NOTICE.get(server, []):
        NOTICE[server].append(msg)


async def send_notice_msg_tg():
    try:
        for ser, message in NOTICE.items():
            msg_content = ''
            for info in message:
                if info not in global_variable.SHARE_NOTICE.get(ser, []):
                    msg_content += info + '\n'
            if msg_content:
                await send_telegram_markdown_async(f'{ser} status => \n' + msg_content, 'dw_info')
            else:
                print(f'The message has been sent {global_variable.SHARE_NOTICE = }')
        print('SHARE_NOTICE', global_variable.SHARE_NOTICE)
        for ser, message in NOTICE.items():
            notice_msg_dict = global_variable.SHARE_NOTICE.get(ser, [])
            for msg in message:
                if msg not in notice_msg_dict:
                    notice_msg_dict.append(msg)
                    global_variable.SHARE_NOTICE[ser] = notice_msg_dict[-100:]
        print('SHARE_NOTICE', global_variable.SHARE_NOTICE)
    except Exception as e:
        print(f'send tg msg {e}')


async def main():
    init_share_memory()
    # await huobi_notice()
    # await gate_api_notice()
    await gate_notice()
    await okex()
    await binance()
    # await huobi_sys()
    # await mxc_notice()
    await bitget_api_notice()
    await send_heart()
    await send_notice_msg_tg()


if __name__ == '__main__':
    msg = {'huobi': [], 'okex': [], 'okex_status': [], 'binance': [], 'gate': [], "mexc": [], 'bitget': []}
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
