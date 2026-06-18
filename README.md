# Clean CRM

Simple CRM web app scaffolded with Clean Architecture boundaries.

## Stack

- Python 3.12
- FastAPI for the delivery layer
- SQLAlchemy + PostgreSQL for persistence
- Alembic for schema migrations

## Run With Docker

1. Set the required environment values in your shell or a local `.env` file. At minimum you need:

	- `DATABASE_URL`
	- `POSTGRES_DB`
	- `POSTGRES_USER`
	- `POSTGRES_PASSWORD`
	- `CRM_JWT_SECRET`

	Optional bootstrap values:

	- `CRM_ADMIN_USERNAME`
	- `CRM_ADMIN_PASSWORD`
	- `CRM_ADMIN_EMAIL`
	- `CRM_ADMIN_PASSWORD_HASH`

	YCloud campaign secrets, if you use that module:

	- `YCLOUD_API_KEY`
	- `YCLOUD_WEBHOOK_SECRET`

2. Build and start the full stack:

	```bash
	docker compose up --build
	```

3. Open the app at http://localhost:8000

4. Create a user from the CLI if you did not set bootstrap admin values:

	```bash
	docker compose exec clean-crm python -m clean_crm.cli users add --username admin --email admin@clean-crm.local --password 'choose-a-password'
	```

5. List and remove users from the CLI when needed:

	```bash
	docker compose exec clean-crm python -m clean_crm.cli users list
	docker compose exec clean-crm python -m clean_crm.cli users remove --username admin
	```

6. Apply migrations manually when needed:

	```bash
	docker compose exec clean-crm python -m clean_crm.cli migrate
	```

7. Roll migrations back if needed:

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

The MVP now includes live contacts, tags, tag assignment, PostgreSQL persistence, Alembic migrations wired through Docker, a JWT-protected login screen for the whole app, and CLI user management for adding or removing application users.