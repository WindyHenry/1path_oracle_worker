import asyncio
import json
from datetime import datetime
from enum import Enum

import aioredis
import httpx
from pycoingecko import CoinGeckoAPI

from defi.pools import get_pools
from settings.env import env

redis = aioredis.from_url(
    env.redis_dsn,
    encoding="utf-8",
    decode_responses=True,
)

cg = CoinGeckoAPI()


class CoinGeckoTokens(str, Enum):
    ETH = 'ethereum'
    WETH = 'weth'
    WBTC = 'wrapped-bitcoin'
    DAI = 'dai'
    USDT = 'tether'
    USDC = 'usd-coin'
    MATIC = 'matic-network'
    BNB = 'binancecoin'

    @classmethod
    def values_list(cls):
        return [e.value for e in cls]


class OwlracleGasPaths(str, Enum):
    bsc: str = f'https://api.owlracle.info/v3/bsc/gas?accept=90&apikey={env.owlracle_api_key}'
    ethereum: str = f'https://api.owlracle.info/v3/eth/gas?accept=90&apikey={env.owlracle_api_key}'
    polygon: str = f'https://api.owlracle.info/v3/poly/gas?accept=90&apikey={env.owlracle_api_key}'

    @classmethod
    def names(cls):
        return [item.name for item in cls]


async def get_estimated_fee(url, gas_quotes):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            for item in gas_quotes:
                if url.split('/')[-2] == 'bsc' and item['chain'] == 'bsc':
                    return {
                        'gwei': response.json()['speeds'][0]['gasPrice'],
                        'tokenPrice': item['value'],
                        'dateUpdated': datetime.now().isoformat(),
                    }
                elif url.split('/')[-2] == item['chain']:
                    return {
                        'gwei': response.json()['speeds'][0]['baseFee'],
                        'tokenPrice': item['value'],
                        'dateUpdated': datetime.now().isoformat(),
                    }
        except (KeyError, httpx.NetworkError, httpx.HTTPError) as e:
            print(f'Failed to get gas ({url}): {e}')
            return None


async def get_gas() -> None:
    gas_quotes = await collect_quotes_for_gas_coingecko()
    tasks = [asyncio.create_task(get_estimated_fee(path.value, gas_quotes)) for path in OwlracleGasPaths]
    estimated_fee_results = await asyncio.gather(*tasks)
    new_gas = dict(zip(OwlracleGasPaths.names(), estimated_fee_results))
    old_gas = await redis.get('gas')

    if old_gas:
        try:
            old_gas = json.loads(old_gas)
            old_values = [x for x in old_gas if new_gas.get(x) is None or not new_gas.get(x, {}).get('tokenPrice')]
            for key in old_values:
                new_gas[key] = old_gas[key]

        except Exception as e:
            print(f'Failed to save gas: {e}')

    print('setting gas')
    await redis.set('gas', json.dumps(new_gas))


async def get_and_store_quotes() -> None:
    quotes_response: dict = cg.get_price(ids=CoinGeckoTokens.values_list(), vs_currencies='usd')

    quotes_output = [{
        'token_name': CoinGeckoTokens(k).name,
        'value': v['usd'],
        'date_updated': datetime.now().isoformat(),
    } for k, v in quotes_response.items()]

    await redis.set('quotes', json.dumps(quotes_output))


async def collect_quotes_for_gas_coingecko():
    cg = CoinGeckoAPI()
    ids_q = ['ethereum', 'matic-network', 'binancecoin']
    temp_quotes = cg.get_price(ids=ids_q, vs_currencies='usd')
    quotes_for_gas_output = [{
        "name": str('ETH'),
        "value": temp_quotes['ethereum']['usd'],
        "chain": str('eth')
    }, {
        "name": str('MATIC'),
        "value": temp_quotes['matic-network']['usd'],
        "chain": str('poly')
    }, {
        "name": str('BNB'),
        "value": temp_quotes['binancecoin']['usd'],
        "chain": str('bsc')
    }]
    return quotes_for_gas_output


async def get_and_store_pools() -> None:

    new_pools = get_pools()

    old_pools = await redis.get('pools')

    if not old_pools:
        pools = new_pools

    else:
        try:
            old_pools = json.loads(old_pools)

        except Exception:
            pass
        for pool_type in ["swap_pools", "bridge_pools"]:
            for chain_name, old_chain_pairs in old_pools[pool_type].items():
                if pool_type == "swap_pools":
                    key_name = 'pair_name'
                else:
                    key_name = 'token_name'
                old_chain_pairs_dict = dict((item[key_name], item) for item in old_chain_pairs)
                new_chain_pairs = dict((item[key_name], item) for item in new_pools[pool_type][chain_name])

                not_updated = [item for name, item in old_chain_pairs_dict.items() if name not in new_chain_pairs]
                new_pools[pool_type][chain_name] += not_updated

        pools = new_pools

    await redis.set('pools', json.dumps(pools))


async def get_gas_scheduler() -> None:
    while True:
        await asyncio.gather(
            get_gas(),
            asyncio.sleep(env.get_gas_delay),
        )


async def get_quotes_scheduler() -> None:
    while True:
        await asyncio.gather(
            get_and_store_quotes(),
            asyncio.sleep(env.get_quotes_delay),
        )


async def get_pools_scheduler() -> None:
    while True:
        await asyncio.gather(
            get_and_store_pools(),
            asyncio.sleep(env.get_pools_delay),
        )


async def main():
    while True:
        await asyncio.gather(
            get_gas_scheduler(),
            get_pools_scheduler(),
            get_quotes_scheduler(),
        )


if __name__ == "__main__":
    asyncio.run(main())
