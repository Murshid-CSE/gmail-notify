# CareerMail AI — REST API Documentation

Comprehensive API reference for the CareerMail AI backend service.

---

## 1. Overview & Conventions

### Base URL
```text
http://localhost:8000
```

### Response Conventions
All endpoints return standard JSON responses. Success responses return `200 OK` with structured payloads.

### Error Response Schema
All errors conform to FastAPI's standard schema:
```json
{
  "detail": "Human-readable error description"
}
```

Standard Status Codes:
- `200 OK`: Request succeeded.
- `400 Bad Request`: Validation failure or semantic request error.
- `404 Not Found`: Resource does not exist.
- `422 Unprocessable Entity`: Query or body parameters failed schema validation (e.g. invalid `sort_by` field, `page < 1`, `page_size > 100`).
- `500 Internal Server Error`: Unhandled server exception (sanitized in production, no stack traces leaked).

### Security & Secret Sanitization
Endpoints never expose:
- OAuth `access_token` or `refresh_token`
- Database encryption keys
- Gemini API keys
- Raw credentials or passwords

---

## 2. Opportunities API

### `GET /opportunities`
Lists opportunities with multi-attribute filtering, safe column-mapped sorting, and pagination.

#### Query Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `category` | string | `null` | Filter by category: `hackathon`, `internship`, `placement`, `college`, `general` |
| `status` | string | `null` | Filter by status: `opportunity`, `registered`, `shortlisted`, `assessment`, `next_round`, `interview`, `selected`, `completed`, `rejected` |
| `priority` | string | `null` | Filter by priority: `low`, `medium`, `high`, `critical` |
| `search` | string | `null` | Search query across `title` and `organization` (case-insensitive substring) |
| `sort_by` | string | `"updated_at"` | Sort field: `deadline`, `created_at`, `updated_at`, `priority`, `title` |
| `sort_order` | string | `"desc"` | Sort direction: `asc`, `desc` |
| `page` | integer | `1` | Page number ($\ge 1$) |
| `page_size` | integer | `20` | Page size ($1 \le \text{size} \le 100$) |

#### Response Example
```json
{
  "items": [
    {
      "id": 12,
      "category": "hackathon",
      "title": "Smart India Hackathon 2026",
      "organization": "Ministry of Education",
      "description": "National level hackathon for college students",
      "status": "shortlisted",
      "round_name": "Round 2",
      "deadline": "2026-09-12T18:30:00Z",
      "event_date": "September 20-22, 2026",
      "location": "New Delhi",
      "eligibility": "B.Tech students",
      "apply_url": "https://sih.gov.in",
      "event_url": null,
      "action_required": true,
      "action": "Submit prototype PPT and architecture diagram",
      "priority": "critical",
      "confidence": 0.95,
      "first_seen_at": "2026-09-01T10:00:00Z",
      "last_updated_at": "2026-09-08T06:30:00Z",
      "days_remaining": 4,
      "hours_remaining": 98.5,
      "is_overdue": false,
      "is_due_today": false,
      "is_due_tomorrow": false
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 1,
    "total_pages": 1,
    "has_next": false,
    "has_previous": false
  }
}
```

---

### `GET /opportunities/{id}`
Retrieves full details of an opportunity, including attached source emails and historical status transitions.

