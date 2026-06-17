# WhatsApp Campaigns Module Plan

## Purpose

Add a dedicated campaigns module that can send automatic WhatsApp messages through YCloud without forcing the existing CRM core to become campaign-aware. The module should stay small and practical now, while still keeping clean boundaries so later scaling features can be added without refactoring the core CRM.

## Product Goal

The first version should let an operator define a WhatsApp campaign, choose a recipient set, create or select one WhatsApp template, confirm approval, schedule or launch delivery, and track outcomes from YCloud webhooks.

This is not a general marketing automation engine yet. The initial scope should support one-off broadcast-style campaigns that send a single template, with a clear path to more advanced automation later.

## Repo Fit

The current repository is a clean-architecture CRM scaffold with:

- domain entities for customers, tags, users, and notes
- application use cases for customer and tag management
- SQLAlchemy persistence in infrastructure
- FastAPI delivery layer

That means the campaign feature should be introduced as a new bounded context, not as extra fields on customers or tags. The CRM core should only expose the data the module needs, such as customer contact details, tags, birthday, and consent state.

## Scope

### In Scope for MVP

- Create WhatsApp campaigns with name, one template, audience rule, sender number, and schedule
- Create and manage WhatsApp templates for campaign use
- Check template approval status before launch
- Build audiences from CRM tags and a few simple rules such as birthday today
- Validate recipient phone numbers and required consent before sending
- Use approved YCloud WhatsApp templates for proactive outreach
- Send messages asynchronously through YCloud for bulk delivery
- Persist outbound message records and delivery status history
- Receive and verify YCloud webhooks for message updates and inbound replies
- Track opt-outs and prevent re-sending to unsubscribed contacts
- Provide basic campaign results: queued, sent, delivered, read, failed, filtered, unsubscribed

### Out of Scope for MVP

- A/B testing
- Multi-channel orchestration beyond WhatsApp
- Advanced analytics and attribution dashboards
- Full catalog or commerce automation

## YCloud Integration Strategy

YCloud should be treated as an external messaging provider behind a narrow adapter interface.

### Required YCloud Capabilities

- API authentication via `X-API-Key`
- WhatsApp outbound sending via `POST /v2/whatsapp/messages`
- Optional direct send via `POST /v2/whatsapp/messages/sendDirectly` for debugging or special cases only
- Template creation and retrieval via the WhatsApp Templates endpoints
- Webhook endpoint configuration via the webhook endpoints API
- Webhook event handling for `whatsapp.message.updated` and `whatsapp.inbound_message.received`

### Important YCloud Constraints to Design Around

- Proactive sends must use approved templates
- Bulk sends should use the asynchronous queue-based send endpoint
- Phone numbers must be in international format with the `+` prefix and country code
- Webhook signatures must be verified using the shared secret and raw request body
- Webhook events may retry, so handlers must be idempotent
- The platform recommends quick `2xx` responses and background processing for webhook work
- `externalId` should be used to correlate outbound YCloud messages with local campaign records
- `filterUnsubscribed` and `filterBlocked` should be used when doing async bulk sends so blocked or unsubscribed users are not messaged

## Proposed Domain Model

Create a separate campaign domain model with its own entities and invariants.

### Core Entities

- Campaign
- CampaignAudience
- CampaignRecipient
- CampaignMessage
- CampaignTemplateBinding
- CampaignSchedule
- CampaignDeliveryEvent
- CampaignOptOut
- WhatsAppChannelConfiguration

### Suggested Rules

- A campaign must reference exactly one template before it can be launched
- A template can be created locally and then synced or checked against YCloud for approval
- A campaign must have a sender number tied to a YCloud-enabled WhatsApp business phone number
- Each recipient must have a valid phone number and non-empty consent state before send
- Audience selection should be limited to CRM tags and simple rules such as birthday today, city equals, or customer created in a date range
- Campaign messages must be uniquely identifiable to support idempotent retries
- Message status transitions should be monotonic and append-only in history
- Opt-out state should prevent future sends until the contact explicitly re-subscribes

## Data Model

The first pass should add dedicated tables rather than overloading the existing customer tables.

### Likely Tables

- `campaigns`
- `campaign_recipients`
- `campaign_messages`
- `campaign_message_events`
- `campaign_templates`
- `campaign_schedules`
- `campaign_channels`
- `customer_messaging_preferences` or a similar consent table

