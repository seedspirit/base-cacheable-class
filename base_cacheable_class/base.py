from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from .interfaces import CacheDecoratorInterface

F = TypeVar("F", bound=Callable[..., Any])


class BaseCacheableClass:
    def __init__(self, cache_decorator: CacheDecoratorInterface) -> None:
        self._cache_decorator = cache_decorator

    def wrapped(self, func: F) -> F:
        return self._cache_decorator()(func)  # type: ignore

    @classmethod
    def cache(cls, ttl: int | None = None) -> Callable[[F], F]:
        # Note: if `ttl` is None, then the cache is stored forever in-memory.
        def decorator(func: F) -> F:
            @wraps(func)
            async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
                if not hasattr(self, "_cache_decorator"):
                    raise AttributeError("_cache_decorator not found. Did you call super().__init__?")
                return await self._cache_decorator(ttl=ttl)(func)(self, *args, **kwargs)

            return wrapper  # type: ignore

        return decorator

    @classmethod
    def invalidate(cls, target_func_name: str, param_mapping: dict[str, str] | None = None) -> Callable[[F], F]:
        """조건에 따른 캐시 무효화 로직.

        target_func: 캐시를 무효화할 대상 함수
        param_mapping: 현재 함수의 파라미터와 대상 함수 파라미터 간의 매핑
        예: {'user_id': 'customer_id'} -> 현재 함수의 customer_id를 target_func의 user_id로 매핑
        """

        def decorator(func: F) -> F:
            @wraps(func)
            async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
                if not hasattr(self, "_cache_decorator"):
                    raise AttributeError("_cache_decorator not found. Did you call super().__init__?")
                return await self._cache_decorator.invalidate(target_func_name, param_mapping)(func)(
                    self, *args, **kwargs
                )

            return wrapper  # type: ignore

        return decorator

    @classmethod
    def invalidate_all(cls) -> Callable[[F], F]:
        def decorator(func: F) -> F:
            @wraps(func)
            async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
                if not hasattr(self, "_cache_decorator"):
                    raise AttributeError("_cache_decorator not found. Did you call super().__init__?")
                return await self._cache_decorator.invalidate_all()(func)(self, *args, **kwargs)

            return wrapper  # type: ignore

        return decorator
