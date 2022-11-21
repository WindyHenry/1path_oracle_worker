import json
from datetime import datetime
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

# multichain pool addresses
with open('./defi/multichain_pools.json') as f:
    multichain_pools = json.load(f)
    
# symbiosis pool addresses
with open('./defi/symbiosis_pools.json') as f:
    symbiosis_pools = json.load(f)

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

minABI = [
    {
        'constant': True,
        'inputs': [{'name': "_owner", 'type': "address"}],
        'name': "balanceOf",
        'outputs': [{'name': "balance", 'type': "uint256"}],
        'type': "function",
    },
]

symbiosis_ABI = [
    {
        'constant': True,
        'inputs': [{'name': "_owner", 'type': "address"}],
        'name': "getTokenIndex",
        'outputs': [{'name': "index", 'type': "uint8"}],
        'type': "function",
    },
    {
        'constant': True,
        'inputs': [{'name': "_owner", 'type': "uint8"}],
        'name': "getTokenBalance",
        'outputs': [{'name': "index", 'type': "uint256"}],
        'type': "function",
    }
]


def get_pools():
    response = {"swap_pools": {}, "bridge_pools": {}}

    for chain in chain_token_list:
        chain_name = chain['chain']
        protocol_name = chain['protocolName']

        chain_result = []
        response["swap_pools"][chain_name] = chain_result

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
            try:
                t1, t2 = pair
                t1_name = t1['name']
                t2_name = t2['name']
                name = f'{t1_name}/{t2_name}'

                pair_address = contract.functions.getPair(t1['address'], t2['address']).call()
                pair_contract = web3.eth.contract(address=pair_address, abi=pair_abi)

                t1_address = pair_contract.functions.token0().call()
                t2_address = pair_contract.functions.token1().call()

                now = datetime.now()

                t1_supply, t2_supply, _ = pair_contract.functions.getReserves().call()

                if t1_address != t1['address']:
                    name = f'{t2_name}/{t1_name}'

                chain_result.append({
                    'protocol_name': protocol_name,
                    'pair_name': name,
                    'token_0': t1_address,
                    'token_1': t2_address,
                    'pair_address': pair_address,
                    'token_0_supply': t1_supply,
                    'token_1_supply': t2_supply,
                    'date_updated': now.isoformat()
                })

            except Exception as e:
                # do not add pair to chain list if cannot get info
                print(f'Failed to update pair {name} on {chain_name}: {e}')

    # multichain pools
    for chain in multichain_pools:
        protocol_name = chain['protocolName']
        chain_name = chain['chain']
        chain_result = []
        temp_chain_token_info = {}
        for chain_tokens in chain_token_list:
            if chain_tokens['chain'] == chain_name:
                temp_chain_token_info = chain_tokens['tokens']
        for bridge_token_info in chain['tokens']:
            token_result = {}
            for i in temp_chain_token_info:
                if i['name'] == bridge_token_info['name']:
                    token_address = i['address']
                name = bridge_token_info['name']
            try:
                contract = PROVIDERS[chain_name].eth.contract(address=token_address, abi=minABI)
                token_balance = contract.functions.balanceOf(bridge_token_info['address']).call()
                now = datetime.now()

                token_result['protocol_name'] = protocol_name
                token_result['token_name'] = name
                token_result['token_address'] = token_address
                token_result['token_supply'] = token_balance
                token_result['date_updated'] = now.isoformat()
                chain_result.append(token_result)
            except Exception as e:
                # do not add pair to chain list if cannot get info
                print(f'Failed to update {protocol_name} pool info of {name} on {chain_name}: {e}')
        response["bridge_pools"][chain_name] = chain_result
     
    # symbiosis pools
    for chainPair in symbiosis_pools:

        protocol_name = chainPair['protocolName']
        chain_name = chainPair['chainPair']
        chain_result_sym = []
    
        for token_info in chainPair['nerves']:
            token_address = Web3.toChecksumAddress(token_info['address'])
            token_result = {}

            try:
                
                contract = PROVIDERS[chain_name.split('_')[0]].eth.contract(address=token_address, abi=symbiosis_ABI)
            
                token0address = Web3.toChecksumAddress(token_info['tokens'][0]['address'])
                token0decimals = token_info['tokens'][0]['decimals']
                token1address = Web3.toChecksumAddress(token_info['tokens'][1]['address'])
                token1decimals = token_info['tokens'][1]['decimals']
            
                ind0 = contract.functions.getTokenIndex(token0address).call()
                ind1 = contract.functions.getTokenIndex(token1address).call()
            
                token_balance0 = contract.functions.getTokenBalance(ind0).call() / (10 ** token0decimals)
                token_balance1 = contract.functions.getTokenBalance(ind1).call() / (10 ** token1decimals)
            
                token_balance = token_balance0 + token_balance1            
                now = datetime.now()

                token_result['protocol_name'] = protocol_name
                token_result['pair_address'] = token_address
                token_result['token_supply'] = token_balance
                token_result['date_updated'] = now.isoformat()
                chain_result_sym.append(token_result)
                
            except Exception as e:
                print(f'Failed to update {protocol_name} pool info on {chain_name}: {e}')
        response["bridge_pools"][chain_name] = chain_result_sym
        
    return response
