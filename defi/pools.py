import json
from itertools import combinations

from settings.env import env
from web3 import Web3

ethereum_web3 = Web3(Web3.HTTPProvider(env.mainnet_http_provider_url))
bsc_web3 = Web3(Web3.HTTPProvider(env.bsc_http_provider_url))
polygon_web3 = Web3(Web3.HTTPProvider(env.polygon_http_provider_url))

PROVIDERS = {
    'ethereum': ethereum_web3,
    'bsc': bsc_web3,
    'polygon': polygon_web3,
}

# tokens
with open('./defi/tokens.json') as f:
    chain_token_list = json.load(f)

# uniswap v2 Factory
with open('./defi/uniswap_factory.json') as f:
    uniswap_v2_factory_abi = json.load(f)

# uniswap v2 Pair
with open('./defi/uniswap_pair.json') as f:
    uniswap_v2_pair_abi = json.load(f)

uniswap_v2_factory_address = '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f'
uniswap_v2_factory_contract = PROVIDERS['ethereum'].eth.contract(
    address=uniswap_v2_factory_address, abi=uniswap_v2_factory_abi
)

pancakeswap_factory_address = '0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73'
pancakeswap_factory_contract = PROVIDERS['bsc'].eth.contract(
    address=pancakeswap_factory_address, abi=uniswap_v2_factory_abi
)

quickswap_factory_address = '0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32'
quickswap_factory_contract = PROVIDERS['polygon'].eth.contract(
    address=quickswap_factory_address, abi=uniswap_v2_factory_abi
)

CONTRACTS = {
    'uniswapv2': uniswap_v2_factory_contract,
    'pancakeswap': pancakeswap_factory_contract,
    'quickswap': quickswap_factory_contract,
}

PAIRS = {
    'uniswapv2': uniswap_v2_pair_abi,
    'pancakeswap': uniswap_v2_pair_abi,
    'quickswap': uniswap_v2_pair_abi,
}


def get_pools():
    response = {}

    for chain in chain_token_list:
        chain_name = chain['chain']
        protocol_name = chain['protocolName']

        chain_result = []
        response[chain_name] = chain_result

        web3 = PROVIDERS.get(chain_name, None)
        contract = CONTRACTS.get(protocol_name, None)
        pair_abi = PAIRS.get(protocol_name, None)

        if not chain_name:
            print(f'No web3 provider found for {chain_name}')
            continue

        if not contract:
            print(f'No factory contract found for chain {chain_name}: {protocol_name}')
            continue

        if not pair_abi:
            print(f'No pair ABI found for chain {chain_name}: {protocol_name}')
            continue

        pairs = combinations(chain['tokens'], 2)
        for pair in pairs:
            t1, t2 = pair
            t1_name = t1['name']
            t2_name = t2['name']
            name = f'{t1_name}/{t2_name}'

            pair_address = contract.functions.getPair(t1['address'], t2['address']).call()
            pair_contract = web3.eth.contract(address=pair_address, abi=pair_abi)

            t1_address = pair_contract.functions.token0().call()
            t2_address = pair_contract.functions.token1().call()

            t1_supply, t2_supply, _ = pair_contract.functions.getReserves().call()

            if t1_address != t1['address']:
                name = f'{t2_name}/{t1_name}'

            chain_result.append({
                'protocol_name': protocol_name,
                'pair_name': name,
                'token_0': t1_address,
                'token_1': t2_address,
                'token_0_supply': t1_supply,
                'token_1_supply': t2_supply
            })

    return response