#### Response Example
```json
{
  "id": 12,
  "category": "hackathon",
  "title": "Smart India Hackathon 2026",
  "organization": "Ministry of Education",
  "description": "National level hackathon for college students",
  "status": "next_round",
  "round_name": "Round 2",
  "deadline": "2026-09-12T18:30:00Z",
  "event_date": "September 20-22, 2026",
  "location": "New Delhi",
  "eligibility": "B.Tech students",
  "apply_url": "https://sih.gov.in",
  "event_url": null,
  "action_required": true,
  "action": "Submit prototype PPT",
  "priority": "critical",
  "confidence": 0.95,
  "first_seen_at": "2026-09-01T10:00:00Z",
  "last_updated_at": "2026-09-08T06:30:00Z",
  "days_remaining": 4,
  "hours_remaining": 98.5,
  "is_overdue": false,
  "is_due_today": false,
  "is_due_tomorrow": false,
  "source_emails": [
    {
      "id": 101,
      "gmail_message_id": "189abcde12345",
      "subject": "SIH 2026 Registration Confirmation",
      "received_at": "2026-09-01T10:00:00Z",
      "sender": "no-reply@sih.gov.in"
    },
    {
      "id": 142,
      "gmail_message_id": "189bcdef67890",
      "subject": "SIH 2026: You have advanced to Round 2!",
      "received_at": "2026-09-08T06:30:00Z",
      "sender": "evaluations@sih.gov.in"
    }
  ],
  "status_history": [
    {
      "id": 1,
      "old_status": "opportunity",
      "new_status": "registered",
      "source_email_id": 101,
      "changed_at": "2026-09-01T10:00:00Z"
    },
    {
      "id": 2,
      "old_status": "registered",
      "new_status": "next_round",
      "source_email_id": 142,
      "changed_at": "2026-09-08T06:30:00Z"
    }
  ]
}
```

---

## 3. Deadlines API

### `GET /deadlines`
Groups active opportunities into urgency buckets computed in the user's timezone.

#### Query Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `category` | string | `null` | Filter by category (`hackathon`, `internship`, etc.) |
| `tz` | string | `Asia/Kolkata` (configurable) | IANA timezone name (e.g. `Asia/Kolkata`, `America/New_York`, `UTC`) |

#### Response Schema
```json
{
  "overdue": [],
  "today": [],
  "tomorrow": [],
  "this_week": [],
  "later": [],
  "no_deadline": [],
  "total_active": 4
}
```

Each item inside the groups is a mobile card object:
```json
{
  "id": 12,
  "title": "Smart India Hackathon 2026",
  "organization": "Ministry of Education",
  "category": "hackathon",
  "status": "shortlisted",
  "deadline": "2026-09-09T18:29:59+05:30",
  "priority": "critical",
  "action_required": true,
  "action": "Submit prototype PPT",
  "days_remaining": 1,
  "hours_remaining": 26.2,
  "is_overdue": false,
  "is_due_today": false,
  "is_due_tomorrow": true
}
```

#### Timezone Urgency Rules:
1. **Overdue:** `deadline < now`
2. **Today:** `deadline.date() == now.date()` and `not is_overdue`
3. **Tomorrow:** `deadline.date() == (now + 1 day).date()`
4. **This Week:** Between day after tomorrow and Sunday of the current week (or +7 days if near weekend)
5. **Later:** Beyond the current week
6. **No Deadline:** Opportunities with `deadline == null`

---

## 4. Daily Digest API

### `GET /digest/today`
Returns a personalized daily career briefing answering: *"What do I need to know or do today?"*

#### Query Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tz` | string | `Asia/Kolkata` (configurable) | Timezone for day boundary calculations |

#### Response Example
```json
{
  "generated_at": "2026-09-08T14:30:00+05:30",
  "target_date": "2026-09-08",
  "timezone": "Asia/Kolkata",
  "summary": "YOUR DAILY CAREER BRIEF\nDate: Tuesday, Sep 08, 2026\n\n⚠️  2 urgent actions needing attention\n\nACTION REQUIRED\n• Google SWE Intern: Submit coding assessment (Deadline: 1d)\n• HackNITR 5.0: Submit Round 2 prototype (Deadline: 2d)\n\nHACKATHON UPDATES\n• HackNITR 5.0 — status: Next Round (Round 2)\n\nAPPROACHING DEADLINES\n• Google SWE Intern — Google (tomorrow)\n\n✨ 1 new opportunity added today",
  "counts": {
    "new_opportunities": 1,
    "status_changes": 1,
    "urgent_actions": 2,
    "deadlines_today": 0,
    "deadlines_tomorrow": 1,
    "deadlines_this_week": 2,
    "hackathon_updates": 1,
    "internship_updates": 1,
    "placement_updates": 0,
    "college_updates": 0
  },
  "urgent_actions": [
    {
      "opportunity_id": 5,
      "title": "Google Software Engineering Intern",
      "organization": "Google",
      "category": "internship",
      "action": "Submit coding assessment",
      "priority": "critical",
      "deadline": "2026-09-09T18:00:00+05:30",
      "days_remaining": 1,
      "is_overdue": false
    }
  ],
  "recent_status_changes": [
    {
      "opportunity_id": 12,
      "title": "HackNITR 5.0",
      "organization": "NIT Rourkela",
      "category": "hackathon",
      "old_status": "shortlisted",
      "new_status": "next_round",
      "round_name": "Round 2",
      "changed_at": "2026-09-08T11:00:00+05:30"
    }
  ],
  "new_opportunities": [
    {
      "opportunity_id": 18,
      "title": "Microsoft Engage 2026",
      "organization": "Microsoft",
      "category": "internship",
      "status": "open",
      "priority": "high",
      "deadline": "2026-09-15T18:30:00+05:30",
      "first_seen_at": "2026-09-08T09:15:00+05:30"
    }
  ],
  "upcoming_deadlines": [
    {
      "opportunity_id": 5,
      "title": "Google Software Engineering Intern",
      "organization": "Google",
      "category": "internship",
      "deadline": "2026-09-09T18:00:00+05:30",
      "urgency_label": "tomorrow",
      "days_remaining": 1
    }
  ]
}
```

