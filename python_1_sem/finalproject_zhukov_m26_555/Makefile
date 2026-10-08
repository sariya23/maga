.PHONY: install project run lint format build check

install:
	uv sync

project run:
	uv run valutatrade

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .

build:
	uv build

check: lint
