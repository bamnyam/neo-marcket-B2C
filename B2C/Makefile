.PHONY: help install run migrations migrate superuser shell test lint format docker-build

help:
	@echo "Available B2C commands:"
	@echo "  make install       - install dependencies"
	@echo "  make run           - run Django server locally"
	@echo "  make migrations    - create Django migrations"
	@echo "  make migrate       - apply Django migrations"
	@echo "  make superuser     - create Django superuser"
	@echo "  make shell         - open Django shell"
	@echo "  make test          - run tests"
	@echo "  make lint          - run ruff lint"
	@echo "  make format        - format code"
	@echo "  make docker-build  - build B2C docker image"

install:
	uv sync

run:
	uv run python manage.py runserver

migrations:
	uv run python manage.py makemigrations

migrate:
	uv run python manage.py migrate

superuser:
	uv run python manage.py createsuperuser

shell:
	uv run python manage.py shell

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

docker-build:
	docker build -t neo-market-b2c .