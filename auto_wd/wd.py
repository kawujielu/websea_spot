"""
    现货自动提币 (wd2)
    基于 wd.py：提币前检查 196 余额，不足时从 11/12/13 经 17 补资到 196

    后续增加自动提币交易对,需修改 _WITHDRAW_ADDRS 及 _GATE/_KRAKEN 币种集合
"""

import time
import hashlib
import math
import random
import string
from enum import Enum
import traceback
import asyncio
import requests
from scaffold.mysql import G_MysqlSession
from loguru import logger
from scaffold.redis import rs_wd_instance
from auto_wd.abc_api import AbcApi
from libs.senddd import send_telegram_msg_async
from auto_wd.bn_api import bn_instance
from auto_wd.gate_api import gate_instance
from auto_wd.kraken_api import kraken_instance
from libs import heartbeat


auto_wd_log = "[自动化充提-wd2] "

SUPPORT_EXCHANGES = ("bn", "gate", "kraken")
_GATE_CURRENCIES = {
    "OKB", "SAFE", "XAUT", "GIGGLE", "NVDAON", "AAPLON", "GOOGLON", "MSFTON",
    "TSLAON", "CRCLON", "AMDON", "KOON", "QQQON", "NFLXON", "CSCOON", "LLYON", 
    "SBUXON", "PEPON", "SLVON", "SPYON", "IAUON", "HOODON", "AMZNON", "METAON",
    "SKHYON"
}
_KRAKEN_CURRENCIES = {"EURQ"}
_GATE_ADDR = "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"
_KRAKEN_ADDR = "0x415C05E021aD257Bb8a8c86FB473571333b46461"


def _build_withdraw_deposit_config():
    """按币种路由生成各外盘提币地址配置。"""
    cfg = {ex: {} for ex in SUPPORT_EXCHANGES}
    for currency, addr_cfg in _WITHDRAW_ADDRS.items():
        if currency in _KRAKEN_CURRENCIES:
            target = "kraken"
        elif currency in _GATE_CURRENCIES:
            target = "gate"
        else:
            target = "bn"
        cfg[target][currency] = addr_cfg
    cfg["gate"]["USDT"] = ("ERC20", _GATE_ADDR)
    cfg["kraken"]["USDT"] = ("ERC20", _KRAKEN_ADDR)
    return cfg


