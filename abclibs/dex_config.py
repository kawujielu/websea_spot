
from load import load_remote

try:
    from . import config as libs_config
except:
    LIBS_HOST = "10.0.209.181"
    libs_config = load_remote.urllib_model(f"server@{LIBS_HOST}", "/home/server/abclibs/config.py")

ExchangeCode = libs_config.ExchangeCode

# 按swap 区分
s_dex_mappers = {
    ExchangeCode.uniswapv2.value: {

    },
    ExchangeCode.uniswapv3.value: {
        "BSSB": {
            "pair_name": "ETH-BSSB",
            "pair_address": "0xe21876Afd4C632b22870DF250E5Df1754C1875E8",
            "first_address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
            "second_address": "0xda31D0d1Bc934fC34F7189E38A413ca0A5e8b44F",
            "first_decimal": 18,
            "second_decimal": 18,
            "fee": 10000,
        },
        "SAVM": {
            "pair_name": "SAVM-ETH",
            "pair_address": "0xad9ef19e289dcbc9ab27b83d2df53cdeff60f02d",
            "first_address": "0x15e6e0d4ebeac120f9a97e71faa6a0235b85ed12",
            "second_address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
            "first_decimal": 18,
            "second_decimal": 18,
            "fee": 10000,
        }
    },
    ExchangeCode.sushi.value: {

    },
    ExchangeCode.pancake.value: {


    },
    ExchangeCode.mdex.value: {

    },
    ExchangeCode.matic.value: {

    },
}

