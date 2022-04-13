import asyncio
import json
from enum import Enum

import aioredis
import httpx
from pydantic import BaseSettings, Field, RedisDsn


class Settings(BaseSettings):
    redis_dsn: RedisDsn = Field(default='redis://localhost/0:6379', env='redis_url')

    owlracle_api_key: str = '15534502928e4f5c913b2142c8fa82bd'

    get_gas_delay: float = 120
    get_pools_delay: float = 1


env = Settings()

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


async def get_gas_sheduler() -> None:
    while True:
        await asyncio.gather(
            get_gas(),
            asyncio.sleep(env.get_gas_delay),
        )


async def get_pools() -> None:
    # ⚔️🛡️ Write code here ⚔️🛡️
    print('Some "Get Pools" async mock (with doggos) 🐶🐶🐶')


async def get_pools_sheduler():
    while True:
        await asyncio.gather(
            get_pools(),
            asyncio.sleep(env.get_pools_delay),
        )


async def main():
    while True:
        await asyncio.gather(get_gas_sheduler(), get_pools_sheduler())


if __name__ == "__main__":
    asyncio.run(main())
