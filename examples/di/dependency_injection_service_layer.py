"""
Service Layer Integration Example with Dependency Injection

This example demonstrates a realistic application architecture:
- Repository pattern for data access
- Service layer for business logic
- Facade pattern for API simplification
- Proper separation of concerns
- Caching at appropriate layers
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from dependency_injector import containers, providers

from base_cacheable_class import BaseCacheableClass, CacheDecoratorInterface, InMemoryCache, InMemoryCacheDecorator

try:
    from base_cacheable_class import RedisCache, RedisCacheDecorator
except ImportError:
    RedisCache: type[Any] | None = None
    RedisCacheDecorator: type[Any] | None = None


# Domain Models
class User:
    def __init__(self, id: int, email: str, name: str, created_at: datetime):
        self.id = id
        self.email = email
        self.name = name
        self.created_at = created_at

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "email": self.email, "name": self.name, "created_at": self.created_at.isoformat()}


class Post:
    def __init__(self, id: int, user_id: int, title: str, content: str, created_at: datetime):
        self.id = id
        self.user_id = user_id
        self.title = title
        self.content = content
        self.created_at = created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
        }


# Repository Interfaces
class UserRepositoryInterface(ABC):
    @abstractmethod
    async def find_by_id(self, user_id: int) -> User | None:
        pass

    @abstractmethod
    async def find_by_email(self, email: str) -> User | None:
        pass

    @abstractmethod
    async def create(self, email: str, name: str) -> User:
        pass

    @abstractmethod
    async def update(self, user_id: int, **kwargs) -> User | None:
        pass


class PostRepositoryInterface(ABC):
    @abstractmethod
    async def find_by_id(self, post_id: int) -> Post | None:
        pass

    @abstractmethod
    async def find_by_user_id(self, user_id: int) -> list[Post]:
        pass

    @abstractmethod
    async def create(self, user_id: int, title: str, content: str) -> Post:
        pass


# Repository Implementations
class UserRepository(UserRepositoryInterface):
    """Simulated database repository for users."""

    def __init__(self):
        self._users: dict[int, User] = {}
        self._email_index: dict[str, int] = {}
        self._next_id = 1
        self._db_calls = 0

    async def find_by_id(self, user_id: int) -> User | None:
        self._db_calls += 1
        print(f"[DB] Finding user by ID: {user_id}")
        await asyncio.sleep(0.05)  # Simulate DB latency
        return self._users.get(user_id)

    async def find_by_email(self, email: str) -> User | None:
        self._db_calls += 1
        print(f"[DB] Finding user by email: {email}")
        await asyncio.sleep(0.05)
        user_id = self._email_index.get(email)
        return self._users.get(user_id) if user_id else None

    async def create(self, email: str, name: str) -> User:
        self._db_calls += 1
        print(f"[DB] Creating user: {email}")
        await asyncio.sleep(0.1)

        user = User(self._next_id, email, name, datetime.now())
        self._users[user.id] = user
        self._email_index[email] = user.id
        self._next_id += 1
        return user

    async def update(self, user_id: int, **kwargs) -> User | None:
        self._db_calls += 1
        print(f"[DB] Updating user: {user_id}")
        await asyncio.sleep(0.1)

        user = self._users.get(user_id)
        if user:
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
        return user

    @property
    def db_call_count(self) -> int:
        return self._db_calls


class PostRepository(PostRepositoryInterface):
    """Simulated database repository for posts."""

    def __init__(self):
        self._posts: dict[int, Post] = {}
        self._user_posts: dict[int, list[int]] = {}
        self._next_id = 1
        self._db_calls = 0

    async def find_by_id(self, post_id: int) -> Post | None:
        self._db_calls += 1
        print(f"[DB] Finding post by ID: {post_id}")
        await asyncio.sleep(0.05)
        return self._posts.get(post_id)

    async def find_by_user_id(self, user_id: int) -> list[Post]:
        self._db_calls += 1
        print(f"[DB] Finding posts by user ID: {user_id}")
        await asyncio.sleep(0.1)

        post_ids = self._user_posts.get(user_id, [])
        return [self._posts[pid] for pid in post_ids if pid in self._posts]

    async def create(self, user_id: int, title: str, content: str) -> Post:
        self._db_calls += 1
        print(f"[DB] Creating post for user: {user_id}")
        await asyncio.sleep(0.1)

        post = Post(self._next_id, user_id, title, content, datetime.now())
        self._posts[post.id] = post

        if user_id not in self._user_posts:
            self._user_posts[user_id] = []
        self._user_posts[user_id].append(post.id)

        self._next_id += 1
        return post

    @property
    def db_call_count(self) -> int:
        return self._db_calls


# Services with Caching
class UserService(BaseCacheableClass):
    """User service with caching for expensive operations."""

    def __init__(self, user_repository: UserRepositoryInterface, cache_decorator: CacheDecoratorInterface):
        super().__init__(cache_decorator)
        self.user_repository = user_repository

    @BaseCacheableClass.cache(ttl=3600)  # Cache for 1 hour
    async def get_user(self, user_id: int) -> dict[str, Any] | None:
        user = await self.user_repository.find_by_id(user_id)
        return user.to_dict() if user else None

    @BaseCacheableClass.cache(ttl=3600)
    async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        user = await self.user_repository.find_by_email(email)
        return user.to_dict() if user else None

    async def create_user(self, email: str, name: str) -> dict[str, Any]:
        user = await self.user_repository.create(email, name)
        return user.to_dict()

    @BaseCacheableClass.invalidate("get_user", param_mapping={"user_id": "user_id"})
    async def update_user(self, user_id: int, **kwargs) -> dict[str, Any] | None:
        user = await self.user_repository.update(user_id, **kwargs)
        return user.to_dict() if user else None


class PostService(BaseCacheableClass):
    """Post service with caching for post queries."""

    def __init__(self, post_repository: PostRepositoryInterface, cache_decorator: CacheDecoratorInterface):
        super().__init__(cache_decorator)
        self.post_repository = post_repository

    @BaseCacheableClass.cache(ttl=1800)  # Cache for 30 minutes
    async def get_post(self, post_id: int) -> dict[str, Any] | None:
        post = await self.post_repository.find_by_id(post_id)
        return post.to_dict() if post else None

    @BaseCacheableClass.cache(ttl=900)  # Cache for 15 minutes
    async def get_user_posts(self, user_id: int) -> list[dict[str, Any]]:
        posts = await self.post_repository.find_by_user_id(user_id)
        return [post.to_dict() for post in posts]

    @BaseCacheableClass.invalidate("get_user_posts", param_mapping={"user_id": "user_id"})
    async def create_post(self, user_id: int, title: str, content: str) -> dict[str, Any]:
        post = await self.post_repository.create(user_id, title, content)
        return post.to_dict()


# Facade for simplified API
class BlogFacade:
    """Facade that combines user and post services for blog operations."""

    def __init__(self, user_service: UserService, post_service: PostService):
        self.user_service = user_service
        self.post_service = post_service

    async def get_user_profile_with_posts(self, user_id: int) -> dict[str, Any] | None:
        """Get complete user profile including their posts."""
        # Both service calls may benefit from caching
        user_data = await self.user_service.get_user(user_id)
        if not user_data:
            return None

        posts = await self.post_service.get_user_posts(user_id)

        return {"user": user_data, "posts": posts, "post_count": len(posts)}

    async def create_blog_post(self, user_email: str, title: str, content: str) -> dict[str, Any]:
        """Create a blog post by user email."""
        # Get user by email (cached)
        user_data = await self.user_service.get_user_by_email(user_email)
        if not user_data:
            raise ValueError(f"User not found: {user_email}")

        # Create post (invalidates user posts cache)
        post = await self.post_service.create_post(user_data["id"], title, content)

        return {"post": post, "author": user_data}


# Dependency Injection Container
class ApplicationContainer(containers.DeclarativeContainer):
    """DI container for the blog application."""

    config = providers.Configuration()

    # Cache providers
    memory_cache = providers.Singleton(InMemoryCache)

    # Cache decorators
    cache_decorator = providers.Factory(
        InMemoryCacheDecorator, cache=memory_cache, default_ttl=config.cache.default_ttl
    )

    # Repositories
    user_repository = providers.Singleton(UserRepository)
    post_repository = providers.Singleton(PostRepository)

    # Services with caching
    user_service = providers.Factory(UserService, user_repository=user_repository, cache_decorator=cache_decorator)

    post_service = providers.Factory(PostService, post_repository=post_repository, cache_decorator=cache_decorator)

    # Facade
    blog_facade = providers.Factory(BlogFacade, user_service=user_service, post_service=post_service)


# Demo Application
async def run_demo():
    """Demonstrate the service layer architecture."""

    # Initialize container
    container = ApplicationContainer()
    container.config.cache.default_ttl.from_value(1800)

    # Get facade
    blog_facade = container.blog_facade()

    # Get repositories for stats
    user_repo = container.user_repository()
    post_repo = container.post_repository()

    print("=== Blog Application Demo ===\n")

    # Create users
    print("1. Creating users...")
    user_service = container.user_service()

    alice = await user_service.create_user("alice@example.com", "Alice Smith")
    bob = await user_service.create_user("bob@example.com", "Bob Jones")

    print(f"Created users: {alice['name']}, {bob['name']}")

    # Create posts
    print("\n2. Creating blog posts...")

    await blog_facade.create_blog_post(
        "alice@example.com", "Introduction to Caching", "Caching is essential for performance..."
    )

    await blog_facade.create_blog_post(
        "alice@example.com", "Advanced Caching Patterns", "Let's explore cache invalidation strategies..."
    )

    await blog_facade.create_blog_post(
        "bob@example.com", "My First Post", "Hello, world! This is my first blog post..."
    )

    print("Created 3 blog posts")

    # Test caching behavior
    print("\n3. Testing cache behavior...")

    print(f"\nDB calls before cached operations: Users={user_repo.db_call_count}, Posts={post_repo.db_call_count}")

    # These should hit cache
    profile1 = await blog_facade.get_user_profile_with_posts(alice["id"])
    await blog_facade.get_user_profile_with_posts(alice["id"])  # Second call should use cache

    print(f"DB calls after cached operations: Users={user_repo.db_call_count}, Posts={post_repo.db_call_count}")
    print(f"Alice has {profile1['post_count']} posts")

    # Update user (invalidates cache)
    print("\n4. Updating user (cache invalidation)...")
    await user_service.update_user(alice["id"], name="Alice Johnson")

    # This should hit DB due to cache invalidation
    profile3 = await blog_facade.get_user_profile_with_posts(alice["id"])
    print(f"Updated user name: {profile3['user']['name']}")
    print(f"DB calls after update: Users={user_repo.db_call_count}, Posts={post_repo.db_call_count}")

    # Performance comparison
    print("\n5. Performance comparison...")

    # Time without cache (simulate by clearing)
    import time

    # Clear caches
    cache = container.memory_cache()
    await cache.clear()

    start = time.time()
    for _ in range(5):
        await blog_facade.get_user_profile_with_posts(alice["id"])
    no_cache_time = time.time() - start

    # Time with cache (second run should use cache)
    start = time.time()
    for _ in range(5):
        await blog_facade.get_user_profile_with_posts(alice["id"])
    cache_time = time.time() - start

    print(f"Time without cache: {no_cache_time:.3f}s")
    print(f"Time with cache: {cache_time:.3f}s")
    print(f"Speedup: {no_cache_time / cache_time:.1f}x")

    print(f"\nTotal DB calls: Users={user_repo.db_call_count}, Posts={post_repo.db_call_count}")


# Advanced scenario: Multiple cache layers
async def advanced_caching_demo():
    """Demonstrate advanced caching with different TTLs per service."""

    class AdvancedContainer(ApplicationContainer):
        # Different cache decorators for different services
        user_cache_decorator = providers.Factory(
            InMemoryCacheDecorator,
            cache=ApplicationContainer.memory_cache,
            default_ttl=3600,  # 1 hour for user data
        )

        post_cache_decorator = providers.Factory(
            InMemoryCacheDecorator,
            cache=ApplicationContainer.memory_cache,
            default_ttl=300,  # 5 minutes for posts (more dynamic)
        )

        # Override services with specific cache configs
        user_service = providers.Factory(
            UserService, user_repository=ApplicationContainer.user_repository, cache_decorator=user_cache_decorator
        )

        post_service = providers.Factory(
            PostService, post_repository=ApplicationContainer.post_repository, cache_decorator=post_cache_decorator
        )

    print("\n\n=== Advanced Caching Configuration ===")
    print("User data: 1 hour TTL")
    print("Post data: 5 minutes TTL")

    container = AdvancedContainer()
    facade = container.blog_facade()

    # Create test data
    user_service = container.user_service()
    carol = await user_service.create_user("carol@example.com", "Carol Davis")

    await facade.create_blog_post("carol@example.com", "Test Post", "Content")

    # Access data
    profile = await facade.get_user_profile_with_posts(carol["id"])
    print(f"\nCarol's profile loaded with {len(profile['posts'])} posts")


if __name__ == "__main__":
    print("=== Service Layer Integration Example ===\n")

    # Run main demo
    asyncio.run(run_demo())

    # Run advanced caching demo
    asyncio.run(advanced_caching_demo())
