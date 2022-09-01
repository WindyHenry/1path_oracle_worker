from pydantic import BaseSettings, Field, RedisDsn


class Settings(BaseSettings):
    redis_dsn: RedisDsn = Field(default='redis://localhost:6379/0', env='redis_url')

    owlracle_api_key: str

    mainnet_http_provider_url: str
    bsc_http_provider_url: str
    polygon_http_provider_url: str

    get_gas_delay: float = 120
    get_pools_delay: float = 60
    get_quotes_delay: float = 60


env = Settings()
