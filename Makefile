#### DATABASE ####

db:
	docker compose -f docker-compose.dev.yaml up

db-test:
	docker compose -f docker-compose.test.yaml up

psql-dev:
	docker compose -f docker-compose.dev.yaml exec db psql -U gusto_user -d gusto_db

#### ALEMBIC ####

make-migration:
	uv run alembic revision --autogenerate -m "$(msg)"

apply-migration-dev:
	uv run alembic upgrade head

apply-migration-test:
	ENV_FILE=".env.test" uv run alembic upgrade head

#### SEEDING ####

seed:
	uv run python3 -m scripts.cli.seed_db

#### TESTING ####

test:
	ENV_FILE=".env.test" uv run pytest -vs

#### DEVELOPMENT ####

dev:
	uv run fastapi dev