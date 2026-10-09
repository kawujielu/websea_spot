import libs


if libs.libs_config.DEBUG:
    EXTERNAL_ACCOUNTS = {
        'bn': {'apiKey': 'SQxzM22zGQl7nrFbxvf7DbjEpdQCNOlgcNmEA5p0h2hhNedRmJrP99s03rjcDZr1',
               'secret': 'riHRO8mc5kgsgHZfkg59CrQY4VcWCNf8fHvaLna06mLmYWTZQNFDBZMuKhmCvaIH'},
        'okex': {'apiKey': "71de2e01-8a7e-4dc6-b587-920997d7ec2c",
                 'secret': "9CB9F465BD1494EB6134742EC0DB3289",
                 'password': 'Quant123...', 'flag': '1'},
        # # hb,gate 没有测试网络
        # 'hb': {'apiKey': 'b7e15bdd-bgbfh5tv3f-0bf80824-d95e5',
        #        'secret': '4a340036-a21a5241-c8805729-c4b1c'},
        # 'gateio': {'apiKey': '4cb40d8969cafb0f4d360ea6030d768b',
        #          'secret': 'ded3a8f1e5cf658a6e9cc1eda6b8de8e3fde8ff69b10a89493fd4c7db62bb019'},
        'hb': {'apiKey': '197feb7b-bn2wed5t4y-25df15af-e0f03',
               'secret': '49eb1b08-67a413d5-766287c6-9e185'},
        'gate': {'apiKey': 'f483ee25a4b44935a6324437e4bcc3f9',
                 'secret': '0f93fb419b3350af79923cda0d9517bffd9a63890fb88418340afdc5e6d45cbb'},
        'mxc': {'apiKey': 'mx0vglAWFGsHeImiQM',
                'secret': 'cc2972dc2fc444b49dfd318ff24c2878'},
        'ethereum_1': {
            'apiKey': '0xC4CB0f670DFdC7c28F49F63feAacb2E10BAFdeC7',  # address
            'secret': '466da00cf375703f6dfe77ec1a97507126d26dd496621043f9134cff1ebf07d2',
            'node': 'https://goerli.infura.io/v3/a9c51f709a154d03a6f8a79af24fccb2'},

        'ethereum_2': {
            'apiKey': '0xa1Baf5E036BD4dD788e5f42A4C314C72098Ca242',  # address
            'secret': '32092bef785ee2a5a8e29a19e98768be1665c28b76f4833fe0717ad1671b5686',
            'node': 'https://goerli.infura.io/v3/a9c51f709a154d03a6f8a79af24fccb2'},

        'bsc_1': {
            'apiKey': '0xC4CB0f670DFdC7c28F49F63feAacb2E10BAFdeC7',  # address
            'secret': '466da00cf375703f6dfe77ec1a97507126d26dd496621043f9134cff1ebf07d2',
            'node': 'https://bsc-testnet.blockpi.network/v1/rpc/public'},
        'bitget': {'apiKey': 'bg_f841b315d26820fcae008edcf9c2d8ca',
                   'secret': 'd20f4b14dd107626b3dc7d3badcb225a4e2103be2a71a66e5e68ff13743ef807',
                   'password': '123456789'},
        'kraken': {'apiKey': '65R3R8msUtIozB3FcpNdHVpx+3p5/TyNWpv1e44QUO1tbXB1WyNbBXr+',
                   'secret': 'tot4Wb756e8xOcfZqF6CYfWpdhSKov0jFXaWoTnRfMubXV7A4V8T77v0TrtVE/66fVUxq6JS3KycWHpQDsbziA==',
                   },

    }
    ABC_ACCOUNTS = ['10', '11', '12', '13', '14', '15', '16', '17', '96']
else:
    EXTERNAL_ACCOUNTS = libs.libs_ex_account
    ABC_ACCOUNTS = ['10', '11', '12', '13', '14', '15', '16', '17']

DEX_ACCOUNT = ['ethereum', 'bsc']
