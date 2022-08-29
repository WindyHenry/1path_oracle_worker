# 1Path Oracle worker

Collects pools info and gas prices for 1Path Oracle, stores in redis for API to serve.

## Deployment

### Build image

1. `docker build -t oracle-worker .`
2. `docker push oracle-worker`

### Add env configuration (all env vars are required):

```
# Redis url to shared with Oracle API redis instance (same instance, same DB required)
REDIS_URL=redis://some-redis/0:6379

# Owracle API key, better to replace with your
OWLRACLE_API_KEY=15534502928e4f5c913b2142c8fa82bd

# Mainnet http provider url
MAINNET_HTTP_PROVIDER_URL=https://mainnet.infura.io/v3/<API_KEY>

# BSC http provider url
BSC_HTTP_PROVIDER_URL=https://bsc-dataseed.binance.org/

# Polygon http provider url
POLYGON_HTTP_PROVIDER_URL=https://polygon-mainnet.infura.io/v3/<API_KEY>

# Period in seconds to refresh gas prices
GET_GAS_DELAY=120

# Period in seconds to refresh pools info
GET_POOLS_DELAY=60

# Period in seconds to refresh pools info
GET_QUOTES_DELAY=60

```

### Add service to docker-compose:

```
oracle-worker:
  image: oracle-worker
  env_file: oracle-worker.env
  depends_on:
    - some-redis
  restart: always
```
