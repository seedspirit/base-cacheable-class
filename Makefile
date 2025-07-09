.PHONY: init format check requirements test clean build publish dev-install lint type-check

init:
	export PATH="$$HOME/.local/bin:$$PATH"
	wget -qO- https://astral.sh/uv/install.sh | sh
	uv venv
	. .venv/bin/activate
	uv sync
	uvx pyrefly init

dev-install:
	uv pip install -e ".[dev,redis]"

format:
	uvx ruff format .

check:
	uvx ruff check base_cacheable_class --fix; \
	uvx ty check base_cacheable_class; \
	uvx pyrefly check base_cacheable_class

lint:
	uvx ruff check base_cacheable_class --fix

requirements:
	uv export -o requirements.txt --without-hashes --without dev
	uv export -o requirements-dev.txt --without-hashes

test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ -v --cov=src/base_cacheable_class --cov-report=term-missing

test-watch:
	uv run pytest-watch tests/ -v

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	uv build

publish-test: build
	uvx twine upload --repository testpypi dist/*

publish: build
	uvx twine upload dist/*