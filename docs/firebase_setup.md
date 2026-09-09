# Firebase Cloud Messaging (FCM) Setup Guide

This guide details how to configure **Firebase Cloud Messaging** for push notifications in CareerMail AI.

CareerMail AI supports two operational modes:
1. **Mock / Dry-Run Mode (Default)**: Requires zero credentials, zero internet setup, and does not talk to Firebase. Safe for local development and automated CI/CD testing. All notifications are simulated and logged as `mock_sent`.
2. **Live FCM Mode**: Dispatches real, cryptographically authenticated push notifications to physical or virtual mobile devices via Google Firebase infrastructure.

---

## Architecture Overview

```text
Email Ingestion (Gmail)
          │
          ▼
 Gemini Analysis (AI)
          │
          ▼
Opportunity Manager
          │
          ▼
Concrete Event Detected
  • status_changed (high-value: shortlisted, interview, etc.)
  • urgent_action_detected (action required + urgent deadline)
  • deadline_became_urgent (deadline today/tomorrow)
  • daily_digest_ready (deterministic brief)
          │
          ▼
Notification Dispatcher
  • Cooldown Window: 6 hours (configurable via NOTIFICATION_COOLDOWN_MINUTES)
  • Deduplication Key: (user_id, opportunity_id, event_type, event_detail)
          │
          ▼
FCM Client Abstraction
  ├── If credentials configured ──► Live FCM (firebase-admin) ──► Device Notification
  └── If credentials missing    ──► Mock Dry-Run Simulation  ──► Logged as mock_sent
          │
          ▼
Mobile Tap Navigation
  └── Notification Tap ──► Flutter deep links to OpportunityDetailScreen
```

---

## Setup Steps

### 1. Create a Firebase Project
1. Navigate to the [Firebase Console](https://console.firebase.google.com/).
2. Click **Add project** (or **Create a project**).
3. Name your project `careermail-ai` (or your preferred name).
4. (Optional) Disable or enable Google Analytics according to your preference.
5. Click **Create project**.

---

### 2. Add Android Application
1. In Project Overview, click the **Android** icon (`+ Add app`).
2. Enter the Android package name: `com.example.careermail` (matches `mobile/android/app/build.gradle`).
3. Enter an app nickname, e.g., `CareerMail AI Android`.
4. (Optional) Provide the SHA-1 signing fingerprint if using Google Sign-In.
5. Click **Register app**.

---

### 3. Configure Flutter Firebase
1. Download `google-services.json` from the Firebase console.
2. Place `google-services.json` inside:
   ```text
   mobile/android/app/google-services.json
   ```
   > [!IMPORTANT]
   > Ensure `mobile/android/app/google-services.json` is not committed to public repositories. It is included in `.gitignore`.

3. Ensure `mobile/android/settings.gradle` and `mobile/android/app/build.gradle` have the Google Services plugin configured when building native APKs.

---

### 4. Obtain Backend Service-Account Credentials
1. In the Firebase Console, go to **Project Settings** (gear icon) → **Service accounts**.
2. Under **Firebase Admin SDK**, select **Python**.
3. Click **Generate new private key**, then confirm **Generate key**.
4. A JSON file will download (e.g. `careermail-ai-firebase-adminsdk-xxxxx.json`).

---

### 5. Set `FIREBASE_CREDENTIALS_PATH`
1. Move the downloaded JSON service-account file to a secure directory (e.g. inside `backend/` or a credentials folder outside source control).
2. Rename or save as `backend/firebase_credentials.json`.
3. In `backend/.env`, set:
   ```env
   FIREBASE_CREDENTIALS_PATH=./firebase_credentials.json
   FCM_ENABLED=true
   NOTIFICATION_COOLDOWN_MINUTES=360
   ```
4. Confirm file permissions:
   ```bash
   chmod 600 backend/firebase_credentials.json  # on Unix/macOS
   ```

---

### 6. Configure Android Firebase Files Safely
- Verify `.gitignore` contains:
  ```text
  firebase_credentials.json
  google-services.json
  GoogleService-Info.plist
  ```
- Never paste credentials into version control, commit messages, or issues.

---

### 7. Run the Application
1. Start the FastAPI backend:
   ```bash
   cd backend
   uvicorn app.main:app --reload --port 8000
   ```
2. Verify startup log indicates Firebase mode:
   - Live: `APP_STARTED | ... | firebase=True`
   - Mock: `APP_STARTED | ... | firebase=False`
3. Launch the Flutter mobile client:
   ```bash
   cd mobile
   flutter run
   ```

---

### 8. Register the Device
1. On the mobile client, navigate to **Settings** (bottom navigation).
2. In the **Push Notifications** card:
   - Check status: if `Not Registered`, tap **Register**.
   - The device sends `POST /devices/register` with its FCM token and platform.
   - The status updates to **Registered with Backend**.

---

### 9. Send a Test Notification
1. In mobile **Settings** → **Push Notifications**, tap **Send Test Notification**.
2. Or trigger via `curl`:
   ```bash
   curl -X POST "http://localhost:8000/notifications/test" \
        -H "Content-Type: application/json" \
        -d '{"title": "Test Push", "body": "CareerMail AI push working!"}'
   ```
3. Response:
   ```json
   {
     "success": true,
     "status": "mock_sent",
     "recipient_count": 1,
     "message_id": "mock-msg-16efb7db3ddb",
     "detail": "Notification simulated for 1 device(s) (mock/dry-run mode)"
   }
   ```

---

### 10. Verify a Real FCM Notification
1. With real credentials configured and an active Android device or emulator with Google Play Services:
   - Trigger a status change (e.g., advancing an opportunity to `interview`).
   - The notification banner appears on the device with title `Status Update: ...`.
2. Check `GET /notifications/history`:
   ```bash
   curl "http://localhost:8000/notifications/history?page=1&page_size=5"
   ```
   - Status will be `sent` with an authentic `fcm_message_id`.

---

### 11. Troubleshoot Permission & Token Issues
- **Status says "Notifications disabled"**:
  - The OS has disabled notification permissions for CareerMail. Open device **App Info** → **Notifications** → **Allow**.
- **`failed` status in history**:
  - Check backend logs: if Firebase reports `registration-token-not-registered`, the device token expired or app was reinstalled. The dispatcher automatically deactivates expired tokens.
- **Notification not delivered on sync**:
  - Check if identical event was sent within 6 hours. Cooldown blocks duplicates within `NOTIFICATION_COOLDOWN_MINUTES`.

---

### 12. Explanation of Mock / Dry-Run Mode
- In development and CI environments, Firebase credentials are absent.
- Instead of throwing an error or crashing, `FCMClient` automatically falls back to mock mode:
  - Generates a simulated message ID (`mock-msg-xxxx`).
  - Records status as `mock_sent` (never pretends to be `sent`).
  - Saves full audit trail to `notification_logs` table for verification.
  - Zero network dependencies, zero credentials needed for testing.
