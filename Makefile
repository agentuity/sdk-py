.PHONY: build install release clean

build:
	@uv build

clean:
	@rm -rf dist
	@rm -rf agentuity.egg-info

install:
	@uv sync --all-extras --dev

release: clean build
	@uv publish
