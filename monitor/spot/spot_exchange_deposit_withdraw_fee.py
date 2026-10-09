import os, sys, asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import infor_load
from libs.database.getmysql import G_MysqlSession, Hedge_MysqlSession
from spot.spot_setting import getRateUsdt

# AGIX 头寸:sell 62.33543 (价值27FET,1AGIX=0.433350FET），bn当前值：294（127FET）
# OCEAN ： 头寸0.9190793928564176 (价值0.4FET ,1OCEAN=0.433226FET）。bn当前值：220 （95.3FET)
# 因为AGIX对冲没有平掉，所以把头寸转移到手续费统计，避免修改成交数以及对冲头寸等数据
REDUCE = {'FET': 27}

# fee_new - fee_old（hedge_gap_summary sync-fee 生成的 offset），写入前叠加到充提手续费汇总 amount
offset = {
    '1CAT': -0.018736783317308436, '1INCH': -0.033754677806427935, 'AAVE': -0.0004981941022383918,
    'ACE': 2.3773820982520553, 'ACT': 1.5277960289968178, 'AEVO': -0.0018185219711313039,
    'AGI': -0.005770937259512721, 'AGIX': -62.33543528894097, 'AGLD': 0.04752946686407711,
    'AI': -0.04949068401090684, 'AINN': -0.007569000029434392, 'ALCH': -0.0073742687080091684,
    'ALCX': -6.635904690499572e-05, 'ALICE': 0.4000000000000057, 'ALT': -0.35999452657604536,
    'ANKR': -0.01443136902776132, 'APE': 61.625312637157684, 'API3': -15.841116751269261,
    'APT': -34.459081379069076, 'ARB': 16.47309345421498, 'ASTER': -26.250526224,
    'ATH': -0.005566821228811136, 'AUCTION': -0.006338973624568478, 'AUDIO': 28.900000000001228,
    'AXS': -26.52812643519381, 'BABYDOGE': 820284795.0826172, 'BAKE': 0.020953836973120588,
    'BAN': 5.135147097809604, 'BANANA': -0.0008000000000043528, 'BAND': 0.0820316112220354,
    'BAT': -0.6423902305978118, 'BCCOIN': 0.09391545302787563, 'BCUT': -0.0014596053078150817,
    'BEAMX': 13492.028260228211, 'BEER': -0.7785860858857632, 'BIGTIME': 0.1030303586417034,
    'BLZ': -0.6172582268826226, 'BMT': 308.83587498765473, 'BNB': -4.6772994505,
    'BNT': -0.025662486290414677, 'BOME': 34850.446361335344, 'BOND': 3.918264006174537,
    'BR': 7.680760869057785, 'BSSB': 2.0, 'BTC': 0.08712298,
    'BTCS': 0.28157708824301153, 'C': -3440.0614493537405, 'CAKE': -13.295574542266785,
    'CELR': -134.57107004185082, 'CETUS': -0.007612248480145745, 'CFX': -620.8503050812576,
    'CGPT': -0.004615749220738596, 'CHILLGUY': 0.35626239911930213, 'CHZ': 93.47880331116579,
    'COMBO': -0.05999999999921268, 'COMP': 0.0006909777341417012, 'CORE': -26.84502704831562,
    'CRV': -0.0033206807276258132, 'CSAS': 4.226637971307355, 'CVC': -0.39606302327865706,
    'DAR': 6.799589549200618, 'DATA': 4.928561884080409, 'DEGO': 0.004969945818642074,
    'DMAIL': -0.0038736000002326243, 'DOG': 2273.3623326313314, 'DOGE': 13320.929623596487,
    'DOGS': -493058.37038838863, 'DYDX': -0.004815966012975181, 'EDU': 0.20616003283398865,
    'EGLD': 0.5297277705766092, 'ELF': -15.044278048969495, 'ELX': -339.7989731849318,
    'ENA': 77.4328902555917, 'ENJ': -0.4091347301100541, 'ENS': -0.009438052537100727,
    'ERA': -0.08164211817363765, 'ESP': -457.92328269730797, 'ETH': 20.672524094834806,
    'ETHFI': 1.1504069775797143, 'EURQ': 106.75202907131619, 
    'FARTCOIN': 1.7056779035545333, 'FET': -0.002118305664268405, 'FLOKI': -99646.2922782898,
    'FOXY': 57.24547845676541, 'FRONT': 21.541299614683776, 'FTT': -0.0069773645806625595,
    'FXS': 1.4210854715202004e-14, 'GALA': 114860.2811419, 'GIGGLE': -1.9742815023,
    'GLM': -18.0911758753291, 'GMT': 307.67404021163975, 'GOAT': -0.00863164095815705,
    'GOUT': 1798.0304406248033, 'GPT': -0.0008889655208008662, 'GROK': -0.02193519682441547,
    'GRT': -0.0, 'GTC': -4.999999999999876, 'H': -0.005830244289541042,
    'HOME': -756.0479044816633, 'HYPER': -0.046654705402488617, 'IDOL': -0.00044045860158803407,
    'ILV': 0.031000000000010963, 'IMX': 75.74154260947171, 'INJ': -4.565669265701012,
    'INSP': -0.0039022130115711207, 'IO': -0.3932834662990672, 'IOTX': -0.3982943539728723,
    'IQ': -0.573512651011697, 'JASMY': 923.5948372998037, 'JENNER': 12608.359999999999,
    'JTO': -0.00627927930036154, 'JUP': -0.08253893164476267, 'KARRAT': 0.18307839388145375,
    'KERNEL': 2.8728090096537358, 'KMNO': 26.99833701118556, 'KNC': 19.941696725910873,
    'L3': 20.11979609292996, 'LADYS': -51375899.431143284, 'LDO': -0.009464328750356188,
    'LENDS': 0.7762559922452965, 'LINK': -37.4265, 'LISTA': -0.02979880369930754,
    'LOKA': 0.06248861717585896, 'LOOM': -0.8875184759008334, 'LPT': 0.16827091239263398,
    'LQTY': 0.3499999999998238, 'LTC': 0.2055659399568166, 'MANA': -0.8698620284205845,
    'MANEKI': 182.14973029359385, 'MANTRA': -2984.3936525351555, 'MASK': -0.06105296876608435,
    'MATIC': 0.032910835803221516, 'MAV': -0.1463468370880764, 'MAVIA': -0.0020040833543930603,
    'MBOX': 25.914408427876808, 'MCG': -0.002096499998060608, 'MDT': -25.788787987481328,
    'MELANIA': 0.31619040751252214, 'MEME': 10446.203836086323, 'METIS': -0.10093229972720852,
    'MEW': -0.039513707713922486, 'MICE': 141.2827106869081, 'MKR': -0.01828456107459949,
    'MMSS': -0.0001351748996967217, 'MON': -0.00950123788013002, 'MOVE': 54.62927161481775,
    'MSN': -0.005257230792489409, 'MUBARAK': -0.006078518752929085, 'MUBI': -0.04425896978818855,
    'MULTI': -208.94905080162684, 'MYRO': 0.34006835521964973, 'NAVX': 0.5029169999888836,
    'NEAR': -47.58053434742122, 'NEIRO': -1408263.5704453, 'NEWT': 0.36062001853533365,
    'NFP': 0.09937506485657677, 'NMR': 0.07000000000000062, 'NXPC': 43.72119509894971,
    'NYAN': 4.136962748109568, 'OCEAN': 13.944779392856475, 'OGN': 5.0, 'OKB': -1.293451671711681,
    'OKT': -0.08447864005305702, 'OM': -9.283638210890588, 'OMNI': -0.008576661818501918,
    'ONDO': -58.3755698056324, 'ORCA': 3.377001037584156, 'ORDI': -4.398688413708214,
    'ORN': -0.006981936584634196, 'PENDLE': 31.333623619690226, 'PENGU': -63757.454183670416,
    'PEOPLE': -3506.86807067052, 'PEPE': 58656219.01480198, 'PERP': 1.8918614080353677,
    'PHB': -0.06742703218316848, 'PIRATE': -0.13051473972561212, 'PIXEL': 33.96689420415848,
    'PIXFI': -0.03842810053609469, 'PMG': -0.008616428415962218, 'PNUT': -8781.010714752572,
    'POL': -872.053797729, 'POND': -68.63398889793734, 'PORTAL': -0.03977926150355415,
    'POWR': -0.0, 'PRCL': 0.1295539234269043, 'PROS': 6.791714588138253,
    'PUMP': -355583.2194916572, 'PUNDIX': 3.5999999999996533, 'PYR': 0.0009133284777651518,
    'QNT': -0.2351284619775869, 'RARE': 65.97638670334075, 'RATS': 261.95658787339926,
    'RAY': 4.579277789402397, 'RDNT': -623.8921940928273, 'RENDER': 0.0645651998611747,
    'REZ': 0.063751569602573, 'RNDR': 0.023119952707073566, 'RSR': 245.1601410022795,
    'SAFE': -10.397069408328527, 'SAND': -819.0526399883254, 'SATOSHI': -0.008053199109752995,
    'SATS': 249.6185406446457, 'SAVM': -0.009541319581345853, 'SEND': 0.009988123515439096,
    'SHIB': 10092504.415008754, 'SKY': -201.38470410585273, 'SLERF': -34.47119061136574,
    'SLN': 30.628542142522864, 'SLP': -0.8060421018744819, 'SNAP': 8319.651799976826,
    'SNT': 90.55200655200679, 'SOL': -77.5659831155, 'SSV': -0.0008820865390311017,
    'STMX': -0.7533325435360894, 'SUI': -367.828575231, 'SUSHI': 0.24715074669374193,
    'SXT': -140.31641892135042, 'T': -299.00621704048535, 'TIA': 0.0010808180593813166,
    'TLM': 0.0, 'TNSR': 0.40000000000009095, 'TOKEN': -144.00178539131593,
    'TON': 8.717984774696502, 'TRAC': -5.7065898862054, 'TRB': -2.8795421864680204e-05,
    'TROLL': 276682575.0520403, 'TRUMP': 0.04118857959995221, 'TRX': 8401.807500737,  #8195.865201737,
    'TURBO': 1201.3698496940826, 'TUT': -2397.141180604118, 'ULTI': 18.739471575145302,
    'UMA': 0.4999999999999858, 'UNI': -575.4572146857923, 'UPC': -0.009334000000247755,
    'USDC': 5801.0006469020855, 'USDQ': -4.3341971078803e-06, 
    'USDT': -134457.31148437213, 'UXLINK': -0.0038990000010699077, 'VGX': -5.4569682106375694e-12,
    'VINE': -0.0046297120857161644, 'VOXEL': 16.842975206611527, 'W': -0.00741697302888511,
    'WIF': 120.87172671896381, 'WLD': -0.054019947929337064, 'WLFI': -44771.41091094018,
    'WRX': 15.410820123078302, 'XAUT': 0.0019113167002435026, 'XR': 0.11400590188122095,
    'XRP': 98.58877659058052, 'XVS': 0.28999999999999915, 'YFI': 8.139899286205284e-05,
    'YGG': 0.487096328214065, 'ZETA': -0.008144000000342544, 'ZEUS': -0.00706740893009794,
    'ZEX': 2.474622500007399, 'ZK': 333.9, 'ZKJ': 3.6590595000000676, 'ZRO': 288.69617188603917,
}
# offset = {'1CAT': 0.0, '1INCH': 0.0, 'AAVE': 0.0, 'ACE': 0.0, 'ACT': 0.0, 'AEVO': -0.003929772455535385, 'AGI': 0.0, 'AGIX': 0.0, 'AGLD': 0.0, 'AI': 0.0, 'AINN': 0.0, 'ALCH': 0.0, 'ALCX': 0.0, 'ALICE': 0.0, 'ALT': 0.0, 'ANKR': 0.0, 'APE': 5.02251299999898, 'API3': 0.0, 'APT': 0.0, 'ARB': -448.6183500000043, 'ASTER': -105.2359901900677, 'ATH': 0.0, 'AUCTION': 0.0, 'AUDIO': 0.0, 'AXS': 0.0, 'BABYDOGE': 0.0, 'BAKE': 0.0, 'BAN': 0.0, 'BANANA': 0.0, 'BAND': 0.0, 'BAT': 0.0, 'BCCOIN': 0.0, 'BCUT': 0.0, 'BEAMX': -4068.0, 'BEER': 0.0, 'BIGTIME': 0.0, 'BLZ': 0.0, 'BMT': 0.0, 'BNB': -4.142454805315942, 'BNT': 0.0, 'BOME': -5251.0, 'BOND': 0.0, 'BR': 0.0, 'BSSB': 0.0, 'BTC': -5.361295158934354e-07, 'BTCS': 0.0, 'C': 0.0, 'CAKE': 0.0, 'CELR': 0.0, 'CETUS': 0.0, 'CFX': 9.0, 'CGPT': 0.0, 'CHILLGUY': 0.0, 'CHZ': 1104.5231000000203, 'COMBO': 0.0, 'COMP': 0.0, 'CORE': 0.0, 'CRV': 0.0, 'CSAS': 0.0, 'CVC': 0.0, 'DAR': 0.0, 'DATA': 0.0, 'DEGO': 0.0, 'DMAIL': 0.0, 'DOG': 0.0, 'DOGE': -0.00037482939660549164, 'DOGS': -123502.03611738235, 'DYDX': 0.0, 'EDU': 0.0, 'EGLD': 5.551115123125783e-17, 'ELF': 0.0, 'ELX': 0.0, 'ENA': 0.0, 'ENJ': 0.0, 'ENS': 0.0, 'ERA': 0.0, 'ESP': 8.450161265550832, 'ETH': -6.070527452450847e-05, 'ETHFI': 0.0, 'EURQ': 0.0, 'EURR': 0.0, 'FARTCOIN': 0.0, 'FET': 0.0, 'FLOKI': 0.0, 'FOXY': 0.0, 'FRONT': 0.0, 'FTT': 0.0, 'FXS': 0.0, 'GALA': -50507.0, 'GIGGLE': -2.12, 'GLM': 0.0, 'GMT': 0.0, 'GOAT': 0.0, 'GOUT': 0.0, 'GPT': 0.0, 'GROK': 0.0, 'GRT': -0.0, 'GTC': 0.0, 'H': 0.0, 'HOME': 0.0, 'HYPER': 0.0, 'IDOL': 0.0, 'ILV': 0.0, 'IMX': 0.0, 'INJ': 0.0, 'INSP': 0.0, 'IO': 0.0, 'IOTX': 0.0, 'IQ': 0.0, 'JASMY': -912.0, 'JENNER': 0.0, 'JTO': 0.0, 'JUP': 0.0, 'KARRAT': 0.0, 'KERNEL': 0.0, 'KMNO': 0.0, 'KNC': 0.0, 'L3': 0.0, 'LADYS': 0.0, 'LDO': 0.0, 'LENDS': 0.0, 'LINK': -510.69000000000005, 'LISTA': 0.0, 'LOKA': 0.0, 'LOOM': 0.0, 'LPT': 0.0, 'LQTY': 0.0, 'LTC': -0.0990000000000002, 'MANA': 0.0, 'MANEKI': 0.0, 'MANTRA': 0.0, 'MASK': 0.0, 'MATIC': 0.0, 'MAV': 0.0, 'MAVIA': 0.0, 'MBOX': 0.0, 'MCG': 0.0, 'MDT': 0.0, 'MELANIA': 0.0, 'MEME': 39.0, 'METIS': 0.0, 'MEW': 0.0, 'MICE': 0.0, 'MKR': 0.0, 'MMSS': 0.0, 'MON': 0.0, 'MOVE': 0.0, 'MSN': 0.0, 'MUBARAK': 0.0, 'MUBI': 0.0, 'MULTI': 0.0, 'MYRO': 0.0, 'NAVX': 0.0, 'NEAR': -0.00414340207407804, 'NEIRO': -1379541.0, 'NEWT': 0.0, 'NFP': 0.0, 'NMR': 0.0, 'NXPC': 0.0, 'NYAN': 0.0, 'OCEAN': 0.0, 'OGN': 0.0, 'OKB': -0.5200000000000031, 'OKT': 0.0, 'OM': 0.0, 'OMNI': 0.0, 'ONDO': 0.0, 'ORCA': 0.010322580645160784, 'ORDI': 0.0, 'ORN': 0.0, 'PENDLE': 0.0, 'PENGU': 1797.9662950000056, 'PEOPLE': 0.0, 'PEPE': 191519.9500361681, 'PERP': 0.0, 'PHB': 0.0, 'PIRATE': 0.0, 'PIXEL': 0.0, 'PIXFI': 0.0, 'PMG': 0.0, 'PNUT': 0.0, 'POL': -1116.699999999997, 'POND': 0.0, 'PORTAL': 0.0, 'POWR': -0.0, 'PRCL': 0.0, 'PROS': 0.0, 'PUMP': -11519.0, 'PUNDIX': 0.0, 'PYR': 0.0, 'QNT': 0.0, 'RARE': 0.0, 'RATS': 0.0, 'RAY': 0.0, 'RDNT': 0.0, 'RENDER': 0.0, 'REZ': 0.0, 'RNDR': 0.0, 'RSR': 0.0, 'SAFE': 0.0, 'SAND': 0.0, 'SATOSHI': 0.0, 'SATS': 0.0, 'SAVM': 0.0, 'SEND': 0.0, 'SHIB': -1511147.0, 'SKY': 0.0, 'SLERF': 0.0, 'SLN': 0.0, 'SLP': 0.0, 'SNAP': 0.0, 'SNT': 0.0, 'SOL': -0.17025342956003442, 'SSV': 0.0, 'STMX': 0.0, 'SUI': -131.36114664360775, 'SUSHI': 0.0, 'SXT': -636.49, 'T': 0.0, 'TIA': 0.0, 'TLM': 0.0, 'TNSR': 0.0, 'TOKEN': 0.0, 'TON': -0.004912169631296592, 'TRAC': 0.0, 'TRB': 0.0, 'TROLL': 0.0, 'TRUMP': 0.0, 'TRX': -2275.7328371526673, 'TURBO': 0.0, 'TUT': 0.0, 'ULTI': 0.0, 'UMA': 0.0, 'UNI': 0.011840500000062093, 'UPC': 0.0, 'USDC': 0.007525527798861731, 'USDQ': 0.0, 'USDR': -1083.9399999999996, 'USDT': -1023.3844442046247, 'UXLINK': 0.0, 'VGX': 0.0, 'VINE': 0.0, 'VOXEL': 0.0, 'W': 0.0, 'WIF': 0.0, 'WLD': 2.9204956444609707, 'WLFI': -0.9099999999962165, 'WRX': 0.0, 'XAUT': -0.0009499999999999786, 'XR': 0.0, 'XRP': 0.5818817146609945, 'XVS': 0.0, 'YFI': 0.0, 'YGG': 0.0, 'ZETA': 0.0, 'ZEUS': 0.0, 'ZEX': 0.0, 'ZK': 0.0, 'ZKJ': 0.0, 'ZRO': -0.006315400295477502}


