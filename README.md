# Clean CRM

Simple CRM web app scaffolded with Clean Architecture boundaries.

## Stack

- Python 3.12
- FastAPI for the delivery layer
- SQLAlchemy + PostgreSQL for persistence
- Alembic for schema migrations

## Run With Docker

1. Build and start the full stack:

	```bash
	docker compose up --build
	```

2. Open the app at http://localhost:8000

3. Apply migrations manually when needed:

	```bash
	docker compose exec clean-crm python -m clean_crm.cli migrate
	```

4. Roll migrations back if needed:

	```bash
	docker compose exec clean-crm python -m clean_crm.cli downgrade base
	```

## Structure

- `src/clean_crm/domain` - entities, value objects, domain rules
- `src/clean_crm/application` - use cases and orchestration
- `src/clean_crm/interfaces` - API controllers and request/response mapping
- `src/clean_crm/infrastructure` - persistence and external services
- `src/clean_crm/main.py` - app entrypoint

## Current status

The MVP now includes live contacts, tags, tag assignment, PostgreSQL persistence, and Alembic migrations wired through Docker.