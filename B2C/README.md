# Neo Market - B2C Service

B2C service of the Neo Market platform built with Django, DRF, PostgreSQL, Docker and uv.

## Tech Stack

- Python 3.14
- Django 5
- Django REST Framework
- PostgreSQL 16
- Docker / Docker Compose
- uv
- Ruff
- Pytest

---

# Project Structure

```text
B2C/
├── config/               # Django project configuration
│   ├── settings.py
│   └── test_settings.py
│
├── app/                  # ASGI / WSGI application
│
├── tests/                # Tests
│
├── manage.py
├── Dockerfile
├── Makefile
├── pyproject.toml
├── uv.lock
└── .env
```

---

# Requirements

Before starting make sure you have installed:

- Docker
- Docker Compose
- Python 3.14+
- uv

Install uv:

```bash
brew install uv
```

or

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

# Local Development

## Install dependencies

```bash
cd B2C
make install
```

---

## Run development server

```bash
make run
```

Application will be available at:

```text
http://localhost:8000
```

---

# Docker

## Start infrastructure

From repository root:

```bash
docker compose up --build
```

B2C service will be available at:

```text
http://localhost:8001
```

---

# Database

## Create migrations

```bash
cd B2C
make migrations
```

---

## Apply migrations

```bash
cd B2C
make migrate
```

---

## Create superuser

```bash
cd B2C
make superuser
```

---

# Testing

Run tests:

```bash
cd B2C
make test
```

Tests use `config.test_settings` and start a PostgreSQL 16 test container.

---

# Linting

Run linter:

```bash
cd B2C
make lint
```

Format code:

```bash
cd B2C
make format
```

---

# Useful Commands

| Command | Description |
|---|---|
| `make install` | Install dependencies |
| `make run` | Run Django server |
| `make migrations` | Create migrations |
| `make migrate` | Apply migrations |
| `make superuser` | Create admin user |
| `make shell` | Open Django shell |
| `make test` | Run tests |
| `make lint` | Run Ruff lint |
| `make format` | Format code |

---

# Environment

GitHub -> Settings -> Environments -> B2C

That's where all the secrets are.
