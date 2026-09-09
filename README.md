# CareerMail AI

Intelligent email analysis for hackathons, internships, placements, and college opportunities.

> **Email → Opportunity → Progress → Deadline → Action → Notification**

CareerMail AI connects to your Gmail accounts, identifies career-relevant emails, and converts them into structured, actionable updates using Gemini AI.

---

## Architecture

```
Gmail Account 1 ─┐
                 │
Gmail Account 2 ─┤
                 ▼
          Google OAuth 2.0
                 ▼
             Gmail API
                 ▼
          Email Ingestion
                 ▼
        Relevance Filtering
                 ▼
        Gemini AI Extraction
                 ▼
         Deduplication /
         Entity Resolution
                 ▼
           SQLite / PostgreSQL
                 ▼
          FastAPI REST API
                 ▼
            Flutter App
```

**Tech Stack:**
- **Backend:** Python, FastAPI, SQLAlchemy, Pydantic
- **Database:** SQLite (dev), PostgreSQL (prod)
- **AI:** Gemini API
- **Mobile:** Flutter, Dart, Material 3
- **Notifications:** Firebase Cloud Messaging
- **Auth:** Google OAuth 2.0

---

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.11+ | `python --version` |
| pip | any | `python -m pip --version` |
| Git | any | `git --version` |
| Flutter | 3.x+ | `flutter --version` |
| Docker | optional | `docker --version` |

---

## Google Cloud Setup (Step by Step)

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Click **Select a project** → **New Project**.
3. Name it `careermail-ai` → **Create**.
4. Select the new project from the dropdown.

### 2. Enable Gmail API

1. Go to **APIs & Services** → **Library**.
2. Search for **Gmail API**.
3. Click **Enable**.

### 3. Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**.
2. Select **External** → **Create**.
3. Fill in:
   - **App name:** `CareerMail AI`
   - **User support email:** your email
   - **Developer contact:** your email
4. Click **Save and Continue**.
5. **Scopes:** Click **Add or Remove Scopes** → search for `gmail.readonly` → check it → **Update** → **Save and Continue**.
6. **Test users:** Add your Gmail address(es) → **Save and Continue**.
7. **Summary:** Review and go back to dashboard.

> **Important:** While in "Testing" mode, only test users you add can use the app. This is fine for the MVP.

### 4. Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**.
2. Click **Create Credentials** → **OAuth client ID**.
3. **Application type:** Web application.
4. **Name:** `CareerMail AI Backend`.
5. **Authorized redirect URIs:** Add `http://localhost:8000/auth/google/callback`.
6. Click **Create**.
7. **Copy the Client ID and Client Secret** — you'll need these for `.env`.

---

## Gemini API Setup

