## Quickstart

Run postgres DB with command

``` bash
docker compose -f docker-compose.dev.yaml up
```

Start the FastAPI server with

``` bash
uv run fastapi dev
```

## Database

Access the PSQL of database with 

``` bash
docker compose -f docker-compose.dev.yaml exec -it db psql -U {POSTGRES_USER} -d {POSTGRES_DB} 
```

## Migrations

Make migration with

``` bash
uv run alembic revision --autogenerate -m "Basic users model"
```

Apply migration with

``` bash
uv run alembic upgrade head
```