# 按链区分
heco_node_pools = [
    # "https://http-mainnet.hecochain.com",
    # "https://http-mainnet-node.huobichain.com",
]
bsc_node_pools = [
    "https://bsc-dataseed1.binance.org",
    "https://bsc-dataseed2.binance.org",
    "https://bsc-dataseed3.binance.org",
    # "https://bsc-dataseed4.binance.org", # 不同步
    "https://bsc-dataseed1.defibit.io",
    "https://bsc-dataseed2.defibit.io",
    "https://bsc-dataseed3.defibit.io",
    "https://bsc-dataseed4.defibit.io",
    "https://bsc-dataseed1.ninicoin.io",
    "https://bsc-dataseed2.ninicoin.io",
    "https://bsc-dataseed3.ninicoin.io",
    # "https://bsc-dataseed4.ninicoin.io",
    'https://bsc-dataseed.binance.org',
    'https://bsc-dataseed.binance.org',
    # 'https://speedy-nodes-nyc.moralis.io/51970be46a91d547b73eaca6/bsc/mainnet',
    # 'https://speedy-nodes-nyc.moralis.io/e103c69663695f3cd1cf7304/bsc/mainnet',
    # 'https://speedy-nodes-nyc.moralis.io/bc0ae2a3e9010f1623e05bfe/bsc/mainnet',
    # 第三方备用节点
    # "https://speedy-nodes-nyc.moralis.io/ed5739ca17c091f3bdde0853/bsc/mainnet",
    # "https://speedy-nodes-nyc.moralis.io/8e3378ae8ef7d87237aa8c84/bsc/mainnet",
    # 'https://speedy-nodes-nyc.moralis.io/455a6a1d72ae6c714b6640af/bsc/mainnet',
    # 'https://speedy-nodes-nyc.moralis.io/f668289b1dbd38060c3c1a11/bsc/mainnet',
    # 'https://speedy-nodes-nyc.moralis.io/0de1f9aebda7a8d938e474c4/bsc/mainnet',
    # 'https://speedy-nodes-nyc.moralis.io/d18742afcf29f291d520d969/bsc/mainnet',
    # 'https://speedy-nodes-nyc.moralis.io/6af39bea4278817c41c2f2a3/bsc/mainnet',
    # 'https://speedy-nodes-nyc.moralis.io/a1c17eeee545080478434756/bsc/mainnet',
]
eth_node_pools = [
                  'https://mainnet.infura.io/v3/d6bb88fe3aac458e8afa7d010f8f5e6f',
                  'https://mainnet.infura.io/v3/32feef58c5334b5f869bb7db31b2894b',
                  'https://mainnet.infura.io/v3/bd16a30662a144f38e19000b25ef09fa',
                  'https://mainnet.infura.io/v3/d99b783bb3fd42ec887fef9bef81162d',
                  'https://mainnet.infura.io/v3/ea23142033354fd09ca6739cf8477c65',
                  'https://mainnet.infura.io/v3/24d4c896ebf34a1785c3c75fd0a42d3a',
                  'https://mainnet.infura.io/v3/7cbdec8bf6a84b9c8b7f926d9ffd4d25',
                  'https://mainnet.infura.io/v3/f1fcf643bf334812a60385a9b08d36fd',
                  'https://mainnet.infura.io/v3/1067b19747b74e96a0f79fac14ea4f4b',
                  'https://mainnet.infura.io/v3/953770bbcdf24661bb296d4938d4d3d5',
                  'https://mainnet.infura.io/v3/583e51ee0595406ba5161bcece5087c6',
                  'https://mainnet.infura.io/v3/c911c31d1bf948bc9bede1c9ae7f7e6a',
                  'https://mainnet.infura.io/v3/4cb8307d99c746fc9bc70f483ee7bf30',
                  'https://mainnet.infura.io/v3/f3e506c598dc42fba77a5eb8a0b78316',
                  'https://mainnet.infura.io/v3/d441f73e2105423d9ca8471b6d2ee78d',
                  'https://mainnet.infura.io/v3/ed3e5a8785f4498b852adf91dc47ff77',
                  'https://mainnet.infura.io/v3/64ceb3d2ff324851b01dda7da46814d8',
                  'https://mainnet.infura.io/v3/974544fa36d64897876879b97a036ebb',
                  'https://mainnet.infura.io/v3/85c41522b64c4a22b3a5900cac861022',
                  # 'https://mainnet.infura.io/v3/817b1484e18247d2b5029842c32bd324',
                  # 'https://mainnet.infura.io/v3/40a2c61ecbf84b0aae2012c53272559b',
                  # 'https://mainnet.infura.io/v3/1cc4ab260dff4d4c82d5895f5e2848df',
                  'https://mainnet.infura.io/v3/985698ea9d9140ccbeb142983dfb4f85',
                  'https://mainnet.infura.io/v3/0c3cabbe838847a5b575480695ae1d11',
                  'https://mainnet.infura.io/v3/48df59eec6884729a64a9a2d7d83d718',
                  'https://mainnet.infura.io/v3/fd1af535a5e540f8b22b35f721d069f2',
                  'https://mainnet.infura.io/v3/50af98ad9ea647829a8221fd3eb19f7c',
                  'https://mainnet.infura.io/v3/132ee2342be543a9ba9b4ab5caa1297e',
                  'https://mainnet.infura.io/v3/dddb959a7244477886ec6b4e2dfbbdf5',

                  'https://mainnet.infura.io/v3/ea9612d612d24f1593d374c3ff2b80f0',
                  'https://mainnet.infura.io/v3/060e2a8977f146cf9025d6de0602c737',
                  "https://mainnet.infura.io/v3/1aa9c3093929471b8ebbd9b87fb06e8c",
                  "https://mainnet.infura.io/v3/0e337423aa58456bb5a0fb82d11c94d6",
                  "https://mainnet.infura.io/v3/6f2014e11e24410190737aca06413172",
                  "https://mainnet.infura.io/v3/c5ab2a67c2a8469e81fed8ee51c33e25",
                  "https://mainnet.infura.io/v3/9abb103586bc4d9faf35623e27a5c0ff",
                  'https://mainnet.infura.io/v3/87407153d4284a069df1a1db1d43fcb3',
                  'https://mainnet.infura.io/v3/266ad4a4bceb494d82e44a8aee0035b4',
                  "https://mainnet.infura.io/v3/5ff8e26a52774786beeb03ef30a455d7",
                  'https://mainnet.infura.io/v3/afc92aca07c44842a754867017280463',
                  'https://mainnet.infura.io/v3/6e7290eda1194ca7aef5614b94e03d63',
                  'https://mainnet.infura.io/v3/713f607e5ff84f729767ec57a92d8b8e',
                  'https://mainnet.infura.io/v3/b7128fd230704e21ba530201baf25e8f',
                  'https://mainnet.infura.io/v3/ca5938a58e8b4b37a43f704ae67a8692',
                  'https://mainnet.infura.io/v3/8a88dc427c2f4378942cae6b90fba70f',
                  'https://mainnet.infura.io/v3/43aa8a18284c44228b3df1113108b2e8',
                  ]

matic_node_pools = [
                    # "https://rpc-mainnet.maticvigil.com",
                    # "https://matic-mainnet.chainstacklabs.com",
                    #"https://polygon-mainnet.blastapi.io/59bd3b8b-2cc5-49d0-970c-2e9187185601",
                    #"https://polygon-mainnet.blastapi.io/8cd21bee-5d78-42fe-8b2d-a22b687b121e"
                    ]
