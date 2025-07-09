import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from ...interfaces import CacheDecoratorInterface, CacheInterface

logger = logging.getLogger(__name__)


class InMemoryCacheDecorator(CacheDecoratorInterface):
    def __init__(self, cache: CacheInterface, default_ttl: int = 60):
        self.cache = cache
        self.default_ttl = default_ttl

    def key_builder(self, f: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        arg_str = str(args)
        kwarg_str = str(kwargs) if kwargs else "{}"
        func_name = getattr(f, "__name__", "unknown")
        return f"{func_name}:{arg_str}:{kwarg_str}"

    def __call__(self, ttl: int | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                _key = self.key_builder(func, *args, **kwargs)
                current_ttl = ttl if ttl is not None else self.default_ttl

                try:
                    cached_value = await self.cache.get(_key)
                    if cached_value is not None:
                        return cached_value

                    result = await func(*args, **kwargs)

                    if result is not None:
                        await self.cache.set(_key, result, ttl=current_ttl)

                    return result
                except Exception as e:
                    logger.error(f"Error in cache decorator: {e}")
                    return await func(*args, **kwargs)

            return wrapper

        return decorator

    def invalidate(
        self, target_func_name: str, param_mapping: dict[str, str] | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    pattern = rf"{target_func_name}:\(.*\):{{.*}}"
                    if param_mapping:
                        # 매핑된 파라미터 값 추출
                        mapped_kwargs = {
                            target_param: kwargs[source_param]
                            for target_param, source_param in param_mapping.items()
                            if source_param in kwargs
                        }
                        kwargs_patterns = [rf".*'{k}':\s*'{v!s}'" for k, v in mapped_kwargs.items()]
                        pattern = rf"{target_func_name}:\(.*\):{{" + ".*".join(kwargs_patterns) + ".*}"

                    cached_keys = await self.cache.get_keys(pattern)

                    for cache_key in cached_keys:
                        await self.cache.delete(cache_key)

                except Exception as e:
                    logger.error(f"Error in cache invalidation: {e}")

                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def invalidate_all(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                _key = self.key_builder(func, *args, **kwargs)
                try:
                    await self.cache.clear()
                except Exception as e:
                    logger.error(f"Error in cache clear: {e}")
                return await func(*args, **kwargs)

            return wrapper

        return decorator