_WITHDRAW_ADDRS = {
        "USDT": ("TRC20", "TLxBj9Edy11Wps3Yf7oufEeVcb8R4hyjPt"),
        "BTC": ("BTC", "12yDuBueTUZcDw9P7VNdnYbd4Q9GQLuoiN"),
        "ETH": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "SOL": ("Solana", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
        "BNB": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "TRX": ("TRC20", "TLxBj9Edy11Wps3Yf7oufEeVcb8R4hyjPt"),
        "XRP": ("XRP", "rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV", "493586538"),
        "MASK": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "GALA": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "WLFI": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "ETHFI": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "PEPE": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "WLD": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "LTC": ("LTC", "LNu4gJwxujrvxhDuWcT7YDhvCWCyWgovVp"),
        "CFX": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "FLOKI": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "ASTER": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "NXPC": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "USDC": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "DOGE": ("DOGE", "DRu9tqGhqvZRqzGg7nzTpsvKuzBSiWWHUR"),

        "AXS": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "ENS": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "LINK": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "MANA": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "SAND": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "SHIB": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "COMP": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "SUSHI": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        # "1INCH": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "AAVE": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "CRV": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "ANKR": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "CHZ": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "QNT": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "UNI": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        # "TRB": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "GLM": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "MEME": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "FTT": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "CAKE": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "WLD": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "GRT": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "LDO": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "ONDO": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "IMX": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "LPT": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "JASMY": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "AEVO": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "ENA": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "ZRO": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "POL": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "MOVE": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "HYPER": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "KERNEL": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "SXT": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "NEWT": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "SKY": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),

        "NXPC": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "EGLD": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "NEAR": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "INJ": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "BMT": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "ERA": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "C": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),

        "ORDI": ("BRC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "BEAMX": ("BRC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),

        "PENGU": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
        "TRUMP": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
        "ORCA": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
        "PNUT": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
        "ACT": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
        "RENDER": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
        "JUP": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
        # "WIF": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
        "W": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
        "JTO": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
        
        "TIA": ("Celestia", "celestia1fd3mclxp4e2fh0wpau3eg55x2fsm7yjxzg29j2","106324248"),
        "SUI": ("SUI", "0x2555c3903f45c653a193d241c48aa67de38032e7835ff4648c262ee1fe99f174"),
        "ARB": ("Arbitrum", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
        "DOGS": ("TON", "UQB0dW0k-KBfbI1qMhav9iqKuBsRhvZQPGHkZZvVsiUnQowh"),
        "GRAM": ("TON", "UQB0dW0k-KBfbI1qMhav9iqKuBsRhvZQPGHkZZvVsiUnQowh"),
        # "TON": ("TON", "UQB0dW0k-KBfbI1qMhav9iqKuBsRhvZQPGHkZZvVsiUnQowh"),

        # GATE
        "OKB": ("Xlayer", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "XAUT": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "GIGGLE": ("BEP20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "NVDAON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "AAPLON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "GOOGLON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "MSFTON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "TSLAON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "CRCLON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "AMDON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "KOON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "QQQON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "NFLXON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "CSCOON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "LLYON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "SBUXON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "PEPON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "SLVON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "SPYON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "IAUON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "HOODON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "AMZNON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "METAON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),
        "SKHYON": ("ERC20", "0x2Ec27dB0b8A35c773Cbb1c02FbEE48A43517956a"),

        # kraken
        "EURQ": ("ERC20", "0x415C05E021aD257Bb8a8c86FB473571333b46461"),
}

WITHDRAW_DEPOSIT_CONFIG = _build_withdraw_deposit_config()


server_status1 = True
server_status2 = True

apikey = {'token': "78fc47c5590f77ca42d1e2c3bb432813", 'secret_key': "5e5yg7ga285hctuqrtpb"} # 196
# apikey = {'token': "7665d59224d56e497a142e9000i56478975", 'secret_key': "sm1w1u30nlduxv7fzkem"}  # 我自己测试账号
abc_instance = AbcApi(**apikey)
user_id = 196

SPOT_HOST = "https://oapi.websea.com"
RISK_BASE = "https://riskapi.websea.work/api/open/get"
RISK_TOKEN = "c1cf4185b2bed317aeb6e6674491fbef"
HUB_UID = 17
# 做市账户 11/12/13 → 17 → 196（同 select_spot_wallet.py）
_ACC = {
    11: {"token": "18c4725b9d218777c3863f812e21d9a2522", "sk": "2ijh2r7nf8nvjce4rnq7"},
    12: {"token": "291d6fa8dc35f58690c38f7c3afcf2h2808", "sk": "7rk8zhyxbbxk5ro8r4to"},
    13: {"token": "e5451dae5de519289e45aaab4be461f2856", "sk": "lmtn1yxnlwq6ecjqs5yv"},
    17: {"token": "2ec49187f681419d1959af499d7bb0p3584", "sk": "wcj34ct96l2vh3s1hog7"},
    196: {"token": apikey["token"], "sk": apikey["secret_key"]},
}
_MAKER_UIDS = (11, 12, 13)


def _fetch_spot_wallet(token, sk):
    """查询现货钱包列表（GET /openApi/wallet/list）。"""
    params = {"show_all": 1}
    nonce = "%d_%s" % (int(time.time() * 1000), "".join(random.sample(string.ascii_letters + string.digits, 5)))
    parts = [token, sk, nonce] + [f"{k}={v}" for k, v in params.items()]
    headers = {
        "Token": token,
        "Nonce": nonce,
        "Signature": hashlib.sha1("".join(sorted(parts)).encode("utf-8")).hexdigest(),
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        ),
    }
    resp = requests.get(
        f"{SPOT_HOST.rstrip('/')}/openApi/wallet/list",
        params=params, headers=headers, timeout=30, verify=False,
    )
    if resp.status_code != 200:
        return {"errno": -1, "errmsg": f"HTTP {resp.status_code}", "result": resp.text}
    return resp.json()


def _coin_available(uid, coin):
    """返回指定账户某币种的可用余额。"""
    meta = _ACC[uid]
    payload = _fetch_spot_wallet(meta["token"], meta["sk"])
    if payload.get("errno") != 0:
        logger.warning(f"{auto_wd_log}查询钱包失败 uid={uid} {payload}")
        return 0.0
    for item in payload.get("result") or []:
        if str(item.get("currency", "")).upper() == coin.upper():
            return float(item.get("available") or 0)
    return 0.0


# 划转精度查不到时的默认小数位；粉尘阈值按 10^(-decimals)
_TRANSFER_DECIMALS_DEFAULT = 4


def _format_transfer_amount(amount, decimals=_TRANSFER_DECIMALS_DEFAULT):
    """划转金额按 decimals 向下截取；低于精度返回 None，避免提交 amount=0。"""
    decimals = max(0, int(decimals))
    scale = 10 ** decimals
    floored = math.floor(float(amount) * scale + 1e-12) / scale
    if floored <= 0:
        return None
    if decimals == 0:
        return str(int(floored))
    s = f"{floored:.{decimals}f}".rstrip("0").rstrip(".")
    return s or None


def _risk_transfer(from_uid, to_uid, currency, amount, decimals=_TRANSFER_DECIMALS_DEFAULT, note="auto_wd2 topup"):
    """内部账户划转（quantuser/transfer）。"""
    amt_s = _format_transfer_amount(amount, decimals)
    if amt_s is None:
        return {
            "errno": 40003,
            "errmsg": f"amount too small after {decimals}dp floor: {amount}",
            "result": None,
        }
    params = {
        "url": "quantuser/transfer",
        "token": RISK_TOKEN,
        "from": from_uid,
        "to": to_uid,
        "currency": currency,
        "amount": amt_s,
        "note": note,
    }
    nonce = f"{int(time.time() * 1000)}_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
    tmp = [RISK_TOKEN, "", nonce] + [f"{k}={v}" for k, v in params.items()]
    headers = {
        "Token": RISK_TOKEN,
        "Nonce": nonce,
        "Signature": hashlib.sha1("".join(sorted(tmp)).encode()).hexdigest(),
    }
    r = requests.get(RISK_BASE, params=params, headers=headers, timeout=30)
    return r.json()


async def ensure_196_balance(currency, quantity):
    """确保196余额足够提币，不足则从11/12/13经17补资。"""
    bal = _coin_available(196, currency)
    logger.info(f"{auto_wd_log}196 {currency} available={bal} need={quantity}")
    if bal >= quantity:
        return True

    decimals = await abc_instance.amount_decimals(currency)
    transfer_min = 10 ** (-decimals) if decimals > 0 else 1.0

    need = quantity - bal
    # 浮点误差 / 粉尘缺口：低于币对精度无需划转
    if need < transfer_min or _format_transfer_amount(need, decimals) is None:
        logger.info(f"{auto_wd_log}缺口低于划转精度，跳过补资 need={need} decimals={decimals}")
        return True

    maker_bals = [(uid, _coin_available(uid, currency)) for uid in _MAKER_UIDS]
    # 粉尘余额无法提交划转，不计入可用
    usable = [(uid, b) for uid, b in maker_bals if b >= transfer_min]
    total = sum(b for _, b in usable)
    need_buf = need * 1.001  # 千1 缓冲，抵消划转磨损
    logger.info(
        f"{auto_wd_log}maker余额 {maker_bals} usable_total={total} "
        f"need={need} need_buf={need_buf} decimals={decimals}"
    )
    if total < need:
        msg = f"{auto_wd_log}资产不足 无法提币 {currency=} need={need} 196={bal} 11/12/13合计={total}"
        logger.error(msg)
        if _throttled_alert(f"insufficient:{currency}"):
            await send_telegram_msg_async(msg, ser="spot_hedge")
        return False
    if total >= need_buf:
        need = need_buf

    # 优先单户够用；否则按 11→12→13 拼凑
    plan = []
    remain = need
    single = next(((uid, need) for uid, b in usable if b >= need), None)
    if single:
        plan = [single]
    else:
        for uid, b in usable:
            if remain < transfer_min:
                break
            take = min(b, remain)
            if take < transfer_min:
                continue
            plan.append((uid, take))
            remain -= take

    moved = 0.0
    for uid, amt in plan:
        amt_s = _format_transfer_amount(amt, decimals)
        if amt_s is None:
            continue
        res = _risk_transfer(uid, HUB_UID, currency, amt, decimals=decimals)
        if res.get("errno") != 0:
            msg = f"{auto_wd_log}划转失败 {uid}->{HUB_UID} {currency} {amt_s} {res}"
            logger.error(msg)
            await send_telegram_msg_async(msg, ser="spot_hedge")
            return False
        moved += float(amt_s)
        logger.info(f"{auto_wd_log}划转成功 {uid}->{HUB_UID} {currency} {amt_s}")

    if moved < transfer_min or _format_transfer_amount(moved, decimals) is None:
        logger.info(f"{auto_wd_log}累计划转低于精度，跳过 17->196 moved={moved}")
        return True

    res = _risk_transfer(HUB_UID, 196, currency, moved, decimals=decimals)
    if res.get("errno") != 0:
        msg = f"{auto_wd_log}划转失败 {HUB_UID}->196 {currency} {moved} {res}，资金可能滞留17"
        logger.error(msg)
        await send_telegram_msg_async(msg, ser="spot_hedge")
        return False
    logger.info(f"{auto_wd_log}划转成功 {HUB_UID}->196 {currency} {moved}")

    await asyncio.sleep(1)
    bal2 = _coin_available(196, currency)
    logger.info(f"{auto_wd_log}补资后196 {currency} available={bal2} need={quantity}")
    if bal2 < quantity:
        msg = f"{auto_wd_log}补资后196仍不足 {currency=} bal={bal2} need={quantity}"
        logger.error(msg)
        await send_telegram_msg_async(msg, ser="spot_hedge")
        return False
    return True


def _wd_signal_key(ex, currency):
    """生成 Redis 提币信号字段名。"""
    return f"{ex}:{currency}"


def _split_wd_signal_key(field):
    """解析提币信号字段为交易所与币种。"""
    if ":" in field:
        ex, currency = field.split(":", 1)
        if ex in SUPPORT_EXCHANGES:
            return ex, currency
    # 兼容旧版/monitor：key 仅为 currency，默认 bn
    return "bn", field


async def send_wd_signal(currency, quantity, price, ex):
    """写入/更新 Redis 自动提币信号。"""
    logger.info(f"send_wd_signal {currency=} {quantity=} {price=} {ex=}")
    if ex not in SUPPORT_EXCHANGES or currency not in WITHDRAW_DEPOSIT_CONFIG.get(ex, {}):
        return
    if currency == "USDT":
        quantity = max(20000, quantity)

    try:
        signal_key = _wd_signal_key(ex, currency)
        ready_new = await rs_wd_instance.async_connection.hget("auto_wd_signal", signal_key)
        ready_legacy = await rs_wd_instance.async_connection.hget("auto_wd_signal", currency)
        ready_quantity = max(float(ready_new or 0), float(ready_legacy or 0))
        logger.info(f"{auto_wd_log}receive wd signal {ex=} {currency=} {ready_quantity=} {quantity=} {price=}")
        if ready_quantity < quantity:
            res = await rs_wd_instance.async_connection.hset("auto_wd_signal", signal_key, f"{quantity:.4f}")
            if currency != signal_key:
                await rs_wd_instance.async_connection.hdel("auto_wd_signal", currency)
            logger.info(f"{auto_wd_log}send_wd_signal update {res=}")
    except Exception as e:
        msg = f"send_wd_signal {traceback.format_exc()}"
        logger.error(msg)
        await send_telegram_msg_async(msg, ser="spot_hedge")


class StatusCode(Enum):
    request = 1
    success = 2


background_tasks = set()
background_tasks_name = set()
_pending_deposit_alert_ts = {}  # tx -> last alert ts
_sync_alert_ts = {}  # key -> last alert ts
_PENDING_DEPOSIT_ALERT_INTERVAL = 5 * 60


def _throttled_alert(key):
    """同一 key 至少间隔 _PENDING_DEPOSIT_ALERT_INTERVAL 才报警。"""
    now = time.time()
    if now - _sync_alert_ts.get(key, 0) < _PENDING_DEPOSIT_ALERT_INTERVAL:
        return False
    _sync_alert_ts[key] = now
    return True


def discard(task):
    """后台任务结束后从跟踪集合中移除。"""
    background_tasks_name.discard(task.get_name())
    background_tasks.discard(task)


def register_task(task):
    """注册后台任务并在结束时自动清理。"""
    background_tasks_name.add(task.get_name())
    background_tasks.add(task)
    task.add_done_callback(discard)


async def risk_control():
    """近1小时提币超过20次则报警并拦截。"""
    since = time.time() - 60 * 60
    query_sql = f"SELECT currency, quantity from auto_wd WHERE send_ts > {since}"
    res = await G_MysqlSession.fetch_all(query_sql)
    send_times = len(res)
    msg = f"最近1小时连续自动提币次数{send_times=}"
    logger.info(msg)
    if len(res) > 20:
        msg = f"{auto_wd_log}{msg} 超过20次，请通知检查！"
        await send_telegram_msg_async(msg, ser="spot_hedge")
        return True
    return False


async def withdraw_deposit():
    """
    status 0 发送请求 -1 撤销 1
    从196账户提币到执行的对冲交易所地址
    消费提币信号：补资后从196提币到外盘地址。
    """
    while True:
        try:
            # 1 获取wd请求信号
            res = await rs_wd_instance.async_connection.hgetall("auto_wd_signal")
            logger.info(f"auto_wd_signal查询结果:{res}")

            await heartbeat.i_live_well("自动化充提-main-process", 20, 4)

            if not res:
                continue

            if await risk_control():
                continue

            for field, quantity in res.items():
                ex, currency = _split_wd_signal_key(field)
                if not ex or currency not in WITHDRAW_DEPOSIT_CONFIG.get(ex, {}):
                    continue
                quantity = float(quantity)
                if quantity == 0:
                    continue

                logger.info(f"{auto_wd_log}receive withdraw deposit signal {ex=} {currency=} {quantity=}")
                if not server_status1:
                    logger.info(f"withdraw_deposit server is stop ...............")
                    continue

                await rs_wd_instance.async_connection.hset("auto_wd_signal", field, "0")
                signal_key = _wd_signal_key(ex, currency)
                if field != signal_key:
                    await rs_wd_instance.async_connection.hset("auto_wd_signal", signal_key, "0")
                query_sql = (
                    f"SELECT currency, quantity from auto_wd "
                    f"WHERE currency='{currency}' and wd_to='{ex}' and status={StatusCode.request.value}"
                )
                query_res = await G_MysqlSession.fetch_all(query_sql)
                process_quantity = sum([float(i[1]) for i in query_res]) if query_res else 0
                if process_quantity > 0:
                    logger.info(f"{auto_wd_log}{query_res} {process_quantity=} has withdraw in process , wait to completed")
                    continue

                query_sql = (
                    f"SELECT id, currency, quantity, finish_ts from auto_wd "
                    f"WHERE currency='{currency}' and wd_to='{ex}' ORDER BY id DESC LIMIT 1"
                )
                latest_res = await G_MysqlSession.fetch_all(query_sql)
                if latest_res:
                    latest_res = latest_res[0]
                    finish_ts = latest_res[3]
                    # 防止bn刚入账，对冲没有检测到，又发起请求
                    if time.time() - finish_ts < 5 * 60:
                        logger.error(f"{auto_wd_log}前一个充提信息是5分钟内刚完成更新，忽略掉本次充提信号")
                        continue

                try:
                    # if not await ensure_196_balance(currency, quantity):
                    #     continue

                    # wd_config = WITHDRAW_DEPOSIT_CONFIG[ex][currency]
                    # chain = wd_config[0]
                    # address = wd_config[1]
                    # memo = wd_config[2] if len(wd_config) > 2 else None

                    # decimals = await abc_instance.amount_decimals(currency)
                    # amt_s = _format_transfer_amount(quantity, decimals)
                    # if amt_s is None:
                    #     logger.error(f"{auto_wd_log}提币数量过小 {currency=} {quantity=} {decimals=}")
                    #     continue
                    # quantity = float(amt_s)

                    # send_res = await abc_instance.withdraw(currency, quantity, address, chain, memo=memo)
                    # wd_id = ""
                    # if send_res:
                    #     code = send_res["errno"]
                    #     if code == 0:
                    #         wd_id = send_res['result']['withdrawId']
                    #     else:
                    #         msg = f"{auto_wd_log} {ex=} {currency=} {quantity=} {send_res}"
                    #         logger.error(msg)
                    #         await send_telegram_msg_async(msg, ser="spot_hedge")

                    # wd_from = "abc"
                    # wd_to = ex
                    # tx = ''
                    # status = StatusCode.request.value
                    # send_ts = int(time.time())
                    # insert_sql = f"INSERT INTO auto_wd (wd_id,currency,wd_from,wd_to,chain,quantity,address,tx, status, send_ts) VALUES ('{wd_id}', '{currency}', '{wd_from}', '{wd_to}', '{chain}', '{quantity}', '{address}', '{tx}', {status}, {send_ts})"
                    # await G_MysqlSession.insert(insert_sql)

                    # msg = f"{auto_wd_log}发送提币 {wd_to=} {currency=} {quantity=}  {send_res=}"
                    # logger.info(msg)
                    # await send_telegram_msg_async(msg, ser="spot_hedge")
                    pass
                except:
                    logger.error(f"{auto_wd_log}{currency=} {quantity=} send withdraw has error {traceback.format_exc()}")

        except Exception as e:
            logger.error(f"{auto_wd_log}withdraw_deposit {traceback.format_exc()}")
        finally:
            await asyncio.sleep(5)


async def _confirm_deposits(tx_map, hedge_his, tx_key, ok_fn, label):
    """用外盘充值记录确认提币到账并更新状态。"""
    if not tx_map or not hedge_his:
        return
    logger.info(f"获取到{label}充值记录 count={len(hedge_his)}")
    for his in hedge_his:
        tx = his.get(tx_key)
        status = his.get("status")
        # TON 链两端 tx hash 不一致，改用 币种+目标地址+时间窗口 对账，到账状态放宽到 1/6
        ton_key = next(
            (
                k
                for k, m in tx_map.items()
                if m.get("is_ton")
                and his.get("coin") == m.get("currency")
                and his.get("address") == m.get("address")
                and his.get("insertTime", 0) >= m.get("send_ts", 0) * 1000
            ),
            None,
        )
        if ton_key is not None:
            if status in (1, 6):
                update_id = tx_map[ton_key]["id"]
                finish_ts = int(time.time())
                logger.info(f"准备更新充提记录状态 {label=} {update_id=}")
                update_sql = (
                    f"UPDATE auto_wd SET tx='{tx}', status={StatusCode.success.value}, "
                    f"finish_ts={finish_ts} where id={update_id}"
                )
                await G_MysqlSession.insert(update_sql)
            continue

        if tx and ok_fn(status) and tx in tx_map:
            update_id = tx_map[tx]["id"]
            finish_ts = int(time.time())
            logger.info(f"准备更新充提记录状态 {label=} {update_id=}")
            update_sql = (
                f"UPDATE auto_wd SET tx='{tx}', status={StatusCode.success.value}, "
                f"finish_ts={finish_ts} where id={update_id}"
            )
            await G_MysqlSession.insert(update_sql)
            _pending_deposit_alert_ts.pop(tx, None)
        elif tx in tx_map:
            now = time.time()
            if now - _pending_deposit_alert_ts.get(tx, 0) < _PENDING_DEPOSIT_ALERT_INTERVAL:
                continue
            _pending_deposit_alert_ts[tx] = now
            msg = f"{auto_wd_log}检测到{label}充值未完成 {his=}"
            await send_telegram_msg_async(msg, ser="spot_hedge")


DEPOSIT_SYNC = (
    ("bn", bn_instance, "txId", lambda s: s in (1, 6)),
    ("gate", gate_instance, "txid", lambda s: s == "DONE"),
    ("kraken", kraken_instance, "txid", lambda s: s in ("Success", "Settled")),
)


async def sync_withdraw_deposit():
    """轮询未完成提币，同步外盘到账状态。"""
    while True:
        try:
            await heartbeat.i_live_well("自动化充提-sync-status", 20, 4)

            if not server_status2:
                logger.info(f"sync_withdraw_deposit server is stop ...............")
                continue

            query_sql = f"SELECT id, currency, wd_id, quantity, send_ts, wd_to from auto_wd WHERE status={StatusCode.request.value}"
            res = await G_MysqlSession.fetch_all(query_sql)
            logger.info(f"未确认的充提记录 ： {res=}")
            min_ts = time.time()
            temp_currency_mapper = {}
            for i in res:
                id = i[0]
                currency = i[1]
                wd_id = i[2]
                q = i[3]
                send_ts = i[4]
                wd_to = i[5] or "bn"
                min_ts = min(send_ts, min_ts)

                if not wd_id:
                    if _throttled_alert(f"no_wd_id:{id}"):
                        msg = f"{id=} 未获取到wd id ， 可能是发送提币请求没有正确返回， 检查确认！"
                        await send_telegram_msg_async(msg, ser="spot_hedge")
                    continue
                wd_info = await abc_instance.withdraw_his(user_id, wd_id=wd_id)
                if wd_info:
                    tx = wd_info[0]["tx_hash"]
                    if not tx and time.time() - send_ts > 10 * 60:
                        if _throttled_alert(f"no_tx:{wd_id}"):
                            msg = f"{wd_id=} status={wd_info[0].get('status', '未知')} 0审核中,1已通过,2已撤销,3排队中,5打包中,7确认中,9已确认,11失败,12已驳回 10分钟没有生成tx hash， 检查确认！"
                            await send_telegram_msg_async(msg, ser="spot_hedge")
                        continue

                else:
                    msg = f"{wd_id=}未获取到wd 信息， 检查确认！"
                    await send_telegram_msg_async(msg, ser="spot_hedge")
                    continue

                chain_name = wd_info[0].get("chain_name")
                temp_currency_mapper[tx] = {
                    "id": id,
                    "wd_to": wd_to,
                    "currency": currency,
                    "address": wd_info[0].get("address"),
                    "send_ts": send_ts,
                    "is_ton": chain_name == "Toncoin",
                }
                if time.time() - send_ts > 20 * 60 and _throttled_alert(f"no_confirm:{id}"):
                    msg = f"{auto_wd_log} {id=} {q=} {currency} {wd_to=} 长时间没有确认到账，资产检查 @TB147258"
                    await send_telegram_msg_async(msg, ser="spot_hedge")

            if temp_currency_mapper:
                start_ts_ms = int(min_ts * 1000)
                for ex, api, tx_key, ok_fn in DEPOSIT_SYNC:
                    tx_map = {tx: m for tx, m in temp_currency_mapper.items() if m["wd_to"] == ex}
                    if not tx_map:
                        continue
                    hedge_his = await api.deposit_hisrec(start_ts_ms)
                    await _confirm_deposits(tx_map, hedge_his, tx_key, ok_fn, ex)

        except Exception as e:
            logger.error(f"{auto_wd_log}sync_withdraw_deposit {traceback.format_exc()}")
        finally:
            await asyncio.sleep(20)


async def main():
    """拉起提币与到账同步两个后台任务。"""
    while True:
        try:
            if "withdraw_deposit" not in background_tasks_name:
                task = asyncio.create_task(withdraw_deposit(), name="withdraw_deposit")
                register_task(task)
            if "sync_withdraw_deposit" not in background_tasks_name:
                task = asyncio.create_task(sync_withdraw_deposit(), name="sync_withdraw_deposit")
                register_task(task)
        except Exception as e:
            msg = f"main process {traceback.format_exc()}"
            await send_telegram_msg_async(msg, ser="spot_hedge")
        finally:
            await asyncio.sleep(2)


if __name__ == "__main__":
    async def _boot():
    #     await send_wd_signal("USDT", 100, 1, "bn")
        await main()

    asyncio.run(_boot())