async def get_fee_asset_gap():
    ts = []
    asset_gap = {}
    sql = """SELECT coin,amount,generation_time from fee_asset_gap """
    res, title = await Hedge_MysqlSession.fetch_all(sql=sql)

    for i in res:
        coin, amount, time = i
        asset_gap[coin] = asset_gap.get(coin, 0) + amount
        ts.append(time)

    start_time = max(ts) if ts else None
    return start_time, asset_gap


async def get_deposit_withdraw_fee():
    # start_ts, asset_gap = await get_fee_asset_gap()
    # now_time = (datetime.now() + timedelta(minutes=-10)).strftime('%Y-%m-%d %H:%M:%S')
    # # now_time = (datetime.now() + timedelta(days=-1)).strftime('%Y-%m-%d %H:%M:%S')
    # ts = []
    # if start_ts:
    #     time_sql = f"""'{now_time}'>`time` and `time`>'{start_ts}' """
    #     ts.append(str(start_ts))
    # else:
    #     time_sql = f"""'{now_time}'>`time` """
    rate = await getRateUsdt()

    # sql = f"""SELECT currency ,sum(fee) fee,time,exchange from exchange_deposit_withdraw WHERE `status1` in ("已确认","已通过","提现完成","成功","完成","入账成功","提现成功") GROUP BY currency,time,exchange ORDER BY time ASC"""
    sql = f"""SELECT currency ,sum(fee) fee,time,exchange from exchange_deposit_withdraw WHERE (`status1` in ("已确认","已通过","提现完成","成功","完成","入账成功","提现成功")) or (`status1` in ("打包中") and LENGTH(`hash`)>0) GROUP BY currency,time,exchange ORDER BY time ASC"""
    results, title = await G_MysqlSession.fetch_all(sql=sql)
    spec_symbol_rate_mapping_currency_ex = {}
    for ex, i in infor_load.spec_symbol_rate_mapping_currency.items():
        spec_symbol_rate_mapping_currency_ex[ex] = {}
        for curr, v in i.items():
            spec_symbol_rate_mapping_currency_ex[ex][v['name']] = {'name': curr, 'pr': 1 / v['pr']}
    asset_gap = {}
    ts = []
    if results:
        for i in results:
            curr, amount, time, ex = i
            d = spec_symbol_rate_mapping_currency_ex.get(ex, {}).get(curr, {})
            coin = d.get('name', curr)
            pr = d.get('pr', 1)
            asset_gap[coin] = asset_gap.get(coin, 0) + amount * pr * (-1)
            ts.append(str(time))
        generation_time = max(ts)
        for coin, v in REDUCE.items():
            asset_gap[coin] = asset_gap.get(coin, 0) + v

        for coin, fee_update in offset.items():
            asset_gap[coin] = asset_gap.get(coin, 0) + fee_update

        title = ",".join(['coin', 'amount', 'generation_time', 'rate', 'coin_u'])
        values = ",".join([str(tuple([coin, amount, generation_time, rate.get(coin, 0), amount * rate.get(coin, 0)])) for coin, amount in asset_gap.items()])

        sql = f"insert ignore into fee_asset_gap ({title}) " \
              f"values {values}" \
              f"on duplicate key update " \
              f"coin = values (coin)," \
              f"amount = values (amount)," \
              f"rate = values (rate)," \
              f"coin_u = values (coin_u)," \
              f"generation_time = values (generation_time)"
        await Hedge_MysqlSession.insert_sql(sql=sql)


if __name__ == "__main__":
    asyncio.run(get_deposit_withdraw_fee())
