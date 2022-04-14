import asyncio
import json
from enum import Enum

import aioredis
import httpx

from defi.pools import get_pools
from settings.env import env

redis = aioredis.from_url(
    env.redis_dsn,
    encoding="utf-8",
    decode_responses=True,
)


class OwlracleGasPaths(str, Enum):
    bsc: str = f'https://owlracle.info/bsc/gas?accept=90&apikey={env.owlracle_api_key}'
    ethereum: str = f'https://owlracle.info/eth/gas?accept=90&apikey={env.owlracle_api_key}'
    polygon: str = f'https://owlracle.info/poly/gas?accept=90&apikey={env.owlracle_api_key}'

    @classmethod
    def names(cls):
        return [item.name for item in cls]


async def get_estimated_fee(url) -> float:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()['speeds'][0]['estimatedFee']


async def get_gas() -> None:
    tasks = [asyncio.create_task(get_estimated_fee(path.value)) for path in OwlracleGasPaths]
    estimated_fee_results = await asyncio.gather(*tasks)
    data = dict(zip(OwlracleGasPaths.names(), estimated_fee_results))

    await redis.set('gas', json.dumps(data))


async def get_gas_scheduler() -> None:
    while True:
        await asyncio.gather(
            get_gas(),
            asyncio.sleep(env.get_gas_delay),
        )


async def get_and_store_pools() -> None:
    pools = get_pools()

    await redis.set('pools', json.dumps(pools))


async def get_pools_scheduler() -> None:
    while True:
        await asyncio.gather(
            get_and_store_pools(),
            asyncio.sleep(env.get_pools_delay),
        )


async def main():
    while True:
        await asyncio.gather(get_gas_scheduler(), get_pools_scheduler())


if __name__ == "__main__":
    asyncio.run(main())
