.PHONY: build install release clean lint format

build: lint format
	@uv build

clean:
	@rm -rf dist
	@rm -rf agentuity.egg-info

install:
	@uv sync --all-extras --dev

release: clean build
	@uv publish

lint:
	@ruff check

format:
	@ruff format
