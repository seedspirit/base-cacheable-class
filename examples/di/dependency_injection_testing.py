"""
Testing Example with Mock Cache Providers using Dependency Injection

This example demonstrates:
- Creating mock cache implementations for testing
- Using DI to inject mocks into services
- Testing cache behavior without external dependencies
- Verifying cache interactions
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from dependency_injector import containers, providers

from base_cacheable_class import BaseCacheableClass, CacheDecoratorInterface, InMemoryCache, InMemoryCacheDecorator


# Mock Cache Implementation
class MockCache:
    """Mock cache for testing purposes."""

    def __init__(self):
        self.data: dict[str, Any] = {}
        self.call_history: list[dict[str, Any]] = []
        self.get_count = 0
        self.set_count = 0
        self.delete_count = 0
        self.clear_count = 0

    async def get(self, key: str) -> Any | None:
        self.get_count += 1
        self.call_history.append({"method": "get", "key": key})
        return self.data.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self.set_count += 1
        self.call_history.append({"method": "set", "key": key, "value": value, "ttl": ttl})
        self.data[key] = value

    async def delete(self, key: str) -> None:
        self.delete_count += 1
        self.call_history.append({"method": "delete", "key": key})
        self.data.pop(key, None)

    async def clear(self) -> None:
        self.clear_count += 1
        self.call_history.append({"method": "clear"})
        self.data.clear()

    async def exists(self, key: str) -> bool:
        return key in self.data

    def reset_counters(self):
        """Reset all counters for fresh test runs."""
        self.get_count = 0
        self.set_count = 0
        self.delete_count = 0
        self.clear_count = 0
        self.call_history.clear()


class MockCacheDecorator(CacheDecoratorInterface):
    """Mock cache decorator that wraps MockCache."""

    def __init__(self, cache: MockCache, default_ttl: int = 300):
        self.cache = cache
        self.default_ttl = default_ttl

    async def get(self, key: str) -> Any | None:
        return await self.cache.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        await self.cache.set(key, value, ttl or self.default_ttl)

    async def delete(self, key: str) -> None:
        await self.cache.delete(key)

    async def clear(self) -> None:
        await self.cache.clear()

    async def exists(self, key: str) -> bool:
        return await self.cache.exists(key)


# Services to test
class ProductService(BaseCacheableClass):
    """Product service with external API calls."""

    def __init__(self, cache_decorator: CacheDecoratorInterface, api_client):
        super().__init__(cache_decorator)
        self.api_client = api_client

    @BaseCacheableClass.cache(ttl=300)
    async def get_product(self, product_id: int) -> dict[str, Any]:
        return await self.api_client.fetch_product(product_id)

    @BaseCacheableClass.cache(ttl=600)
    async def get_product_reviews(self, product_id: int) -> list[dict[str, Any]]:
        return await self.api_client.fetch_reviews(product_id)

    @BaseCacheableClass.invalidate("get_product", param_mapping={"product_id": "product_id"})
    async def update_product(self, product_id: int, data: dict[str, Any]) -> dict[str, Any]:
        return await self.api_client.update_product(product_id, data)

    @BaseCacheableClass.invalidate_all()
    async def refresh_catalog(self):
        return await self.api_client.refresh_catalog()


# Test Container
class TestContainer(containers.DeclarativeContainer):
    """DI container for testing."""

    # Mock cache
    mock_cache = providers.Singleton(MockCache)

    # Mock cache decorator
    mock_cache_decorator = providers.Factory(MockCacheDecorator, cache=mock_cache, default_ttl=300)

    # Mock API client
    mock_api_client = providers.Singleton(MagicMock)

    # Service with mocks injected
    product_service = providers.Factory(
        ProductService, cache_decorator=mock_cache_decorator, api_client=mock_api_client
    )


# Test scenarios
class TestScenarios:
    """Collection of test scenarios demonstrating cache testing."""

    def __init__(self, container: TestContainer):
        self.container = container

    async def test_cache_hit_miss(self):
        """Test cache hit and miss scenarios."""
        print("=== Test: Cache Hit/Miss ===")

        # Setup
        mock_cache = self.container.mock_cache()
        mock_api = self.container.mock_api_client()
        product_service = self.container.product_service()

        # Configure mock API response
        mock_api.fetch_product = AsyncMock(return_value={"id": 123, "name": "Test Product", "price": 99.99})

        # First call - should miss cache and call API
        product1 = await product_service.get_product(123)
        print(f"First call result: {product1}")
        print(f"Cache get count: {mock_cache.get_count}")
        print(f"Cache set count: {mock_cache.set_count}")
        print(f"API calls: {mock_api.fetch_product.call_count}")

        # Second call - should hit cache
        product2 = await product_service.get_product(123)
        print(f"\nSecond call result: {product2}")
        print(f"Cache get count: {mock_cache.get_count}")
        print(f"API calls: {mock_api.fetch_product.call_count}")

        # Verify
        assert mock_cache.get_count == 2
        assert mock_cache.set_count == 1
        assert mock_api.fetch_product.call_count == 1
        assert product1 == product2

        print("\n✅ Cache hit/miss test passed!")

    async def test_cache_invalidation(self):
        """Test cache invalidation."""
        print("\n=== Test: Cache Invalidation ===")

        # Setup
        mock_cache = self.container.mock_cache()
        mock_api = self.container.mock_api_client()
        product_service = self.container.product_service()

        mock_cache.reset_counters()

        # Configure mocks
        mock_api.fetch_product = AsyncMock(
            side_effect=[
                {"id": 456, "name": "Original Product", "price": 50.00},
                {"id": 456, "name": "Updated Product", "price": 60.00},
            ]
        )
        mock_api.update_product = AsyncMock(return_value={"success": True})

        # Get product (cache miss)
        product1 = await product_service.get_product(456)
        print(f"Initial product: {product1}")

        # Update product (should invalidate cache)
        await product_service.update_product(456, {"price": 60.00})
        print(f"Delete count after update: {mock_cache.delete_count}")

        # Get product again (should miss cache due to invalidation)
        product2 = await product_service.get_product(456)
        print(f"Product after update: {product2}")

        # Verify
        assert mock_cache.delete_count == 1
        assert mock_api.fetch_product.call_count == 2
        assert product1["name"] == "Original Product"
        assert product2["name"] == "Updated Product"

        print("\n✅ Cache invalidation test passed!")

    async def test_cache_clear_all(self):
        """Test clearing all caches."""
        print("\n=== Test: Clear All Caches ===")

        # Setup
        mock_cache = self.container.mock_cache()
        mock_api = self.container.mock_api_client()
        product_service = self.container.product_service()

        mock_cache.reset_counters()

        # Configure mocks
        mock_api.fetch_product = AsyncMock(return_value={"id": 789, "name": "Product"})
        mock_api.fetch_reviews = AsyncMock(return_value=[{"rating": 5}, {"rating": 4}])
        mock_api.refresh_catalog = AsyncMock(return_value={"refreshed": True})

        # Cache some data
        await product_service.get_product(789)
        await product_service.get_product_reviews(789)

        print(f"Items in cache: {len(mock_cache.data)}")

        # Clear all caches
        await product_service.refresh_catalog()

        print(f"Items after clear: {len(mock_cache.data)}")
        print(f"Clear count: {mock_cache.clear_count}")

        # Verify
        assert len(mock_cache.data) == 0
        assert mock_cache.clear_count == 1

        print("\n✅ Clear all caches test passed!")

    async def test_cache_ttl_tracking(self):
        """Test that TTL is properly passed to cache."""
        print("\n=== Test: TTL Tracking ===")

        # Setup
        mock_cache = self.container.mock_cache()
        product_service = self.container.product_service()
        mock_api = self.container.mock_api_client()

        mock_cache.reset_counters()

        # Configure mock
        mock_api.fetch_product = AsyncMock(return_value={"id": 111})
        mock_api.fetch_reviews = AsyncMock(return_value=[])

        # Call methods with different TTLs
        await product_service.get_product(111)  # TTL: 300
        await product_service.get_product_reviews(111)  # TTL: 600

        # Check call history
        set_calls = [call for call in mock_cache.call_history if call["method"] == "set"]

        print(f"Set calls: {len(set_calls)}")
        print(f"First call TTL: {set_calls[0]['ttl']}")
        print(f"Second call TTL: {set_calls[1]['ttl']}")

        # Verify
        assert len(set_calls) == 2
        assert set_calls[0]["ttl"] == 300
        assert set_calls[1]["ttl"] == 600

        print("\n✅ TTL tracking test passed!")


# Integration test with real cache
async def integration_test():
    """Integration test using real in-memory cache."""
    print("\n=== Integration Test with Real Cache ===")

    # Container with real cache but mock API
    class IntegrationContainer(containers.DeclarativeContainer):
        # Real cache
        memory_cache = providers.Singleton(InMemoryCache)
        cache_decorator = providers.Factory(InMemoryCacheDecorator, cache=memory_cache, default_ttl=300)

        # Mock API
        mock_api_client = providers.Singleton(MagicMock)

        # Service
        product_service = providers.Factory(ProductService, cache_decorator=cache_decorator, api_client=mock_api_client)

    container = IntegrationContainer()
    api_mock = container.mock_api_client()
    service = container.product_service()

    # Configure API mock
    api_mock.fetch_product = AsyncMock(return_value={"id": 999, "name": "Integration Test Product"})

    # Test caching behavior
    result1 = await service.get_product(999)
    result2 = await service.get_product(999)

    print(f"API call count: {api_mock.fetch_product.call_count}")
    assert api_mock.fetch_product.call_count == 1
    assert result1 == result2

    print("✅ Integration test passed!")


# Helper to run all tests
async def run_all_tests():
    """Run all test scenarios."""
    container = TestContainer()
    scenarios = TestScenarios(container)

    # Run test scenarios
    await scenarios.test_cache_hit_miss()
    await scenarios.test_cache_invalidation()
    await scenarios.test_cache_clear_all()
    await scenarios.test_cache_ttl_tracking()

    # Run integration test
    await integration_test()

    print("\n🎉 All tests passed!")


# Example of using mocks in unit tests
def example_unit_test():
    """Example of how to use this in actual unit tests."""
    print("\n=== Example Unit Test Structure ===")

    example_code = '''
import pytest
from dependency_injector import containers, providers
from unittest.mock import AsyncMock

class TestProductService:
    @pytest.fixture
    def container(self):
        """Create test container with mocks."""
        container = TestContainer()
        return container

    @pytest.fixture
    def product_service(self, container):
        """Create product service with mocks."""
        return container.product_service()

    @pytest.mark.asyncio
    async def test_get_product_caches_result(self, container, product_service):
        # Arrange
        mock_api = container.mock_api_client()
        mock_cache = container.mock_cache()
        mock_api.fetch_product = AsyncMock(return_value={"id": 1, "name": "Test"})

        # Act
        result1 = await product_service.get_product(1)
        result2 = await product_service.get_product(1)

        # Assert
        assert mock_api.fetch_product.call_count == 1
        assert mock_cache.set_count == 1
        assert result1 == result2
    '''

    print(example_code)


if __name__ == "__main__":
    print("=== Dependency Injection Testing Example ===\n")

    # Run all tests
    asyncio.run(run_all_tests())

    # Show unit test example
    example_unit_test()
