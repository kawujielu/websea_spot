from config.infor_load import libs_dex_config, spot_account

s_dex_mappers_all = libs_dex_config.s_dex_mappers

DEX_NODE_MAPPERS = {
    'etherscan': {'gapikey': '',
                  'chain_name': 'etherscan',
                  'chain_currency': 'ETH',
                  'node_pools': libs_dex_config.eth_node_pools,
                  'node_pools_mappers': [s_dex_mappers_all['uniswapv2'], s_dex_mappers_all['uniswapv3'], s_dex_mappers_all['sushi']],
                  'address': [spot_account['ethereum_1']['apiKey']]
                  },
    'bscscan': {'gapikey': '',
                'chain_name': 'bscscan',
                'chain_currency': 'BNB',
                'node_pools': libs_dex_config.bsc_node_pools,
                'node_pools_mappers': [s_dex_mappers_all['pancake']],
                'address': []
                },
    'matic': {'gapikey': '',
              'chain_name': 'matic',
              'chain_currency': '',
              'node_pools': libs_dex_config.matic_node_pools,
              'node_pools_mappers': [s_dex_mappers_all['matic']],
              'address': []
              },
}