#### How the Daily Digest is Calculated:
1. **Window Boundaries:** The start of day (`00:00:00`) and end of day (`23:59:59.999999`) in the user's configured timezone (e.g. `Asia/Kolkata`) are computed and converted to UTC for query filtering.
2. **New Opportunities:** Counted strictly by `first_seen_at` falling within today's window. Multi-email threads updating an existing opportunity do NOT increment `new_opportunities`.
3. **Status Changes:** Retrieved from `OpportunityStatusHistory` where `changed_at` is within today's window and `old_status != new_status`.
4. **Urgent Actions:** Filtered on `action_required == true` with active status, ordered by `is_overdue`, priority weight (`critical` > `high` > `medium` > `low`), and proximity of deadline.
5. **Approaching Deadlines:** Scans active opportunities with deadlines in `today`, `tomorrow`, and `this_week`.
6. **Deterministic Human-Readable Summary:** Generated purely backend-side without calling Gemini, ensuring instant generation, zero API costs, and reliable formatting for mobile push notifications.

---

## 5. Source Email API

### `GET /emails/{id}`
Returns full email details for source inspection without exposing internal credentials or tokens.

#### Response Example
```json
{
  "id": 142,
  "gmail_message_id": "189bcdef67890",
  "gmail_thread_id": "189abcde12345",
  "account_id": 1,
  "sender": "evaluations@sih.gov.in",
  "recipients": [
    "student@college.edu"
  ],
  "subject": "SIH 2026: You have advanced to Round 2!",
  "received_at": "2026-09-08T06:30:00Z",
  "body_text": "Dear Candidate,\n\nCongratulations! Your team has passed Round 1 evaluation...",
  "labels": [
    "INBOX",
    "IMPORTANT"
  ],
  "processing_status": "extracted",
  "is_relevant": true,
  "created_at": "2026-09-08T06:35:00Z"
}
```

### Open in Gmail Support
- The API exposes `gmail_message_id` and `gmail_thread_id`.
- For the mobile app (Milestone 5), deep linking directly into Gmail on Android/iOS should use standard intent/URI schemes:
  - Web fallback: `https://mail.google.com/mail/u/0/#inbox/<gmail_thread_id>` or `https://mail.google.com/mail/u/0/#all/<gmail_message_id>`
  - Android Intent: `Intent(Intent.ACTION_VIEW)` with Gmail URI.
  - The client application falls back gracefully to opening Gmail search or inbox if exact URL routing varies by Google multi-account index (`/u/0`, `/u/1`).

---

## 6. Device Management API (Milestone 6)

### `POST /devices/register`
Idempotently registers or reactivates an FCM device registration token.

#### Request Body
```json
{
  "fcm_token": "dK4...fcm_registration_token_string",
  "device_type": "android",
  "device_name": "Pixel 8 Pro"
}
```

#### Response Example
```json
{
  "id": 1,
  "user_id": 1,
  "device_type": "android",
  "device_name": "Pixel 8 Pro",
  "is_active": true,
  "created_at": "2026-09-08T11:00:00Z",
  "last_seen_at": "2026-09-08T11:00:00Z",
  "fcm_token_snippet": "dK4...fcm_r..."
}
```

