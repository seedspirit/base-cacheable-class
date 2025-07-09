"""
Advanced Dependency Injection Example with Environment-based Configuration

This example demonstrates:
- Environment-based configuration management
- Factory patterns for cache creation
- Multi-tier caching (L1/L2)
- Conditional cache provider selection
- Configuration profiles (dev/staging/prod)
"""

import asyncio
import os
from enum import Enum
from typing import Any

from dependency_injector import containers, providers

from base_cacheable_class import BaseCacheableClass, CacheDecoratorInterface, InMemoryCache, InMemoryCacheDecorator

try:
    from base_cacheable_class import RedisCache, RedisCacheDecorator
except ImportError:
    # Redis is optional
    RedisCache: type[Any] | None = None
    RedisCacheDecorator: type[Any] | None = None


# Configuration Enums
class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class CacheStrategy(str, Enum):
    MEMORY_ONLY = "memory_only"
    REDIS_ONLY = "redis_only"
    MULTI_TIER = "multi_tier"  # L1: Memory, L2: Redis


# Multi-tier Cache Decorator
class MultiTierCacheDecorator(CacheDecoratorInterface):
    """Implements L1/L2 caching with memory as L1 and Redis as L2."""

    def __init__(self, l1_cache: CacheDecoratorInterface, l2_cache: CacheDecoratorInterface):
        self.l1_cache = l1_cache
        self.l2_cache = l2_cache

    async def get(self, key: str) -> Any | None:
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

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        # Set in both caches
        await asyncio.gather(
            self.l1_cache.set(key, value, ttl=min(ttl or 300, 300)),  # L1 with shorter TTL
            self.l2_cache.set(key, value, ttl=ttl),
        )

    async def delete(self, key: str) -> None:
        await asyncio.gather(self.l1_cache.delete(key), self.l2_cache.delete(key))

    async def clear(self) -> None:
        await asyncio.gather(self.l1_cache.clear(), self.l2_cache.clear())

    async def exists(self, key: str) -> bool:
        return await self.l1_cache.exists(key) or await self.l2_cache.exists(key)


# Services
class UserService(BaseCacheableClass):
    """User service with caching capabilities."""

    def __init__(self, cache_decorator: CacheDecoratorInterface, db_latency: float = 0.1):
        super().__init__(cache_decorator)
        self.db_latency = db_latency
        self._db_calls = 0

    @BaseCacheableClass.cache(ttl=3600)  # 1 hour
    async def get_user(self, user_id: int) -> dict[str, Any]:
        self._db_calls += 1
        print(f"[DB] Fetching user {user_id} (latency: {self.db_latency}s)")
        await asyncio.sleep(self.db_latency)
        return {"id": user_id, "name": f"User {user_id}", "email": f"user{user_id}@example.com", "role": "standard"}

    @BaseCacheableClass.cache(ttl=7200)  # 2 hours
    async def get_user_profile(self, user_id: int) -> dict[str, Any]:
        user = await self.get_user(user_id)
        self._db_calls += 1
        print(f"[DB] Fetching profile for user {user_id}")
        await asyncio.sleep(self.db_latency / 2)
        return {
            **user,
            "bio": f"Bio for {user['name']}",
            "avatar": f"https://avatar.com/{user_id}",
            "preferences": {"theme": "dark", "language": "en"},
        }

    @BaseCacheableClass.invalidate("get_user", param_mapping={"user_id": "user_id"})
    @BaseCacheableClass.invalidate("get_user_profile", param_mapping={"user_id": "user_id"})
    async def update_user(self, user_id: int, **kwargs) -> dict[str, Any]:
        print(f"[DB] Updating user {user_id}")
        return {"id": user_id, "updated": True, **kwargs}

    @property
    def db_call_count(self) -> int:
        return self._db_calls


class AnalyticsService(BaseCacheableClass):
    """Analytics service with different caching requirements."""

    def __init__(self, cache_decorator: CacheDecoratorInterface):
        super().__init__(cache_decorator)

    @BaseCacheableClass.cache(ttl=300)  # 5 minutes for real-time data
    async def get_active_users(self) -> int:
        print("[ANALYTICS] Calculating active users")
        await asyncio.sleep(0.2)
        return 1542

    @BaseCacheableClass.cache(ttl=3600)  # 1 hour for aggregated data
    async def get_daily_stats(self, date: str) -> dict[str, Any]:
        print(f"[ANALYTICS] Calculating stats for {date}")
        await asyncio.sleep(0.3)
        return {"date": date, "total_users": 10000, "active_users": 1542, "new_signups": 123, "revenue": 5432.10}


