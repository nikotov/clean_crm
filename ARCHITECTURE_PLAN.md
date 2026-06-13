# Clean CRM Architecture Plan

## Goal
Build a simple CRM web app with Clean Architecture in Python so the product can grow by adding modules without destabilizing the core.

## Working Principles
- Keep business rules independent from UI, database, and framework concerns.
- Model the CRM around the domain, not around screens.
- Add modules only when the core use cases justify them.
- Prefer explicit boundaries over shared utility dumping grounds.

## Initial Scope
The first version should focus on a narrow but useful CRM core:
- Contacts
- Companies
- Deals / pipeline
- Activities and reminders
- Notes
- Users and roles

## Suggested Module Boundaries
Each module should own its own use cases, entities, and persistence contracts.

- Contacts: people records, tags, lifecycle state
- Companies: organizations linked to contacts and deals
- Deals: pipeline stages, value, probability, status
- Activities: tasks, calls, meetings, reminders
- Notes: freeform notes attached to contacts, companies, or deals
- Auth and access: login, roles, permissions
- Reporting: later, built on top of existing domain data

## Architecture Layers
Use the usual Clean Architecture flow:

1. Domain
2. Application / use cases
3. Interface adapters
4. Infrastructure
5. Delivery layer / web UI

### Domain
Contains entities, value objects, invariants, and domain events. No framework or database code.

### Application
Contains use cases such as create contact, update deal stage, assign activity, and archive company.

### Interface Adapters
Contains presenters, controllers, DTO mapping, and repository interfaces.

### Infrastructure
Contains database implementations, external services, auth providers, and email integrations.

### Delivery Layer
Contains the web app routes, UI components, and form handling.

## Python Stack Direction
The current scaffold assumes:
- FastAPI for HTTP delivery
- Pydantic for request and response models
- Uvicorn as the app server
- Python packaging under `src/`

## Extension Strategy
The app should support future modules without forcing core refactors.

Recommended extension points:
- Domain events for cross-module reactions
- Feature modules with isolated use case sets
- Shared kernel only for truly universal concepts like IDs, timestamps, and pagination
- Integration adapters for things like email, imports, and exports

## MVP Direction
The first milestone should prove the architecture, not completeness.

Recommended MVP:
- Create and edit contacts
- Add notes
- Basic authentication and role separation

## Out of Scope for MVP
- Advanced analytics
- Automation rules
- Email sync
- Multi-tenant billing
- Custom object builder

## Risks To Avoid
- Starting with too many generic abstractions
- Sharing database models directly with the UI
- Allowing modules to import each other freely
- Building reporting before the core data model is stable

## Next Planning Artifacts
If this direction looks right, the next steps should be:
- Define the domain model
- Choose the frontend/backend stack
- Sketch the folder structure
- Write the first use cases and repository contracts
- Decide which modules ship in MVP