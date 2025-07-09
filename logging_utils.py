import functools
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def log_call(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logging.info(f"Calling {func.__qualname__} with args={args} kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            logging.info(f"{func.__qualname__} returned {result}")
            return result
        except Exception as e:
            logging.exception(f"Exception in {func.__qualname__}: {e}")
            raise
    return wrapper

def async_log_call(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        logging.info(f"Calling {func.__qualname__} with args={args} kwargs={kwargs}")
        try:
            result = await func(*args, **kwargs)
            logging.info(f"{func.__qualname__} returned {result}")
            return result
        except Exception as e:
            logging.exception(f"Exception in {func.__qualname__}: {e}")
            raise
    return wrapper 