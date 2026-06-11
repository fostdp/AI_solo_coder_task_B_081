import json
import redis
from shared.config import get_settings

_client = None


def get_redis():
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def publish(channel: str, data: dict):
    r = get_redis()
    r.publish(channel, json.dumps(data, ensure_ascii=False))


def subscribe(channels: list):
    r = get_redis()
    pubsub = r.pubsub()
    pubsub.subscribe(channels)
    return pubsub


def cache_set(key: str, data: dict, ttl: int = 3600):
    r = get_redis()
    r.set(key, json.dumps(data, ensure_ascii=False), ex=ttl)


def cache_get(key: str) -> dict:
    r = get_redis()
    val = r.get(key)
    if val is None:
        return None
    return json.loads(val)


def cache_delete(key: str):
    r = get_redis()
    r.delete(key)


class RedisChannels:
    FORMULA_UPDATED = "formula:updated"
    FORMULA_TRANSACTIONS = "formula:transactions"
    MINING_RESULT = "mining:result"
    COMMUNITY_RESULT = "community:result"
    GRAPH_NETWORK = "graph:network"