1. Go to [Google AI Studio](https://aistudio.google.com/apikey).
2. Click **Create API Key**.
3. Copy the key — you'll need this for `.env` in Milestone 2.

---

## Backend Installation

### 1. Clone and Navigate

```bash
cd "c:\Users\mursh\PP\gmail notification"
```

### 2. Create Virtual Environment (recommended)

```bash
python -m venv backend\venv
backend\venv\Scripts\activate
```

### 3. Install Dependencies

```bash
python -m pip install -r backend\requirements.txt
```

### 4. Configure Environment

```bash
copy backend\.env.example backend\.env
```

Edit `backend\.env` and fill in:

```env
GOOGLE_CLIENT_ID=your-actual-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-actual-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
DATABASE_URL=sqlite:///./careermail.db
```

Generate an encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the output as `ENCRYPTION_KEY` in `.env`.

### 5. Start the Backend

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

### 6. Verify

- Open [http://localhost:8000/health](http://localhost:8000/health) — should show `{"status": "ok"}`.
- Open [http://localhost:8000/docs](http://localhost:8000/docs) — interactive API documentation.

---

## Connecting Gmail Account #1

1. Start the backend server.
2. Open [http://localhost:8000/auth/google/start](http://localhost:8000/auth/google/start).
3. Copy the `authorization_url` from the response.
4. Open that URL in your browser.
5. Sign in with your Gmail account.
6. Grant access to read emails.
7. You'll be redirected back — you should see "✅ Gmail Account Connected".

### Connecting Gmail Account #2

Repeat the same steps with a different Gmail account.

---

## Running First Sync

1. Check connected accounts:
   ```
   GET http://localhost:8000/accounts
   ```

2. Trigger sync (replace `{id}` with the account ID):
   ```
   POST http://localhost:8000/accounts/{id}/sync
   ```

3. View fetched emails:
   ```
   GET http://localhost:8000/emails
   ```

You can use the `/docs` Swagger UI to run these interactively.

---

## Testing

```bash
cd backend
python -m pytest tests/ -v
```

---

## API Endpoints

### Milestone 1 — Core & Accounts
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check and config status (OAuth, encryption, Gemini) |
| `GET` | `/auth/google/start` | Start Google OAuth flow |
| `GET` | `/auth/google/callback` | OAuth callback (automatic) |
| `GET` | `/accounts` | List connected accounts |
| `POST` | `/accounts/{id}/sync` | Sync emails for an account |
| `DELETE` | `/accounts/{id}` | Disconnect and delete account |
| `GET` | `/emails` | List emails (paginated, filter by status/account) |
| `GET` | `/emails/{id}` | Get email detail |

### Milestone 2 — Relevance & AI Extraction
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/extraction/process` | Batch process pending emails through filter & AI |
| `GET` | `/extraction/status` | Current count breakdown across all pipeline states |

### Milestone 3 — Opportunities & Status Tracking
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/opportunities` | List opportunities (filter by category, status, priority, search; paginated with deadline intelligence) |
| `GET` | `/opportunities/{id}` | Detailed opportunity view with all source emails and historical status transitions |

---

## Opportunity Intelligence Example

CareerMail AI guarantees entity resolution and status progression across multiple related emails:

```text
Email 1:
"XYZ Hackathon — Registration Confirmed"
        ↓
Email 2:
"XYZ Hackathon — You are shortlisted!"
        ↓
Email 3:
"XYZ Hackathon — Round 2 details and prototype submission"

        ↓ Database Result:

ONE Opportunity:
  Title: XYZ Hackathon
  Category: hackathon
  Status: next_round
  Round Name: Round 2
  Source Emails: 3 attached
  History:
    Registered → Shortlisted → Next Round
```

- **Downgrade Protection:** Older or delayed emails cannot revert advanced opportunity stages.
- **Multi-Account Dedup:** Related emails from both connected Gmail accounts resolve to the same opportunity.

---

## REST API Endpoints

See [docs/api.md](docs/api.md) for full interactive payload specifications and response schemas.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health and service configuration status |
| `GET` | `/opportunities` | List opportunities with filtering (`category`, `status`, `priority`, `search`), sorting (`sort_by`, `sort_order`), and pagination |
| `GET` | `/opportunities/{id}` | Full detail view of opportunity with attached source emails and status progression history |
| `GET` | `/deadlines` | Opportunities grouped into `overdue`, `today`, `tomorrow`, `this_week`, `later`, `no_deadline` |
| `GET` | `/digest/today` | Personalized daily briefing answering *"What do I need to know or do today?"* with deterministic text brief |
| `GET` | `/emails` | Paginated ingested emails list |
| `GET` | `/emails/{id}` | Cleaned email detail with `gmail_message_id` and `gmail_thread_id` for client-side Gmail deep linking |
| `GET` | `/accounts` | Connected Gmail accounts overview |
| `POST` | `/devices/register` | Idempotent FCM device token registration / reactivation |
| `GET` | `/devices` | List registered user devices (masked tokens) |
| `DELETE` | `/devices/{token}` | Soft-deactivate registered device token |
| `POST` | `/notifications/test` | Trigger test notification (live FCM or mock mode) |
| `GET` | `/notifications/history` | Paginated notification audit log |
| `POST` | `/extraction/process-pending` | Batch process unprocessed emails with Gemini |

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `GOOGLE_CLIENT_ID is missing` | Set `GOOGLE_CLIENT_ID` in `.env` |
| `ENCRYPTION_KEY is not configured` | Generate a Fernet key and set in `.env` |
| `redirect_uri_mismatch` | Ensure the redirect URI in `.env` matches exactly what's in Google Cloud Console |
| `access_denied` | Add your Gmail as a test user in OAuth consent screen |
| `ModuleNotFoundError` | Activate virtual environment and run `pip install -r requirements.txt` |
| `Port 8000 already in use` | Change port: `uvicorn app.main:app --port 8001` |
| `FCM mock mode active` | See [docs/firebase_setup.md](docs/firebase_setup.md) to configure real credentials |
| `Invalid DEFAULT_TIMEZONE` | Ensure `DEFAULT_TIMEZONE` is an IANA timezone (e.g., `Asia/Kolkata`, `UTC`) |
| `Scheduler disabled in test` | When `ENVIRONMENT=test` or `SCHEDULER_ENABLED=false`, scheduler is inactive |

---

## Background Automation & Scheduling (Milestone 7)

CareerMail AI features an automated loop driven by APScheduler 3.x:
- **Periodic Gmail Sync:** Runs every 15 minutes by default (`SYNC_INTERVAL_MINUTES=15`), syncing connected accounts with multi-account isolation, running relevance filtering + Gemini extraction, and scanning approaching deadlines for proactive push notifications.
- **Morning Career Brief:** Deterministically compiled every morning at 08:00 AM (`DAILY_DIGEST_HOUR=8`, `DAILY_DIGEST_MINUTE=0`) in the configured timezone (`DEFAULT_TIMEZONE=Asia/Kolkata`) and dispatched via FCM.
- **Safety & Test Protection:** Scheduler is explicitly disabled in test environments (`SCHEDULER_ENABLED=false` or `ENVIRONMENT=test`), preventing accidental background threads during test runs.
- **Concurrency Protection:** In-process threading locks and `max_instances=1`, `coalesce=True` prevent overlapping pipeline executions.
- **Production Consideration:** The in-process `BackgroundScheduler` is ideal for personal use or single-container deployments. If running multiple backend replicas behind a load balancer, a distributed coordinator or distributed job store (e.g. Redis/Celery) is recommended to prevent duplicate job execution across replicas.

---

## Security

- OAuth tokens are encrypted at rest using Fernet (AES-128-CBC).
- Tokens and device registration credentials are never exposed in API responses or public logs.
- `.env` and `firebase_credentials.json` are gitignored — secrets never enter version control.
- CORS is restricted to localhost in development.
- See [docs/security.md](docs/security.md) and [docs/firebase_setup.md](docs/firebase_setup.md) for full details.

---

## Free-Tier Limitations

| Service | Free Tier | Limitation |
|---------|-----------|------------|
| Gmail API | 1 billion quota units/day | ~250M message reads/day — effectively unlimited |
| Gemini API | Varies by model | Check [pricing](https://ai.google.dev/pricing) |
| Firebase FCM | Unlimited messages | No cost for notifications |
| SQLite | Unlimited | Single-writer, not for multi-user production |

---

## Running the Flutter Mobile App

### 1. Start the Backend API
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

### 2. Run Flutter
```bash
cd mobile

# Run on Chrome (Web)
flutter run -d chrome

# Or run on connected Android emulator
flutter run -d android
```

> **API Base URL Configuration**:
> - **Web/Desktop**: Defaults to `http://localhost:8000`
> - **Android Emulator**: Defaults to `http://10.0.2.2:8000`
> - **Physical Device**: Go to **Settings** tab in the app and set your local machine's IP (e.g. `http://192.168.1.15:8000`).

---

## Project Status

- [x] **Milestone 1:** Gmail OAuth → Email Fetching → Database
- [x] **Milestone 2:** Relevance Filtering + Gemini AI Extraction
- [x] **Milestone 3:** Opportunities + Dedup + Status History
- [x] **Milestone 4:** Full REST API + Daily Digest
- [x] **Milestone 5:** Flutter Mobile App
- [x] **Milestone 6:** FCM Notifications
- [x] **Milestone 7:** Scheduled Automation (Automatic Gmail Sync + Daily Digest + Mobile Triggers)



