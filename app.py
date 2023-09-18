import asyncio
import json
from datetime import datetime
from enum import Enum

import aioredis
import httpx

from defi.pools import get_pools
from settings.env import env
from pycoingecko import CoinGeckoAPI

redis = aioredis.from_url(
    env.redis_dsn,
    encoding="utf-8",
    decode_responses=True,
)


class OwlracleGasPaths(str, Enum):
    bsc: str = f'https://api.owlracle.info/v3/bsc/gas?accept=90&apikey={env.owlracle_api_key}'
    ethereum: str = f'https://api.owlracle.info/v3/eth/gas?accept=90&apikey={env.owlracle_api_key}'
    polygon: str = f'https://api.owlracle.info/v3/poly/gas?accept=90&apikey={env.owlracle_api_key}'

    @classmethod
    def names(cls):
        return [item.name for item in cls]


async def get_estimated_fee(url):
    task = asyncio.create_task(collect_quotes_for_gas_coingecko())
    quotes = await asyncio.gather(task)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            for item in quotes[0]:
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
    tasks = [asyncio.create_task(get_estimated_fee(path.value)) for path in OwlracleGasPaths]
    estimated_fee_results = await asyncio.gather(*tasks)
    new_gas = dict(zip(OwlracleGasPaths.names(), estimated_fee_results))
    old_gas = await redis.get('gas')

    if old_gas:
        try:
            old_gas = json.loads(old_gas)
            old_values = [x for x in old_gas if new_gas.get(x) is None or not new_gas.get(x, {}).get('value')]
            for key in old_values:
                new_gas[key] = old_gas[key]

        except Exception as e:
            print(f'Failed to save gas: {e}')

    await redis.set('gas', json.dumps(new_gas))


async def collect_quotes_coingecko():
    cg = CoinGeckoAPI()
    ids_q = ['usd-coin', 'dai', 'ethereum', 'tether', 'wrapped-bitcoin', 'binance-usd', 'matic-network','chainlink', 'litecoin',
     'dogecoin', 'tron', 'avalanche-2', 'binancecoin', 'baby-doge-coin', 'pancakeswap-token', 'uniswap', 'wombat-exchange', 'woo-network']
    temp_quotes = cg.get_price(ids=ids_q, vs_currencies='usd')
    quotes_output = [
        {"name": str('DAI'), "value": temp_quotes['dai']['usd']},
        {"name": str('USDC'), "value": temp_quotes['usd-coin']['usd']},
        {"name": str('USDT'), "value": temp_quotes['tether']['usd']},
        {"name": str('WETH'), "value": temp_quotes['ethereum']['usd']},
        {"name": str('WBTC'), "value": temp_quotes['wrapped-bitcoin']['usd']},
        {"name": str('BUSD'), "value": temp_quotes['binance-usd']['usd']},
        {"name": str('MATIC'), "value": temp_quotes['matic-network']['usd']},
        {"name": str('LINK'), "value": temp_quotes['chainlink']['usd']},
        {"name": str('LTC'), "value": temp_quotes['litecoin']['usd']},
        {"name": str('DOGE'), "value": temp_quotes['dogecoin']['usd']},
        {"name": str('TRX'), "value": temp_quotes['tron']['usd']},
        {"name": str('AVAX'), "value": temp_quotes['avalanche-2']['usd']},
        {"name": str('BNB'), "value": temp_quotes['binancecoin']['usd']},
        {"name": str('WBNB'), "value": temp_quotes['binancecoin']['usd']},
        {"name": str('BabyDoge'), "value": temp_quotes['baby-doge-coin']['usd']},
        {"name": str('CAKE'), "value": temp_quotes['pancakeswap-token']['usd']},
        {"name": str('UNI'), "value": temp_quotes['uniswap']['usd']},
        {"name": str('WOM'), "value": temp_quotes['wombat-exchange']['usd']},
        {"name": str('WOO'), "value": temp_quotes['woo-network']['usd']}
    ]
    return quotes_output


async def collect_quotes_for_gas_coingecko():
    cg = CoinGeckoAPI()
    ids_q = ['ethereum', 'matic-network', 'binancecoin']
    temp_quotes = cg.get_price(ids=ids_q, vs_currencies='usd')
    quotes_for_gas_output = [
        {"name": str('ETH'), "value": temp_quotes['ethereum']['usd'], "chain": str('eth')},
        {"name": str('MATIC'), "value": temp_quotes['matic-network']['usd'], "chain": str('poly')},
        {"name": str('BNB'), "value": temp_quotes['binancecoin']['usd'], "chain": str('bsc')}
    ]
    return quotes_for_gas_output


async def get_quotes() -> None:
    task = asyncio.create_task(collect_quotes_coingecko())
    new_quotes = await asyncio.gather(task)
    old_quotes = await redis.get('quotes')

    await redis.set('quotes', json.dumps(new_quotes[0]))


async def get_gas_scheduler() -> None:
    while True:
        await asyncio.gather(
            get_gas(),
            asyncio.sleep(env.get_gas_delay),
        )


async def get_quotes_scheduler() -> None:
    while True:
        await asyncio.gather(
            get_quotes(),
            asyncio.sleep(env.get_quotes_delay),
        )


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


async def get_pools_scheduler() -> None:
    while True:
        await asyncio.gather(
            get_and_store_pools(),
            asyncio.sleep(env.get_pools_delay),
        )


async def main():
    while True:
        await asyncio.gather(get_gas_scheduler(), get_pools_scheduler(), get_quotes_scheduler())


if __name__ == "__main__":
    asyncio.run(main())
