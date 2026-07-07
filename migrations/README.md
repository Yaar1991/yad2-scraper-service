# Migrations

Alembic migration files live in `migrations/versions/`.

Common commands:

- Create migration:
  - `alembic revision -m "describe_change"`
- Apply migrations:
  - `alembic upgrade head`