### Key Fields

- Campaign metadata: name, description, status, created_by, created_at, launched_at, canceled_at
- Audience selection: segment filters, snapshot timestamp, eligible count, skipped count
- Template binding: local template name, YCloud template name, language, category, approval status, parameter mapping
- Message tracking: local message id, YCloud message id, externalId, recipient phone, send payload hash, current status, failure reason
- Webhook tracking: event id, event type, raw payload hash, received_at, processed_at, processing_result
- Consent: opted_in_at, opted_out_at, source, reason, channel

## Application Use Cases

Create a new application module for campaigns with explicit use cases.

### Authoring and Scheduling

- CreateCampaign
- UpdateCampaign
- ScheduleCampaign
- CancelCampaign
- PreviewCampaignRecipients
- CreateCampaignTemplate
- UpdateCampaignTemplate
- SyncCampaignTemplateStatus
- ValidateCampaignTemplate

### Dispatch

- LaunchCampaign
- EnqueueCampaignBatch
- SendCampaignRecipientMessage
- RetryFailedCampaignMessage
- PauseCampaign

### Status and Reporting

- RecordCampaignSendAccepted
- RecordCampaignMessageStatus
- RecordCampaignInboundReply
- RecordCampaignOptOut
- ListCampaigns
- GetCampaignDetails
- GetCampaignMetrics

### Integration Use Cases

- HandleYCloudWebhook
- SyncYCloudTemplateCatalog
- RegisterOrUpdateYCloudWebhookEndpoint

## Infrastructure Components

The infrastructure layer should hold all provider-specific implementation details.

### YCloud Client Adapter

Implement a typed HTTP client that encapsulates:

- authentication header injection
- retry policy for transient provider failures
- timeout handling
- response parsing
- error mapping to internal exceptions

### YCloud Template Adapter

Use the template API to:

- create templates
- check approval or review status
- list approved templates
- retrieve template metadata when needed
- mirror template definitions into the local database for validation and UI selection

### YCloud Message Sender

Use the async send endpoint as the primary delivery path.

Responsibilities:

- build payloads from campaign templates and recipient parameters
- attach `externalId` for correlation
- set `filterUnsubscribed` and `filterBlocked` when applicable
- normalize provider responses into local message records

### Webhook Receiver

Add a delivery-layer webhook route that:

- captures the raw request body
- validates the `YCloud-Signature`
- checks event idempotency
- forwards the event to a use case for processing
- returns `200` quickly once the event is accepted

## Delivery Flow

### Outbound Campaign Flow

1. Operator creates a campaign and selects or creates one template
2. The system checks template approval status before launch
3. The system resolves the audience from tags and simple rules, then filters out invalid, unsubscribed, or blocked recipients
4. A send job or batch is enqueued
5. The sender adapter posts messages to YCloud asynchronously
6. YCloud returns accepted message ids
7. Webhooks update the local campaign message state over time

### Inbound Reply Flow

1. YCloud notifies the app through `whatsapp.inbound_message.received`
2. The webhook is signature-verified and deduplicated
3. The inbound message is linked to the customer and, if possible, the originating campaign
4. The system can mark opt-outs or create follow-up tasks

## API Surface

Expose a small, focused API first.

### Campaign Administration

- `GET /campaigns`
- `POST /campaigns`
- `GET /campaigns/{id}`
- `PATCH /campaigns/{id}`
- `POST /campaigns/{id}/schedule`
- `POST /campaigns/{id}/launch`
- `POST /campaigns/{id}/cancel`

### Template and Channel Admin

- `GET /campaign-templates`
- `POST /campaign-templates`
- `PATCH /campaign-templates/{id}`
- `POST /campaign-templates/{id}/sync-status`
- `POST /campaign-templates/sync`
- `GET /whatsapp-channels`
- `POST /whatsapp-channels`

### Operational Endpoints

- `POST /webhooks/ycloud`
- `GET /campaigns/{id}/metrics`
- `GET /campaigns/{id}/messages`

## UI Plan

The interface should stay simple and practical.

### Screens

