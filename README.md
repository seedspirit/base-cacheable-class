# base-cacheable-class

A flexible base class for adding caching capabilities to your Python classes.

## Features
- Asynchronous Support 
- Simple decorator-based caching for class methods
- Support for both in-memory and Redis cache backends
- TTL (Time To Live) support
- Cache invalidation strategies
- Async/await support
- Type hints included

## To come
* Synchronous Operation Support

## Installation

```bash
uv add base-cacheable-class
```

For Redis support:
```bash
uv add base-cacheable-class[redis]
```

## Quick Start

### Basic Usage with In-Memory Cache

```python
import asyncio
from base_cacheable_class import BaseCacheableClass, InMemoryCache, InMemoryCacheDecorator


class UserService(BaseCacheableClass):
    def __init__(self):
        cache = InMemoryCache()
        cache_decorator = InMemoryCacheDecorator(cache, default_ttl=300)  # 5 minutes default
        super().__init__(cache_decorator)
    
    @BaseCacheableClass.cache(ttl=60)  # Cache for 1 minute
    async def get_user(self, user_id: int):
        # Expensive operation here
        return {"id": user_id, "name": f"User {user_id}"}
    
    @BaseCacheableClass.invalidate("get_user", param_mapping={"user_id": "user_id"})
    async def update_user(self, user_id: int, name: str):
        # Update user logic here
        return {"id": user_id, "name": name}


async def main():
    service = UserService()
    
    # First call - will execute the function
    user = await service.get_user(1)
    print(user)  # {"id": 1, "name": "User 1"}
    
    # Second call - will return cached result
    user = await service.get_user(1)
    print(user)  # {"id": 1, "name": "User 1"} (from cache)
    
    # Update user - will invalidate cache
    await service.update_user(1, "Updated User")
    
    # Next call - will execute the function again
    user = await service.get_user(1)
    print(user)  # {"id": 1, "name": "User 1"}


if __name__ == "__main__":
    asyncio.run(main())
```

### Using Redis Cache

```python
import asyncio
from base_cacheable_class import BaseCacheableClass, RedisCache, RedisCacheDecorator


class ProductService(BaseCacheableClass):
    def __init__(self):
        cache = RedisCache(
            host="localhost",
            port=6379,
            password="your_password",
            db=0
        )
        cache_decorator = RedisCacheDecorator(cache, default_ttl=3600)  # 1 hour default
        super().__init__(cache_decorator)
    
    @BaseCacheableClass.cache(ttl=300)  # Cache for 5 minutes
    async def get_product(self, product_id: int):
        # Fetch product from database
        return {"id": product_id, "name": f"Product {product_id}"}
    
    @BaseCacheableClass.invalidate_all()
    async def refresh_catalog(self):
        # Clear all caches when catalog is refreshed
        return "Catalog refreshed"


async def main():
    service = ProductService()
    
    # Use the service
    product = await service.get_product(1)
    print(product)
    
    # Clear all caches
    await service.refresh_catalog()


if __name__ == "__main__":
    asyncio.run(main())
```

* Special Thanks to: https://github.com/Ilevk/fastapi-tutorial/blob/098d3a05f224220cc2cd5125dea5c5cf7bb810ab/app/core/redis.py#L35

## API Reference

### Decorators

#### `@BaseCacheableClass.cache(ttl=None)`
Cache the decorated method's result. If `ttl` is None, cache indefinitely.

#### `@BaseCacheableClass.invalidate(target_func_name, param_mapping=None)`
Invalidate cache for specific function when the decorated method is called.
- `target_func_name`: Name of the function whose cache should be invalidated
- `param_mapping`: Dict mapping current function params to target function params

#### `@BaseCacheableClass.invalidate_all()`
Clear all caches when the decorated method is called.

### Cache Backends

#### InMemoryCache
Simple in-memory cache using a dictionary. Singleton pattern ensures single instance.

#### RedisCache
Redis-based cache with support for distributed systems.

Constructor parameters:
- `host`: Redis host
- `port`: Redis port
- `password`: Redis password
- `db`: Redis database number (default: 0)
- `username`: Redis username
- `socket_timeout`: Socket timeout in seconds (default: 0.5)
- `socket_connect_timeout`: Connection timeout in seconds (default: 0.5)

#### Multi-tier Caching (L1/L2) Patterns

```python
class MultiTierCacheDecorator(CacheDecoratorInterface):
    """Implements L1/L2 caching with memory as L1 and Redis as L2."""
    
    def __init__(self, l1_cache: CacheDecoratorInterface, l2_cache: CacheDecoratorInterface):
        self.l1_cache = l1_cache
        self.l2_cache = l2_cache
    
    async def get(self, key: str) -> Optional[Any]:
        # Try L1 first
        value = await self.l1_cache.get(key)
        if value is not None:
            return value
        
        # Try L2
        value = await self.l2_cache.get(key)
        if value is not None:
            # Populate L1
            await self.l1_cache.set(key, value, ttl=60)  # Short TTL for L1
        
        return value
```

## License

MIT License