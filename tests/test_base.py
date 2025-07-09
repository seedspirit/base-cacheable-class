from unittest.mock import MagicMock

import pytest

from base_cacheable_class import BaseCacheableClass, CacheDecoratorInterface


class MockCacheDecorator(CacheDecoratorInterface):
    def __init__(self):
        self.call_count = 0
        self.invalidate_count = 0
        self.invalidate_all_count = 0

    def __call__(self, ttl=None):
        def decorator(func):
            async def wrapper(*args, **kwargs):
                self.call_count += 1
                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def invalidate(self, target_func_name, param_mapping=None):
        def decorator(func):
            async def wrapper(*args, **kwargs):
                self.invalidate_count += 1
                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def invalidate_all(self):
        def decorator(func):
            async def wrapper(*args, **kwargs):
                self.invalidate_all_count += 1
                return await func(*args, **kwargs)

            return wrapper

        return decorator


class TestService(BaseCacheableClass):
    def __init__(self, cache_decorator):
        super().__init__(cache_decorator)

    @BaseCacheableClass.cache(ttl=60)
    async def get_data(self, key: str):
        return f"data_{key}"

    @BaseCacheableClass.invalidate("get_data", param_mapping={"key": "key"})
    async def update_data(self, key: str, value: str):
        return f"updated_{key}_{value}"

    @BaseCacheableClass.invalidate_all()
    async def clear_all(self):
        return "cleared"


class TestBaseCacheableClass:
    def test_init(self):
        """Test BaseCacheableClass initialization"""
        mock_decorator = MockCacheDecorator()
        service = TestService(mock_decorator)
        assert service._cache_decorator == mock_decorator

    def test_wrapped(self):
        """Test wrapped method"""
        mock_decorator = MagicMock()
        mock_decorator.return_value.return_value = lambda x: x

        service = BaseCacheableClass(mock_decorator)

        def test_func():
            return "test"

        service.wrapped(test_func)
        mock_decorator.assert_called_once_with()
        mock_decorator.return_value.assert_called_once_with(test_func)

    @pytest.mark.asyncio
    async def test_cache_decorator(self):
        """Test cache decorator functionality"""
        mock_decorator = MockCacheDecorator()
        service = TestService(mock_decorator)

        result = await service.get_data("test")
        assert result == "data_test"
        assert mock_decorator.call_count == 1

    @pytest.mark.asyncio
    async def test_invalidate_decorator(self):
        """Test invalidate decorator functionality"""
        mock_decorator = MockCacheDecorator()
        service = TestService(mock_decorator)

        result = await service.update_data("test", "value")
        assert result == "updated_test_value"
        assert mock_decorator.invalidate_count == 1

    @pytest.mark.asyncio
    async def test_invalidate_all_decorator(self):
        """Test invalidate_all decorator functionality"""
        mock_decorator = MockCacheDecorator()
        service = TestService(mock_decorator)

        result = await service.clear_all()
        assert result == "cleared"
        assert mock_decorator.invalidate_all_count == 1

    @pytest.mark.asyncio
    async def test_cache_decorator_without_init(self):
        """Test cache decorator raises error when _cache_decorator not found"""

        class BadService(BaseCacheableClass):
            def __init__(self):
                # Not calling super().__init__()
                pass

            @BaseCacheableClass.cache()
            async def get_data(self):
                return "data"

        service = BadService()
        with pytest.raises(AttributeError, match="_cache_decorator not found"):
            await service.get_data()

    @pytest.mark.asyncio
    async def test_invalidate_decorator_without_init(self):
        """Test invalidate decorator raises error when _cache_decorator not found"""

        class BadService(BaseCacheableClass):
            def __init__(self):
                # Not calling super().__init__()
                pass

            @BaseCacheableClass.invalidate("some_func")
            async def update_data(self):
                return "data"

        service = BadService()
        with pytest.raises(AttributeError, match="_cache_decorator not found"):
            await service.update_data()

    @pytest.mark.asyncio
    async def test_invalidate_all_decorator_without_init(self):
        """Test invalidate_all decorator raises error when _cache_decorator not found"""

        class BadService(BaseCacheableClass):
            def __init__(self):
                # Not calling super().__init__()
                pass

            @BaseCacheableClass.invalidate_all()
            async def clear_data(self):
                return "data"

        service = BadService()
        with pytest.raises(AttributeError, match="_cache_decorator not found"):
            await service.clear_data()