- Campaign list with status, scheduled time, and delivery counts
- Campaign create/edit form
- Template create/edit form with approval status
- Template picker with validation status and language
- Audience preview with estimated recipients from tags and simple rules
- Campaign detail view with message timeline and failures
- Opt-out/consent management per contact

### UX Rules

- Show validation errors before launch, not after a failed send
- Make approval status of templates obvious
- Keep template creation and approval status visible in the campaign flow
- Show clear recipient counts for eligible, filtered, and skipped contacts
- Keep delivery states visible in real time or near-real time

## Permissions and Compliance

Campaigns need a stricter ruleset than core CRM contacts.

- Only authorized users should create or launch campaigns
- Opt-in must be stored and enforced before sends
- Unsubscribe handling should be automatic and persistent
- All outbound sends should be auditable
- Provider secrets must remain in environment variables, never in code
- Webhook signatures must be validated before any state mutation

## Reliability Plan

### Idempotency

- Use a stable local message key per recipient per campaign attempt
- Ignore duplicate webhook events using provider event ids
- Make campaign launch resumable without double-sending already accepted messages

### Retry Strategy

- Retry transient provider errors with bounded backoff
- Do not retry permanent validation errors
- Store failure reasons for operator review

### Rate and Volume Handling

- Use asynchronous delivery for bulk sends
- Chunk large recipient sets into manageable batches
- Record throttling events separately from hard failures

## Testing Plan

### Unit Tests

- campaign validation rules
- template variable mapping
- recipient filtering and consent logic
- tag and birthday-based audience rules
- webhook signature verification helper
- message state transitions

### Integration Tests

- YCloud client payload construction
- webhook ingestion with real raw-body verification shape
- repository persistence for campaigns and messages
- scheduled launch and batch processing behavior

### Contract Tests

- payloads against YCloud request shapes for template sends
- webhook event parsing for status updates and inbound replies

## Implementation Phases

### Phase 1: Domain and Persistence

- Add campaign entities, repository contracts, and SQLAlchemy models
- Add template entities, repository contracts, and SQLAlchemy models
- Add consent and opt-out persistence
- Add migration scripts for the new tables

### Phase 2: Provider Adapter

- Implement the YCloud client wrapper
- Add template sync and sender abstractions
- Add webhook signature verification and event parsing

### Phase 3: Campaign Execution

- Implement create, schedule, launch, and cancel use cases
- Implement template create, edit, and approval-check use cases
- Add batch dispatch and local message tracking
- Wire idempotent status updates from webhook events

### Phase 4: UI and Operations

- Add campaign management screens
- Add template management and approval visibility
- Add delivery metrics and failure inspection
- Add opt-out management and template selection UX

### Phase 5: Hardening

- Add retries, monitoring hooks, and audit logs
- Add rate limiting and bulk-send safeguards
- Add documentation and operational runbooks

## Recommended YCloud Defaults

- Use `POST /v2/whatsapp/messages` for campaign delivery
- Use `POST /v2/webhookEndpoints` to register the webhook endpoint
- Subscribe at minimum to `whatsapp.message.updated` and `whatsapp.inbound_message.received`
- Store the webhook secret securely and rotate it through the provider when needed
- Treat approved templates as the only supported proactive-send mechanism

## Risks

- Template approval delays can block a launch if template validation is not surfaced early
- Missing consent data can make the campaign unusable for real recipients
- Webhook duplication can create incorrect delivery counts if idempotency is weak
- Bulk delivery can fail noisily if retry logic is not separated from business validation errors
- The module can become an all-purpose marketing system if scope is not kept narrow

## Definition of Done for MVP

- A campaign can be created, scheduled, launched, and canceled
- The app can create a WhatsApp template, sync approval status, and send it to eligible recipients through YCloud
- Audience targeting works with CRM tags and simple rules such as birthday today
- Delivery status is updated from YCloud webhooks
- Opt-outs are respected consistently
- The implementation stays isolated from the core CRM modules
- Basic tests cover the provider adapter, webhook handler, and campaign state transitions

## Open Decisions

- Whether templates are only selected from YCloud or also mirrored locally
- Whether campaigns support one-time sends only in MVP or also recurring schedules
- Whether recipient selection is static snapshots or query-based segments
- Whether outbound messages are batched by a background worker or an external job queue
- Whether the UI should include campaign analytics in the first release or only status counts
