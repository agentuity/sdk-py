PHONY: build install release

install:
	@uv sync --all-extras --dev

build:
	@uv build

release:
	@uv publish
