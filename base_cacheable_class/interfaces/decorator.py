from abc import ABC, abstractmethod
from collections.abc import Callable


class CacheDecoratorInterface(ABC):
    @abstractmethod
    def __call__(self, ttl: int | None = None) -> Callable:
        pass

    @abstractmethod
    def invalidate(self, target_func_name: str, param_mapping: dict[str, str] | None = None) -> Callable:
        pass

    @abstractmethod
    def invalidate_all(self) -> Callable:
        pass
