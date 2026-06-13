# Clean CRM

Simple CRM web app scaffolded with Clean Architecture boundaries.

## Stack

- Python 3.12
- FastAPI for the delivery layer
- Uvicorn for local serving

## Structure

- `src/clean_crm/domain` - entities, value objects, domain rules
- `src/clean_crm/application` - use cases and orchestration
- `src/clean_crm/interfaces` - API controllers and request/response mapping
- `src/clean_crm/infrastructure` - persistence and external services
- `src/clean_crm/main.py` - app entrypoint

## Current status

This repo currently contains the Python architecture skeleton only. The next step is to implement the first feature slice, usually contacts.