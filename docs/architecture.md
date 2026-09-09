# CareerMail AI — Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Flutter App                          │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │  Home   │  │Hackathons│  │Internship│  │  Settings   │  │
│  └────┬────┘  └────┬─────┘  └────┬─────┘  └──────┬──────┘  │
│       └─────────────┴─────────────┴───────────────┘         │
│                          HTTP                                │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                      FastAPI Backend                         │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ Auth API │  │Accounts  │  │ Emails   │  │Opportunities│  │
│  │          │  │   API    │  │   API    │  │    API     │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘  │
│       │              │             │               │         │
│  ┌────┴──────────────┴─────────────┴───────────────┴──────┐  │
│  │       Deadlines API     │      Daily Digest API        │  │
│  └────┬────────────────────┴───────────────────────┬──────┘  │
│       │                                            │         │
│  ┌────┴────────────────────────────────────────────┴──────┐  │
│  │                    Service Layer                        │  │
│  │  ┌────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │  │
│  │  │ Gmail  │  │ AI       │  │  Dedup   │  │ Digest  │  │  │
│  │  │Service │  │ Service  │  │  Service │  │ Service │  │  │
│  │  └────┬───┘  └────┬─────┘  └────┬─────┘  └────┬────┘  │  │
│  └───────┴───────────┴─────────────┴──────────────┴───────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐│
│  │              SQLAlchemy ORM / Database                    ││
│  │   User │ EmailAccount │ EmailMessage │ Opportunity │ ...  ││
│  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    │   SQLite    │  (dev)
                    │ PostgreSQL  │  (prod)
                    └─────────────┘
```

## Data Flow

```
Gmail Account → OAuth 2.0 → Gmail API
                                │
                          Message List (paginated)
                                │
                          Message Get (full)
                                │
                          MIME Parsing
                          ├─ text/plain
                          ├─ text/html → BeautifulSoup → text
                          └─ multipart → recursive walk
                                │
                          EmailMessage (DB)
                                │
                     Relevance Filter (keywords)
                                │
                    ┌───────────┴──────────┐
                    │ Relevant             │ Not Relevant
                    ▼                      ▼
               Gemini AI              (skip / archive)
                    │
              EmailAnalysis (Pydantic validated)
                    │
              Deduplication / Entity Resolution
                    │
              Opportunity (DB)
                    │
              Status History (DB)
                    │
              REST API → Flutter App
```

## Database Schema

### Milestone 1 Tables

```
users
├── id (PK)
├── display_name
└── created_at

email_accounts
├── id (PK)
├── user_id (FK → users)
├── provider ("gmail")
├── email_address (UNIQUE)
├── encrypted_access_token
├── encrypted_refresh_token
├── token_expiry
├── last_sync_at
├── history_id
├── is_active
├── created_at
└── updated_at

email_messages
├── id (PK)
├── account_id (FK → email_accounts)
├── gmail_message_id (UNIQUE with account_id)
├── gmail_thread_id
├── sender
├── recipients (JSON)
├── subject
├── received_at
├── body_text
├── body_html
├── labels (JSON)
├── processing_status
├── is_relevant
└── created_at
```

### Milestone 3 Tables

```
opportunities
├── id (PK)
├── user_id (FK → users, indexed)
├── category (indexed)
├── title
├── organization (indexed)
├── description
├── status (indexed)
├── round_name
├── deadline (indexed)
├── event_date
├── location
├── eligibility
├── apply_url
├── event_url
├── priority
├── confidence
├── source_account_id (FK → email_accounts)
├── first_seen_at
├── last_updated_at
├── created_at
└── updated_at

opportunity_emails (Many-to-Many Association)
├── id (PK)
├── opportunity_id (FK → opportunities, indexed)
├── email_id (FK → email_messages, indexed)
└── attached_at

