import json
import logging
import os
import time
from redis import Redis
from redis.exceptions import RedisError

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("paytrack-worker")
redis_url = os.environ["REDIS_URL"]

while True:
    try:
        client = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)
        client.ping()
        logger.info("Worker connected; waiting for payment events")
        while True:
            item = client.brpop("paytrack:events", timeout=5)
            if item:
                _, raw = item
                try:
                    logger.info("Processed demo event: %s", json.dumps(json.loads(raw), sort_keys=True))
                except json.JSONDecodeError:
                    logger.warning("Received invalid event payload")
    except (RedisError, OSError) as exc:
        logger.error("Queue unavailable (%s); retrying in 3 seconds", exc)
        time.sleep(3)
