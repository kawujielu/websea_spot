import datetime, time, asyncio

from libs.database.getmysql import G_MysqlSession

spot_db = 'fund'
#currencies = ['AINN-USDT', 'SATOSHI-USDT', 'DOG-USDT', 'REZ-USDT', 'KARRAT-USDT', 'MYRO-USDT', 'SLERF-USDT', 'FOXY-USDT', 'ZEUS-USDT', 'TNSR-USDT', 'PRCL-USDT', 'MANEKI-USDT', 'MSN-USDT', 'KMNO-USDT', 'BCCOIN-USDT', 'IO-USDT', 'ULTI-USDT', 'MON-USDT', 'BEER-USDT', 'NYAN-USDT']
#currencies = ['FXS-USDT', 'ALT-USDT', 'MAV-USDT', 'XVS-USDT', 'UMA-USDT', 'API3-USDT', 'AUDIO-USDT', 'DMAIL-USDT', 'MAVIA-USDT', 'PIXEL-USDT', 'OKT-USDT', 'BCUT-USDT', 'SLN-USDT', 'PORTAL-USDT', 'GPT-USDT', 'CETUS-USDT', 'LADYS-USDT', 'ZKJ-USDT', 'ZETA-USDT', 'NAVX-USDT', 'IQ-USDT', 'OMNI-USDT']
#currencies = ['NFP-USDT', 'AI-USDT', 'PROS-USDT', 'EDU-USDT', 'SSV-USDT', 'POWR-USDT', 'DATA-USDT', 'OGN-USDT', 'POND-USDT', 'PERP-USDT', 'GTC-USDT', 'COMBO-USDT', 'ALICE-USDT', 'ILV-USDT', 'DAR-USDT', 'SLP-USDT', 'VGX-USDT', 'METIS-USDT', 'MDT-USDT', 'PHB-USDT', 'NMR-USDT']
#currencies = ['TOKEN', 'ORN', 'SATS', 'RATS', 'CSAS', 'RARE', 'AUCTION', 'GROK', 'CGPT', 'AGI', 'PMG', 'SNT', 'LOKA', 'RDNT', 'PUNDIX', 'STMX', 'TRAC', 'MUBI', 'BTCS', 'BAKE', 'DEGO', 'ALCX', 'PYR', 'AGLD', 'TLM', 'ACE', 'VOXEL', 'MBOX']
currencies = ['ENJ', 'BAND', 'KNC', 'YFI', 'BLZ', 'BIGTIME', 'LQTY', 'LOOM', 'WRX', 'CELR', 'CVC', 'T', 'BNT']
SPOT_MYSQL_CONFIG = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "db": spot_db,
}

async def get_start_amount():
    # 现货转现货 、现货转合约、合约转合约、合约转现货
    t1_dict = {}
    for r in currencies:
        sql = f"select * from hedge where currency = '{r.split('-')[0]}' ORDER BY id desc LIMIT 1;"
        res = await G_MysqlSession.fetch_one(sql)
       
        print(res[2], res[23], res[1])

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(get_start_amount())