opportunity_status_history
├── id (PK)
├── opportunity_id (FK → opportunities, indexed)
├── old_status
├── new_status
├── source_email_id (FK → email_messages, indexed)
└── changed_at
```

## Deduplication & Entity Resolution Strategy

Matching runs in two sequential layers:
1. **Layer 1 — Deterministic Matching:**
   - Case-folding and punctuation removal.
   - Suffix stripping on organizations (`Pvt. Ltd.`, `Inc.`, `LLC`, `Technologies`, `University`, etc.).
   - Notification and stage noise stripping on titles (`Invitation to`, `Registration Confirmed`, `Round 2`, `Campus Hiring Drive`, etc.).
   - Exact or substring match on normalized entities within the same user and category.
2. **Layer 2 — Conservative Fuzzy Matching:**
   - Triggered only if deterministic matching yields no match.
   - Guardrails:
     - **Year Guardrail:** Conflicting 4-digit years (e.g. 2026 vs 2027) will *never* merge.
     - **Role Track Guardrail:** Conflicting tracks (e.g. "Python Intern" vs "Java Intern") will *never* merge.
     - **Organization Compatibility:** Organization similarity must meet high threshold or be sub-strings.
   - Conservative similarity ratio $\ge 0.85$ on root titles.

## Status Progression & Downgrade Protection

- Statuses follow a strict progression hierarchy:
  - `opportunity` (10) $\to$ `registered` (30) $\to$ `shortlisted` (40) $\to$ `assessment` (50) $\to$ `next_round` (55) $\to$ `interview` (60) $\to$ `selected` (80) $\to$ `completed` (95) / `rejected` (100).
- Older or out-of-order emails cannot revert an already advanced status.
- Idempotent status history: Duplicate emails do not spawn duplicate history transitions.

## Milestone 4 — REST API, Deadlines & Daily Digest Architecture

### 1. Opportunity Filtering & Safe Sorting
- Multi-dimensional query filters: `category`, `status`, `priority`, `search` (case-insensitive substring on title/organization).
- Safe column-mapped sorting prevents raw SQL injection:
  - `deadline`: nulls placed last in asc/desc.
  - `priority`: custom integer weight mapping (`critical` 4, `high` 3, `medium` 2, `low` 1).
  - `created_at`, `updated_at`, `title`.
- Consistent pagination contract with `page`, `page_size`, `total_items`, `total_pages`, `has_next`, `has_previous`.

### 2. Timezone-Aware Deadline Urgency
- Uses configurable `DEFAULT_TIMEZONE` (`Asia/Kolkata`) or query param `tz` with `ZoneInfo`.
- Precise urgency classification:
  - `overdue`: $\text{deadline} < \text{now}$
  - `today`: $\text{deadline.date} == \text{now.date}$ and not overdue
  - `tomorrow`: $\text{deadline.date} == \text{tomorrow.date}$
  - `this_week`: through the upcoming Sunday
  - `later`: beyond current week
  - `no_deadline`: null deadline opportunities

### 3. Daily Digest Aggregation Pipeline
- Answers: *"What do I need to know or do today?"*
- Aggregates:
  - `new_opportunities`: strictly by `first_seen_at` within today's window.
  - `recent_status_changes`: from `OpportunityStatusHistory` where `old_status != new_status`.
  - `urgent_actions`: active items with `action_required == true`, sorted by overdue state, priority, and deadline.
  - `upcoming_deadlines`: today, tomorrow, and this week.
  - `category_updates`: count breakdown across hackathons, internships, placements, college notices.
- Deterministic text summary format: Instant generation without calling Gemini LLM.


## Milestone 6 — Push Notifications & Device Architecture

### 1. Dual-Mode FCM Client Abstraction
- **Live Mode:** Authenticated dispatch via `firebase-admin` SDK when `FIREBASE_CREDENTIALS_PATH` points to a valid service account JSON.
- **Mock / Dry-Run Mode:** Graceful simulation when credentials are absent or during CI test execution. Emits a mock message ID (`mock-msg-xxxx`), logs audit entries as `mock_sent`, and eliminates runtime crashes.
- **Token Cleanup:** Invalid/unregistered tokens detected by Firebase during dispatch are automatically marked inactive (`is_active = false`) in the database.

### 2. Concrete Event Boundaries & Decision Rules
Notifications are never fired indiscriminately on raw email ingestion. The dispatcher requires concrete events:
- `status_change`: Only triggered when `old_status != new_status` and `new_status` is in high-value set (`shortlisted`, `next_round`, `assessment`, `interview`, `selected`, `rejected`).
- `urgent_action`: Triggered when `action_required == true` and deadline urgency is high (overdue, today, tomorrow) or priority is critical/high.
- `deadline`: Triggered when deadline becomes due today or tomorrow.
- `digest`: Concise deterministic career brief reusing Milestone 4 digest.
- `test`: On-demand verification triggered via client settings.

### 3. Deduplication & 6-Hour Cooldown
- Deduplication key: `(user_id, opportunity_id, notification_type, event_detail)`.
- Prevents spamming when sync cycles process the same thread repeatedly.
- Status advancements (e.g. `shortlisted -> next_round` followed by `next_round -> interview`) have distinct dedup keys and are not erroneously suppressed.

### 4. Deep-Link Tap Routing
- Safe data payloads contain only minimal navigation metadata: `{"type": "opportunity", "opportunity_id": "42"}`.
- Never packages raw email bodies, tokens, or credentials into FCM payloads.
- Flutter `NotificationService` streams tap events directly to route users to `OpportunityDetailScreen`.


## Milestone 7 — Background Automation & Scheduling

### 1. Scheduler Technology & Lifespan Architecture
- **Engine:** APScheduler 3.x (`BackgroundScheduler`) runs daemonized background threads within the FastAPI process.
- **Lifespan Integration:** Starts during FastAPI startup and shuts down gracefully upon SIGINT/SIGTERM without leaking threads.
- **Safety Rule:** Scheduler is explicitly deactivated when `ENVIRONMENT == "test"` or `SCHEDULER_ENABLED == false`, preventing unexpected background executions during automated test runs.
- **Timezone Awareness:** Uses Python 3.9+ `zoneinfo.ZoneInfo` with `DEFAULT_TIMEZONE` (`Asia/Kolkata` by default) to ensure morning briefs run at 08:00 AM local user time regardless of server UTC time.

### 2. Centralized Pipeline Orchestration
The centralized pipeline (`run_full_sync_and_extraction_pipeline`) executes a 5-step automation loop:
1. **Account Discovery:** Queries all active connected accounts.
2. **Multi-Account Isolation:** Loops across accounts; an OAuth failure or network crash in Account 1 does not abort Account 2.
3. **Pending Email Extraction:** Invokes existing batch extraction and Gemini AI parsing.
4. **Opportunity & Status Resolution:** Resolves entities, handles status progression, and updates opportunities.
5. **Approaching Deadline Alerts:** Scans active opportunities with deadlines due today/tomorrow and triggers notifications via `NotificationDispatcher`, respecting the 6-hour deduplication window.

### 3. Concurrency Protection & Session Management
- **Threading Locks:** Reentrant locks (`_sync_lock`, `_digest_lock`) prevent multiple scheduled or manual triggers from running concurrently.
- **Fresh Database Sessions:** Background jobs never reuse request-scoped sessions. Each job acquires a dedicated `SessionLocal()` and ensures cleanup in `finally: session.close()`.

### 4. Deployment Limitation & Future Scaling
- **Single-Process Safety:** The in-process scheduler is designed for single-node / personal MVP deployments.
- **Multi-Replica Caveat:** Running multiple backend containers behind a load balancer will result in duplicate job execution unless a distributed coordinator (e.g., Celery with Redis/RabbitMQ, or leader election) is implemented. This is documented for future production hardening.


## Security Architecture

- OAuth tokens encrypted with Fernet (AES-128-CBC) at rest
- Encryption key stored in environment variable, never committed
- Tokens decrypted only when making Gmail API calls
- Automatic token refresh with re-encryption of new tokens
- Token revocation on account disconnect
- No tokens, FCM keys, or email bodies in log output
- Device registration tokens are masked in API responses (`fcm_token_snippet`)

## Provider Extensibility

The `EmailAccount.provider` field and service-layer abstraction allow future support for:
- Outlook (Microsoft Graph API)
- Yahoo Mail
- Custom IMAP providers

The AI extraction layer is provider-agnostic — it receives normalized email data regardless of source.

