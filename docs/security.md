# CareerMail AI — Security

## Principles

1. **Email content is sensitive.** Treat it with the same care as PII.
2. **Tokens are secrets.** Never log, expose, or commit them.
3. **Defense in depth.** Multiple layers of protection.

---

## OAuth Token Security

### Encryption at Rest

All OAuth tokens (access and refresh) are encrypted using **Fernet symmetric encryption** (AES-128-CBC with HMAC-SHA256) before being stored in the database.

- **Key source:** `ENCRYPTION_KEY` environment variable.
- **Key format:** Base64-encoded 32-byte key, generated via `Fernet.generate_key()`.
- **Key rotation:** If the key changes, existing tokens become unreadable; accounts must be re-connected.

### Token Lifecycle

```
OAuth Callback
    ↓
Exchange code → access_token + refresh_token
    ↓
Encrypt both → store in DB
    ↓
Gmail API call needed
    ↓
Decrypt → use → re-encrypt if refreshed
    ↓
Account disconnect
    ↓
Revoke with Google → delete from DB
```

### What Is Never Done

- ❌ Tokens are never logged (SensitiveFilter strips them).
- ❌ Tokens are never returned in API responses.
- ❌ Tokens are never committed to version control.
- ❌ Client secrets are never in source code.

---

## Email Content Security

### Logging

- **INFO level:** Logs subject length, sender domain, message IDs — never full content.
- **DEBUG level:** May log snippets in development only; guarded by `ENVIRONMENT != production`.
- **Production:** No email bodies in any log output.

### Storage

- Email bodies are stored in the database for the extraction pipeline.
- Bodies are not exposed in list endpoints (`GET /emails` returns metadata only).
- Full body is only returned in detail endpoints (`GET /emails/{id}`).
- Future: option to purge email bodies after extraction.

---

## Opportunity & Source Email Security

- Opportunity endpoints (`GET /opportunities`, `GET /opportunities/{id}`) expose structured opportunity details, computed deadline intelligence, and source email metadata (`id`, `gmail_message_id`, `subject`, `received_at`, `sender`).
- Full email bodies, raw MIME headers, OAuth tokens, and account encryption keys are strictly omitted from Opportunity responses.
- Opportunity data is strictly scoped to the authenticated `user_id`.
- Entity resolution logic merges cross-account updates only within the same user's account pool.

---

## API Security

### CORS

- **Development:** Allows `localhost:3000` and `localhost:8080`.
- **Production:** Must be configured explicitly. Never uses `*`.

### Error Responses

- **Development:** Returns error details for debugging.
- **Production:** Returns generic "An internal error occurred." — no stack traces.

### Input Validation

- All query parameters validated via Pydantic/FastAPI.
- Path parameters validated (account_id must be int, etc.).
- Page size capped at 100.

### Rate Limiting

- Not yet implemented for MVP (single-user local tool).
- Planned for production deployment behind a reverse proxy (nginx, Cloudflare).

---

## Secret Management

### Required Secrets

| Variable | Purpose | How to Get |
|----------|---------|------------|
| `GOOGLE_CLIENT_ID` | OAuth client identification | Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | OAuth client authentication | Google Cloud Console |
| `ENCRYPTION_KEY` | Token encryption at rest | `Fernet.generate_key()` |
| `GEMINI_API_KEY` | AI extraction (Milestone 2) | Google AI Studio |

### Storage

- All secrets in `.env` file.
- `.env` is in `.gitignore`.
- `.env.example` contains placeholder values only.

---

## Threat Model (MVP Scope)

| Threat | Mitigation |
|--------|------------|
| Token theft from DB | Fernet encryption at rest |
| Token in logs | SensitiveFilter on all loggers |
| Token in API response | Pydantic schemas exclude token fields |
| Secret in source code | Environment variables only |
| CORS abuse | Restricted origins |
| SQL injection | SQLAlchemy ORM (parameterized queries) |
| XSS in OAuth callback | Minimal HTML response, no user-controlled content |
| Unauthorized account access | Single-user MVP; multi-user auth in future |

---

## Future Security Enhancements

- [ ] Multi-user authentication (OAuth2 / JWT)
- [ ] Rate limiting on all endpoints
- [ ] HTTPS enforcement
- [ ] Content Security Policy headers
- [ ] Audit logging for account actions
- [ ] Token encryption key rotation mechanism
- [ ] Email body purge after extraction
