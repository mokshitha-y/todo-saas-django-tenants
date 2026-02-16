# Testing Checklist — Todo SaaS

Use this to verify everything works after setting up Keycloak (SMTP, Email as username, User registration Off).

---

## Prerequisites

- **Keycloak** running (e.g. http://localhost:8080) with:
  - Realm **todo-saas** (or your `KEYCLOAK_REALM`)
  - SMTP configured (Gmail App Password, port 465)
  - Realm → Login: **User registration Off**, **Email as username On**
  - Admin user has an email set (for test connection)
- **PostgreSQL** running
- **Django** `.env` has correct `KEYCLOAK_*`, `DB_*` values

---

## 1. Start services

```bash
# Terminal 1 — Backend
cd "/Users/mokshithayeruva/Downloads/todo_saas copy 3"
source venv/bin/activate   # or: venv\Scripts\activate on Windows
python3 manage.py migrate
python3 manage.py runserver
# Expect: Running at http://127.0.0.1:8000/

# Terminal 2 — Frontend
cd "/Users/mokshithayeruva/Downloads/todo_saas copy 3/todo-frontend"
npm start
# Expect: Opens http://localhost:3000
```

---

## 2. Test registration (new organisation + owner)

1. Open http://localhost:3000
2. Go to **Sign up** (or /signup)
3. Fill: **Organization name**, **Username**, **Email**, **Password**
4. Submit
5. **Pass:** You get logged in and see Dashboard with your org name and role **OWNER**

---

## 3. Test invitation flow (Keycloak email)

1. Stay logged in as **OWNER**
2. On Dashboard click **Manage Team**
3. In **Invite User**: enter an **email** (use a real inbox you can check, e.g. a second Gmail)
4. Choose role **Member** or **Viewer** → **Send Invitation**
5. **Pass:** Message like “Invitation sent to …”
6. Check the **invitee’s inbox** (and spam):
   - **Pass:** Email from Keycloak with a link to set password (e.g. “Set your password” / “Execute required actions”)
7. Click the link in the email:
   - **Pass:** Keycloak page asking for **new password** (and confirm)
8. Set password and submit:
   - **Pass:** Success or redirect to login
9. Open your app login: http://localhost:3000/login
10. Log in with **invitee’s email** (not username) and the **password they just set**
11. **Pass:** Invitee sees Dashboard and can see the organisation they were invited to

---

## 4. Test organisation switcher (personal org)

1. Log in as a **member or viewer** (the user you invited)
2. Open **Dashboard**
3. **Pass:** Organisation dropdown appears if they have more than one org (company + “My organisation”)
4. Switch to **“My organisation”** (or the personal org name)
5. **Pass:** Role shows as **OWNER** for that org
6. Click **Manage Team** → **Pass:** “Invite User” section is visible (they can invite into their personal org)

---

## 5. Test login with email (Email as username)

1. Log out
2. On login page enter **email** (not username) and password
3. **Pass:** Login succeeds and you see Dashboard

---

## 6. Quick API checks (optional)

With backend running, from another terminal:

```bash
# Health: Django admin (should 302 or 200)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin/

# Register (replace with your values)
curl -s -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"organization_name":"TestOrg","username":"testowner","email":"test@example.com","password":"TestPass123!"}'
# Expect: 201 and JSON with access/refresh tokens or 400 if user/org already exists
```

---

## 7. If something fails

| Issue | What to check |
|-------|----------------|
| Invitation “sent” but no email | Keycloak → Realm (todo-saas) → Email: SMTP test connection; check spam; Gmail App Password |
| “Invalid or expired invitation” on link | AcceptInvitation page uses `http://localhost:8000/api/` (fixed from api/v1); backend running |
| Login fails with email | Keycloak → Realm → Login: “Email as username” **On** |
| Can’t see “Invite User” as member/viewer | Switch org to “My organisation” so role is OWNER there |
| 403 on invite | You must be OWNER of the **current** org (company or personal) |

---

## 8. One-line test script (backend must be running)

From project root:

```bash
./scripts/test_api.sh
```

(See `scripts/test_api.sh` for simple GET/POST checks.)
