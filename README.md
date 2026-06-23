# Clean CRM

Simple CRM web app scaffolded with Clean Architecture boundaries.

## Stack

- Python 3.12
- FastAPI for the delivery layer
- SQLAlchemy + PostgreSQL for persistence
- Alembic for schema migrations

## Run With Docker

1. Copy [`.env.example`](.env.example) to `.env`, then fill in the values for this machine. At minimum you need:

	- `DATABASE_URL`
	- `POSTGRES_DB`
	- `POSTGRES_USER`
	- `POSTGRES_PASSWORD`
	- `CRM_JWT_SECRET`

	YCloud campaign secrets, if you use that module:

	- `YCLOUD_API_KEY`
	- `YCLOUD_WEBHOOK_SECRET`

2. Build and start the full stack:

	```bash
	docker compose up --build
	```

3. Open the app at http://localhost:8000

4. Create the first user from the CLI:

	```bash
	docker compose exec clean-crm python -m clean_crm.cli users add --username admin --email you@example.com --password 'choose-a-password'
	```

5. List and remove users from the CLI when needed:

	```bash
	docker compose exec clean-crm python -m clean_crm.cli users list
	docker compose exec clean-crm python -m clean_crm.cli users remove --username admin
	docker compose exec clean-crm python -m clean_crm.cli users remove --id 1
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

## Secrets To Add

Store these outside the repo and inject them at deploy time:

- `DATABASE_URL`
- `POSTGRES_PASSWORD`
- `CRM_JWT_SECRET`
- `YCLOUD_API_KEY` if you use WhatsApp campaigns
- `YCLOUD_WEBHOOK_SECRET` if you use WhatsApp campaigns