### `GET /devices`
Lists all registered devices for the current user without exposing full sensitive tokens.

### `DELETE /devices/{token}`
Soft-deactivates the token (`is_active = false`) rather than destroying audit references.

---

## 7. Push Notifications API (Milestone 6)

### `POST /notifications/test`
Dispatches an on-demand test notification to active devices. Operates in live FCM mode when credentials are configured, or safe mock/dry-run mode when absent.

#### Request Body (All Fields Optional)
```json
{
  "title": "CareerMail AI Test",
  "body": "Push notifications are working properly!",
  "opportunity_id": 42
}
```

#### Response Example
```json
{
  "success": true,
  "status": "mock_sent",
  "recipient_count": 1,
  "message_id": "mock-msg-16efb7db3ddb",
  "detail": "Notification simulated for 1 device(s) (mock/dry-run mode)"
}
```

### `GET /notifications/history`
Returns a paginated audit log of notifications generated by the system.

#### Query Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | `1` | Page number |
| `page_size` | integer | `20` | Page size ($1 \le \text{size} \le 100$) |
| `notification_type` | string | `null` | Optional type filter: `status_change`, `urgent_action`, `deadline`, `digest`, `test` |

---

## 8. Scheduler API

### `GET /scheduler/status`
Returns the operational state, active jobs, next run times, and execution metrics of the background scheduler.

#### Response Example
```json
{
  "is_running": true,
  "is_paused": false,
  "scheduler_enabled": true,
  "sync_interval_minutes": 15,
  "daily_digest_time": "08:00",
  "timezone": "Asia/Kolkata",
  "jobs": [
    {
      "id": "periodic_sync",
      "name": "Periodic Gmail Sync",
      "next_run_time": "2026-09-08T18:15:00+05:30",
      "is_paused": false,
      "trigger": "interval[0:15:00]"
    },
    {
      "id": "daily_digest",
      "name": "Daily Career Brief",
      "next_run_time": "2026-09-09T08:00:00+05:30",
      "is_paused": false,
      "trigger": "cron[hour='8', minute='0']"
    }
  ],
  "last_sync_started_at": "2026-09-08T18:00:00Z",
  "last_sync_finished_at": "2026-09-08T18:00:02Z",
  "last_sync_success": true,
  "last_sync_result": {
    "accounts_total": 2,
    "accounts_succeeded": 2,
    "accounts_failed": 0,
    "emails_ingested": 10,
    "emails_extracted": 4,
    "deadline_alerts_sent": 1,
    "duration_seconds": 2.1,
    "success": true
  },
  "last_digest_started_at": "2026-09-08T08:00:00Z",
  "last_digest_finished_at": "2026-09-08T08:00:01Z",
  "last_digest_success": true
}
```

### `POST /scheduler/trigger/sync`
Manually invokes the centralized sync and extraction pipeline with concurrency protection.

#### Response Example
```json
{
  "success": true,
  "message": "Pipeline completed: 2/2 accounts synced, 10 emails ingested, 4 extracted, 1 alerts",
  "details": {
    "accounts_total": 2,
    "accounts_succeeded": 2,
    "accounts_failed": 0,
    "emails_ingested": 10,
    "emails_extracted": 4,
    "deadline_alerts_sent": 1,
    "duration_seconds": 1.8,
    "errors": [],
    "success": true
  }
}
```

### `POST /scheduler/trigger/digest`
Manually triggers the morning daily career brief for a user.

#### Query Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | integer | `1` | Target user ID |

#### Response Example
```json
{
  "success": true,
  "message": "Daily digest triggered: status=mock_sent, notification_id=42",
  "details": {
    "user_id": 1,
    "status": "mock_sent",
    "notification_id": 42
  }
}
```

### `POST /scheduler/pause`
Pauses the background scheduler.

#### Response Example
```json
{
  "success": true,
  "message": "Background scheduler paused",
  "is_paused": true
}
```

### `POST /scheduler/resume`
Resumes the background scheduler.

#### Response Example
```json
{
  "success": true,
  "message": "Background scheduler resumed",
  "is_paused": false
}
```