# Configuration Management
class ConfigLoader:
    """Loads configuration from environment variables and files."""

    @staticmethod
    def load_from_env() -> dict[str, Any]:
        env = os.getenv("APP_ENV", Environment.DEVELOPMENT.value)

        # Default configurations
        configs = {
            Environment.DEVELOPMENT: {
                "cache_strategy": CacheStrategy.MEMORY_ONLY,
                "cache_ttl": 300,
                "redis": {"host": "localhost", "port": 6379, "password": "", "db": 0},
                "features": {"cache_warming": False, "cache_metrics": True},
            },
            Environment.STAGING: {
                "cache_strategy": CacheStrategy.MULTI_TIER,
                "cache_ttl": 600,
                "redis": {
                    "host": os.getenv("REDIS_HOST", "staging-redis"),
                    "port": int(os.getenv("REDIS_PORT", "6379")),
                    "password": os.getenv("REDIS_PASSWORD", ""),
                    "db": 1,
                },
                "features": {"cache_warming": True, "cache_metrics": True},
            },
            Environment.PRODUCTION: {
                "cache_strategy": CacheStrategy.REDIS_ONLY,
                "cache_ttl": 3600,
                "redis": {
                    "host": os.getenv("REDIS_HOST", "prod-redis"),
                    "port": int(os.getenv("REDIS_PORT", "6379")),
                    "password": os.getenv("REDIS_PASSWORD", ""),
                    "db": 0,
                    "socket_timeout": 5,
                    "socket_connect_timeout": 5,
                },
                "features": {"cache_warming": True, "cache_metrics": True},
            },
            Environment.TEST: {
                "cache_strategy": CacheStrategy.MEMORY_ONLY,
                "cache_ttl": 60,
                "redis": {"host": "localhost", "port": 6379, "password": "", "db": 15},
                "features": {"cache_warming": False, "cache_metrics": False},
            },
        }

        config = configs.get(Environment(env), configs[Environment.DEVELOPMENT])
        config["environment"] = env
        return config


# Advanced DI Container
class ApplicationContainer(containers.DeclarativeContainer):
    """Advanced DI container with environment-based configuration."""

    # Configuration provider
    config = providers.Configuration()

    # Load configuration from environment
    config_loader = providers.Singleton(ConfigLoader.load_from_env)

    # Cache implementations
    memory_cache = providers.Singleton(InMemoryCache)

    redis_cache = providers.Singleton(
        RedisCache,
        host=config.redis.host,
        port=config.redis.port,
        password=config.redis.password,
        db=config.redis.db,
        socket_timeout=config.redis.socket_timeout.optional(5),
        socket_connect_timeout=config.redis.socket_connect_timeout.optional(5),
    )

    # Cache decorators
    memory_cache_decorator = providers.Factory(InMemoryCacheDecorator, cache=memory_cache, default_ttl=config.cache_ttl)

    redis_cache_decorator = providers.Factory(RedisCacheDecorator, cache=redis_cache, default_ttl=config.cache_ttl)

    # Multi-tier cache decorator
    multi_tier_cache_decorator = providers.Factory(
        MultiTierCacheDecorator, l1_cache=memory_cache_decorator, l2_cache=redis_cache_decorator
    )

    # Cache strategy selector
    @providers.Factory
    def cache_decorator_factory(
        strategy: str,
        memory_decorator: CacheDecoratorInterface,
        redis_decorator: CacheDecoratorInterface,
        multi_tier_decorator: CacheDecoratorInterface,
    ) -> CacheDecoratorInterface:
        strategies = {
            CacheStrategy.MEMORY_ONLY: memory_decorator,
            CacheStrategy.REDIS_ONLY: redis_decorator,
            CacheStrategy.MULTI_TIER: multi_tier_decorator,
        }
        return strategies.get(CacheStrategy(strategy), memory_decorator)

    selected_cache_decorator = providers.Factory(
        cache_decorator_factory,
        strategy=config.cache_strategy,
        memory_decorator=memory_cache_decorator,
        redis_decorator=redis_cache_decorator,
        multi_tier_decorator=multi_tier_cache_decorator,
    )

    # Services
    user_service = providers.Factory(
        UserService, cache_decorator=selected_cache_decorator, db_latency=config.db_latency.optional(0.1)
    )

    analytics_service = providers.Factory(AnalyticsService, cache_decorator=selected_cache_decorator)


