import redis
from config import settings

# Create a global Redis connection pool
redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)

def get_redis():
    """
    Returns a Redis client instance from the connection pool.
    """
    return redis.Redis(connection_pool=redis_pool)
