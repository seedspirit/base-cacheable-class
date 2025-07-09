"""
Basic Dependency Injection Example with base-cacheable-class

This example demonstrates how to use the dependency-injector library
to manage cache dependencies and create testable, maintainable code.
"""

import asyncio

from dependency_injector import containers, providers

from base_cacheable_class import (
    BaseCacheableClass,
    InMemoryCache,
    InMemoryCacheDecorator,
    RedisCache,
    RedisCacheDecorator,
)


# Service classes
class WeatherService(BaseCacheableClass):
    """Service for fetching weather data with caching support."""

    def __init__(self, cache_decorator):
        super().__init__(cache_decorator)
        self._api_calls = 0

    @BaseCacheableClass.cache(ttl=300)  # Cache for 5 minutes
    async def get_current_weather(self, city: str) -> dict:
        self._api_calls += 1
        print(f"[API] Fetching weather for {city} (API call #{self._api_calls})")
        # Simulate API call
        await asyncio.sleep(0.1)
        return {"city": city, "temperature": 72, "condition": "Sunny", "humidity": 65}

    @BaseCacheableClass.cache(ttl=600)  # Cache for 10 minutes
    async def get_forecast(self, city: str, days: int = 5) -> list:
        self._api_calls += 1
        print(f"[API] Fetching {days}-day forecast for {city} (API call #{self._api_calls})")
        await asyncio.sleep(0.2)
        return [{"day": i, "high": 75 + i, "low": 60 + i} for i in range(1, days + 1)]

    @property
    def api_call_count(self) -> int:
        return self._api_calls


class NewsService(BaseCacheableClass):
    """Service for fetching news with caching support."""

    def __init__(self, cache_decorator):
        super().__init__(cache_decorator)

    @BaseCacheableClass.cache(ttl=60)  # Cache for 1 minute
    async def get_headlines(self, category: str = "general") -> list:
        print(f"[API] Fetching {category} headlines")
        await asyncio.sleep(0.1)
        return [{"title": f"{category.title()} News {i}", "url": f"https://news.com/{i}"} for i in range(1, 6)]

    @BaseCacheableClass.invalidate_all()
    async def refresh_all_news(self):
        print("[CACHE] Clearing all news caches")
        return "News cache cleared"


# Dependency Injection Container
class Container(containers.DeclarativeContainer):
    """DI Container for managing application dependencies."""

    # Configuration
    config = providers.Configuration()

    # Cache implementations
    memory_cache = providers.Singleton(InMemoryCache)

    redis_cache = providers.Singleton(
        RedisCache, host=config.redis.host, port=config.redis.port, password=config.redis.password, db=config.redis.db
    )

    # Cache decorators
    memory_cache_decorator = providers.Factory(
        InMemoryCacheDecorator, cache=memory_cache, default_ttl=config.cache.default_ttl
    )

    redis_cache_decorator = providers.Factory(
        RedisCacheDecorator, cache=redis_cache, default_ttl=config.cache.default_ttl
    )

    # Services with injected cache decorators
    weather_service = providers.Factory(WeatherService, cache_decorator=memory_cache_decorator)

    news_service = providers.Factory(NewsService, cache_decorator=memory_cache_decorator)


# Application class using dependency injection
class Application:
    """Main application demonstrating DI usage."""

    def __init__(self, container: Container):
        self.container = container
        self.weather_service = container.weather_service()
        self.news_service = container.news_service()

    async def run_demo(self):
        print("=== Weather Service Demo ===")

        # First call - will hit the API
        weather1 = await self.weather_service.get_current_weather("New York")
        print(f"Weather: {weather1}")

        # Second call - from cache
        weather2 = await self.weather_service.get_current_weather("New York")
        print(f"Weather (cached): {weather2}")

        # Different city - will hit the API
        weather3 = await self.weather_service.get_current_weather("London")
        print(f"Weather: {weather3}")

        print(f"\nTotal API calls: {self.weather_service.api_call_count}")

        print("\n=== News Service Demo ===")

        # Get headlines
        tech_news = await self.news_service.get_headlines("technology")
        print(f"Tech headlines: {len(tech_news)} articles")

        # From cache
        tech_news_cached = await self.news_service.get_headlines("technology")
        print(f"Tech headlines (cached): {len(tech_news_cached)} articles")

        # Clear cache
        await self.news_service.refresh_all_news()

        # Will hit API again
        tech_news_new = await self.news_service.get_headlines("technology")
        print(f"Tech headlines (after cache clear): {len(tech_news_new)} articles")


# Production configuration with Redis
async def production_demo():
    """Demo using Redis cache for production environment."""
    container = Container()
    container.config.redis.host.from_value("localhost")
    container.config.redis.port.from_value(6379)
    container.config.redis.password.from_value("")
    container.config.redis.db.from_value(0)
    container.config.cache.default_ttl.from_value(3600)

    # Override services to use Redis cache
    container.weather_service.override(
        providers.Factory(WeatherService, cache_decorator=container.redis_cache_decorator)
    )
    container.news_service.override(providers.Factory(NewsService, cache_decorator=container.redis_cache_decorator))

    print("🚀 Running with Redis Cache (Production Mode)\n")
    app = Application(container)
    await app.run_demo()


# Development configuration with in-memory cache
async def development_demo():
    """Demo using in-memory cache for development environment."""
    container = Container()
    container.config.cache.default_ttl.from_value(300)

    print("💻 Running with In-Memory Cache (Development Mode)\n")
    app = Application(container)
    await app.run_demo()


# Dynamic cache selection based on environment
async def dynamic_cache_demo():
    """Demo showing dynamic cache selection based on configuration."""
    container = Container()

    # Simulate environment-based configuration
    use_redis = False  # Change to True to use Redis

    if use_redis:
        print("🔧 Configuring Redis cache...")
        container.config.redis.host.from_value("localhost")
        container.config.redis.port.from_value(6379)
        container.config.redis.password.from_value("")
        container.config.redis.db.from_value(0)

        # Create a dynamic cache decorator provider
        cache_decorator = container.redis_cache_decorator
    else:
        print("🔧 Configuring in-memory cache...")
        cache_decorator = container.memory_cache_decorator

    container.config.cache.default_ttl.from_value(600)

    # Override services with selected cache
    container.weather_service.override(providers.Factory(WeatherService, cache_decorator=cache_decorator))
    container.news_service.override(providers.Factory(NewsService, cache_decorator=cache_decorator))

    app = Application(container)
    await app.run_demo()


if __name__ == "__main__":
    print("=== Basic Dependency Injection Example ===\n")

    # Run development demo
    asyncio.run(development_demo())

    print("\n" + "=" * 50 + "\n")

    # Run dynamic cache selection demo
    asyncio.run(dynamic_cache_demo())

    # Uncomment to run production demo (requires Redis)
    # print("\n" + "="*50 + "\n")
    # asyncio.run(production_demo())