# Application
class Application:
    """Main application with advanced DI configuration."""

    def __init__(self):
        self.container = ApplicationContainer()
        self._initialize_config()

    def _initialize_config(self):
        """Initialize configuration from environment."""
        config_data = self.container.config_loader()
        self.container.config.from_dict(config_data)

        print(f"🚀 Running in {config_data['environment']} mode")
        print(f"📦 Cache Strategy: {config_data['cache_strategy']}")
        print(f"⏱️  Default TTL: {config_data['cache_ttl']}s")

        if config_data["cache_strategy"] in [CacheStrategy.REDIS_ONLY, CacheStrategy.MULTI_TIER]:
            print(f"🔴 Redis: {config_data['redis']['host']}:{config_data['redis']['port']}")

    async def run_demo(self):
        """Run demonstration of advanced caching."""
        user_service = self.container.user_service()
        analytics_service = self.container.analytics_service()

        print("\n=== User Service Demo ===")

        # First call - cache miss
        user1 = await user_service.get_user(1)
        print(f"User 1: {user1}")

        # Second call - cache hit
        user1_cached = await user_service.get_user(1)
        print(f"User 1 (cached): {user1_cached}")

        # Get profile - may use cached user data
        profile1 = await user_service.get_user_profile(1)
        print(f"Profile 1: {profile1['bio']}")

        print(f"\nDB calls: {user_service.db_call_count}")

        # Update user - invalidates cache
        await user_service.update_user(1, name="Updated User")

        # Next call - cache miss due to invalidation
        user1_updated = await user_service.get_user(1)
        print(f"User 1 (after update): {user1_updated}")

        print("\n=== Analytics Service Demo ===")

        # Real-time data with short TTL
        active_users = await analytics_service.get_active_users()
        print(f"Active users: {active_users}")

        # Aggregated data with longer TTL
        daily_stats = await analytics_service.get_daily_stats("2024-01-15")
        print(f"Daily stats: Revenue ${daily_stats['revenue']}")

    async def demonstrate_cache_strategies(self):
        """Demonstrate different cache strategies."""
        strategies = [CacheStrategy.MEMORY_ONLY, CacheStrategy.REDIS_ONLY, CacheStrategy.MULTI_TIER]

        for strategy in strategies:
            print(f"\n{'=' * 50}")
            print(f"Testing {strategy.value} strategy")
            print("=" * 50)

            # Override configuration
            self.container.config.cache_strategy.override(strategy.value)

            # Reset container to apply new strategy
            self.container.reset_singletons()

            # Run demo
            await self.run_demo()


# Helper function to simulate different environments
async def run_with_environment(env: Environment):
    """Run application with specific environment."""
    os.environ["APP_ENV"] = env.value

    if env == Environment.PRODUCTION:
        # Simulate production Redis settings
        os.environ["REDIS_HOST"] = "prod-redis-cluster.example.com"
        os.environ["REDIS_PASSWORD"] = "strong-password"

    app = Application()
    await app.run_demo()


if __name__ == "__main__":
    print("=== Advanced Dependency Injection Example ===\n")

    # Run with current environment
    app = Application()
    asyncio.run(app.run_demo())

    # Demonstrate different cache strategies
    print("\n\n=== Cache Strategy Comparison ===")
    asyncio.run(app.demonstrate_cache_strategies())

    # Simulate different environments
    print("\n\n=== Environment Simulation ===")

    for env in [Environment.DEVELOPMENT, Environment.STAGING]:
        print(f"\n{'=' * 50}")
        print(f"Simulating {env.value} environment")
        print("=" * 50)
        asyncio.run(run_with_environment(env))
