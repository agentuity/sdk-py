PHONY: build install release clean

clean:
	@rm -rf dist
	@rm -rf agentuity.egg-info

install:
	@uv sync --all-extras --dev

build:
	@uv build

release: clean build
	@uv publish
