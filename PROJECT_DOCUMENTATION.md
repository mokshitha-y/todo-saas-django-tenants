# 📋 TODO SaaS - Multi-Tenant Todo Application

A production-ready multi-tenant SaaS application demonstrating enterprise architecture patterns with Django, React, Keycloak, and Prefect.

---

## Table of Contents

1. [What Does This Application Do?](#1-what-does-this-application-do)
2. [Technology Stack](#2-technology-stack)
3. [How Multi-Tenancy Works](#3-how-multi-tenancy-works)
4. [Database Tables Explained](#4-database-tables-explained)
5. [Authentication & Authorization](#5-authentication--authorization)
6. [Complete User Workflows](#6-complete-user-workflows)
7. [API Reference](#7-api-reference)
8. [Background Jobs (Prefect)](#8-background-jobs-prefect)
9. [Frontend Structure](#9-frontend-structure)
10. [Project File Structure](#10-project-file-structure)
11. [Running the Application](#11-running-the-application)

---

## 1. What Does This Application Do?

This is a **multi-tenant Todo application** where:

- **Companies (tenants)** sign up and get their own isolated workspace
- **Users** within each company can create, assign, and track todos
- **Role-based permissions** control who can do what (OWNER → MEMBER → VIEWER)
- **Background jobs** handle scheduled tasks like recurring todos
- **Audit history** tracks all changes to todos

### Key Features

| Feature | Description |
|---------|-------------|
| **Organization Signup** | Create a company with isolated data |
| **Team Management** | Invite users, assign roles, remove members |
| **Todo CRUD** | Create, read, update, soft-delete todos |
| **Recurring Todos** | Daily/weekly/monthly auto-generated todos |
| **Task Assignment** | Assign todos to team members |
| **Dashboard Metrics** | View aggregated statistics |
| **Account Deletion** | Full cleanup of tenant data |

---

## 2. Technology Stack

### Backend
| Technology | Purpose |
|------------|---------|
| **Django 4.x** | REST API framework |
| **PostgreSQL 15** | Database with schema-per-tenant isolation |
| **django-tenants** | Multi-tenancy implementation |
| **django-simple-history** | Audit trail for todos |
| **Keycloak 22.x** | Identity provider (OAuth2/OIDC) |
| **Prefect 2.x** | Background job orchestration |

### Frontend
| Technology | Purpose |
|------------|---------|
| **React 18.x** | Single-page application |
| **Tailwind CSS** | Styling |
| **Axios** | HTTP client |
| **jwt-decode** | Token parsing |

### Infrastructure
| Service | Port | Purpose |
|---------|------|---------|
| Django Backend | 8000 | REST API |
| React Frontend | 3000 | Web UI |
| PostgreSQL | 5432 | Database |
| Keycloak | 8080 | Authentication |
| Prefect UI | 4200 | Job monitoring |

---

## 3. How Multi-Tenancy Works

### The Problem
How do you let multiple companies use the same application while keeping their data completely separate?

### The Solution: Schema-Per-Tenant
Each company gets its own PostgreSQL **schema** (like a separate database within the same database).

```
PostgreSQL Database: todo_saas
├── public (shared tables)
│   ├── users_user
│   ├── customers_client
│   ├── customers_tenantuser
│   └── report_dashboardmetrics
│
├── acme_corp (Acme's private schema)
│   └── todos_todo
│   └── todos_historicaltodo
│
├── globex (Globex's private schema)
│   └── todos_todo
│   └── todos_historicaltodo
```

### How It Works in Practice

1. **User logs in** → Gets a JWT token containing `tenant_schema: "acme_corp"`
2. **User requests todos** → Django middleware reads the token
3. **Middleware switches schema** → `SET search_path TO 'acme_corp'`
4. **Query executes** → Only sees Acme's todos, never Globex's

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐
│   Request    │────▶│   Decode     │────▶│   Switch to tenant   │
│   + JWT      │     │   JWT token  │     │   schema in DB       │
└──────────────┘     └──────────────┘     └──────────────────────┘
                                                    │
                                                    ▼
                                          ┌──────────────────────┐
                                          │   Query only sees    │
                                          │   tenant's data      │
                                          └──────────────────────┘
```

---

## 4. Database Tables Explained

### PUBLIC Schema Tables (Shared Across All Tenants)

#### `users_user` - Global User Accounts
Every user who signs up or is invited.

| Column | Type | Description |
|--------|------|-------------|
| `id` | int | Primary key |
| `username` | varchar | Unique username |
| `email` | varchar | Email address |
| `password` | varchar | Hashed password |
| `keycloak_id` | varchar | UUID from Keycloak |

```
Example:
┌────┬──────────┬────────────────────┬──────────────────────────────────────┐
│ id │ username │ email              │ keycloak_id                          │
├────┼──────────┼────────────────────┼──────────────────────────────────────┤
│ 1  │ aowner   │ aowner@acme.com    │ 550e8400-e29b-41d4-a716-446655440001 │
│ 2  │ amember  │ amember@acme.com   │ 550e8400-e29b-41d4-a716-446655440002 │
│ 3  │ bowner   │ bowner@globex.com  │ 550e8400-e29b-41d4-a716-446655440003 │
└────┴──────────┴────────────────────┴──────────────────────────────────────┘
```

#### `customers_client` - Tenant/Company Registry
Each row = one company with its own schema.

| Column | Type | Description |
|--------|------|-------------|
| `id` | int | Primary key |
| `name` | varchar | Company display name |
| `schema_name` | varchar | PostgreSQL schema name |
| `keycloak_id` | varchar | Keycloak group ID |
| `on_trial` | bool | Subscription status |

```
Example:
┌────┬────────────┬─────────────┬───────────────────────────────────────┐
│ id │ name       │ schema_name │ keycloak_id (group)                   │
├────┼────────────┼─────────────┼───────────────────────────────────────┤
│ 1  │ Acme Corp  │ acme        │ /acme                                 │
│ 2  │ Globex Inc │ globex      │ /globex                               │
└────┴────────────┴─────────────┴───────────────────────────────────────┘
```

#### `customers_tenantuser` - User ↔ Tenant Membership
Links users to tenants with their role. **This is the RBAC source of truth.**

| Column | Type | Description |
|--------|------|-------------|
| `id` | int | Primary key |
| `user_id` | FK → User | Which user |
| `tenant_id` | FK → Client | Which tenant |
| `role` | varchar | OWNER / MEMBER / VIEWER |

```
Example:
┌────┬─────────┬───────────┬────────┐
│ id │ user_id │ tenant_id │ role   │
├────┼─────────┼───────────┼────────┤
│ 1  │ 1       │ 1         │ OWNER  │  ← aowner is OWNER of Acme
│ 2  │ 2       │ 1         │ MEMBER │  ← amember is MEMBER of Acme
│ 3  │ 3       │ 2         │ OWNER  │  ← bowner is OWNER of Globex
│ 4  │ 1       │ 2         │ VIEWER │  ← aowner is also VIEWER at Globex!
└────┴─────────┴───────────┴────────┘
```

> **Key Insight:** One user can belong to multiple tenants with different roles!

#### `report_dashboardmetrics` - Aggregated Statistics
Pre-computed metrics for fast dashboard loading.

| Column | Type | Description |
|--------|------|-------------|
| `tenant_id` | FK → Client | Which tenant |
| `todos_new` | int | Incomplete todos count |
| `todos_completed` | int | Completed todos count |
| `total_users` | int | Team member count |
| `updated_at` | datetime | Last refresh time |

---

### TENANT Schema Tables (Isolated Per Company)

#### `todos_todo` - The Core Todo Items
Lives in each tenant's schema. Acme's todos are in `acme.todos_todo`.

| Column | Type | Description |
|--------|------|-------------|
| `id` | int | Primary key |
| `title` | varchar | Todo title |
| `description` | text | Details |
| `is_completed` | bool | Done status |
| `is_deleted` | bool | Soft delete flag |
| `due_date` | datetime | When it's due |
| `recurrence_type` | varchar | NONE/DAILY/WEEKLY/MONTHLY |
| `parent_todo_id` | FK → Todo | Original recurring todo |
| `created_by_id` | FK → User | Who created it |
| `assigned_to_id` | FK → User | Who should do it |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last modified |

```
Example (in acme schema):
┌────┬────────────────────┬──────────────┬───────────────┬──────────────┬─────────────┐
│ id │ title              │ is_completed │ created_by_id │ assigned_to  │ recurrence  │
├────┼────────────────────┼──────────────┼───────────────┼──────────────┼─────────────┤
│ 1  │ Review Q4 report   │ false        │ 1 (aowner)    │ 2 (amember)  │ NONE        │
│ 2  │ Daily standup      │ false        │ 1 (aowner)    │ NULL         │ DAILY       │
│ 3  │ Daily standup      │ true         │ 1 (aowner)    │ NULL         │ NONE        │ ← Generated instance
└────┴────────────────────┴──────────────┴───────────────┴──────────────┴─────────────┘
```

#### `todos_historicaltodo` - Audit Trail
Auto-generated by django-simple-history. Every change creates a record.

| Column | Type | Description |
|--------|------|-------------|
| `history_id` | int | Primary key |
| `id` | int | Original todo ID |
| `title` | varchar | Title at this point |
| `history_type` | char | + (create), ~ (update), - (delete) |
| `history_date` | datetime | When change happened |
| `history_user_id` | FK → User | Who made the change |

---

## 5. Authentication & Authorization

### Authentication (Who are you?) → Keycloak

Keycloak is an identity provider that handles:
- User registration
- Password storage & validation
- Token issuance (JWT)
- Session management

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   React     │────▶│  Keycloak   │────▶│   Django    │
│   Login     │     │  Validates  │     │   Trusts    │
│   Form      │     │  Password   │     │   Token     │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │
       │                   ▼
       │            ┌─────────────┐
       └───────────▶│  JWT Token  │
                    │  (contains  │
                    │  user info) │
                    └─────────────┘
```

### Authorization (What can you do?) → Django RBAC

Three roles with cascading permissions:

| Role | View Todos | Create Todos | Edit Own | Edit Any | Delete | Manage Team |
|------|------------|--------------|----------|----------|--------|-------------|
| **VIEWER** | ✅ (assigned only) | ❌ | ❌ | ❌ | ❌ | ❌ |
| **MEMBER** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **OWNER** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### How Authorization Works in Code

```python
# In todos/views.py - TodoViewSet

def get_queryset(self):
    user = self.request.user
    
    if user.role == "VIEWER":
        # VIEWERs only see todos assigned to them
        return Todo.objects.filter(assigned_to=user, is_deleted=False)
    else:
        # OWNER and MEMBER see all todos
        return Todo.objects.filter(is_deleted=False)

def perform_create(self, serializer):
    if self.request.user.role == "VIEWER":
        raise PermissionDenied("Viewers cannot create todos")
    serializer.save(created_by=self.request.user)
```

---

## 6. Complete User Workflows

### Workflow 1: Company Signup

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SIGNUP FLOW                                     │
└─────────────────────────────────────────────────────────────────────────┘

User fills form:
  - Company Name: "Acme Corp"
  - Username: "aowner"
  - Email: "aowner@acme.com"
  - Password: "secret123"

                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 1: Django receives POST /api/public/register/                      │
├─────────────────────────────────────────────────────────────────────────┤
│ a) Create Organization(name="Acme Corp")                                │
│ b) Create Client(name="Acme Corp", schema_name="acme")                  │
│    → PostgreSQL: CREATE SCHEMA acme; creates todos_todo table           │
│ c) Create User(username="aowner", email="aowner@acme.com")              │
│ d) Create TenantUser(user=aowner, tenant=acme, role="OWNER")            │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 2: Create Keycloak resources                                       │
├─────────────────────────────────────────────────────────────────────────┤
│ a) Create Keycloak user (username="aowner", email, password)            │
│ b) Create Keycloak group (name="acme")                                  │
│ c) Add user to group                                                    │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 3: Return success                                                  │
│ Response: { "message": "Organization created successfully" }            │
└─────────────────────────────────────────────────────────────────────────┘
```

### Workflow 2: User Login

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          LOGIN FLOW                                     │
└─────────────────────────────────────────────────────────────────────────┘

User enters: username="aowner", password="secret123"

                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 1: POST /api/users/login/                                          │
├─────────────────────────────────────────────────────────────────────────┤
│ Django calls Keycloak: "Validate these credentials"                     │
│                                                                         │
│ Keycloak checks:                                                        │
│   ✓ User exists                                                         │
│   ✓ Password matches                                                    │
│   ✓ User is enabled                                                     │
│                                                                         │
│ Keycloak returns: access_token + refresh_token                          │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 2: Django enriches the token                                       │
├─────────────────────────────────────────────────────────────────────────┤
│ a) Look up TenantUser for this user                                     │
│ b) Find their tenant (e.g., schema_name="acme")                         │
│ c) Find their role (e.g., role="OWNER")                                 │
│ d) Add to response: tenant_schema, role, user info                      │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 3: Frontend stores token                                           │
│                                                                         │
│ localStorage: {                                                         │
│   access_token: "eyJhbGc...",                                           │
│   tenant_schema: "acme",                                                │
│   role: "OWNER",                                                        │
│   username: "aowner"                                                    │
│ }                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Workflow 3: Inviting a Team Member

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       INVITE USER FLOW                                  │
└─────────────────────────────────────────────────────────────────────────┘

OWNER (aowner) invites: username="amember", email="amember@acme.com", role="MEMBER"

                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 1: POST /api/users/invite/                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ Check: Is request.user.role == "OWNER"?  ✓ Yes, proceed                 │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 2: Get or create Keycloak user                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ Check: Does "amember" exist in Keycloak?                                │
│                                                                         │
│ If NO:  Create new user with temp password                              │
│ If YES: Reuse existing user (they may be in another tenant too)         │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 3: Create Django records                                           │
├─────────────────────────────────────────────────────────────────────────┤
│ a) Get or create User(username="amember")                               │
│ b) Create TenantUser(user=amember, tenant=acme, role="MEMBER")          │
│ c) Add user to Keycloak group "acme"                                    │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 4: Response                                                        │
│ { "message": "User amember invited as MEMBER" }                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Workflow 4: Creating a Todo

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      CREATE TODO FLOW                                   │
└─────────────────────────────────────────────────────────────────────────┘

MEMBER (amember) creates: title="Fix bug #123"

                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 1: POST /api/todos/                                                │
│ Headers: Authorization: Bearer <JWT>                                    │
│ Body: { "title": "Fix bug #123", "description": "..." }                 │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 2: Middleware pipeline                                             │
├─────────────────────────────────────────────────────────────────────────┤
│ a) JWTAuthentication: Decode token, get user                            │
│ b) TenantMiddleware: Read tenant_schema, switch to "acme" schema        │
│ c) RBACMiddleware: Attach role="MEMBER" to request.user                 │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 3: Permission check                                                │
├─────────────────────────────────────────────────────────────────────────┤
│ user.role == "MEMBER"  →  ✓ Can create todos                            │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 4: Create record in acme.todos_todo                                │
├─────────────────────────────────────────────────────────────────────────┤
│ INSERT INTO acme.todos_todo (title, created_by_id, ...)                 │
│ VALUES ('Fix bug #123', 2, ...)                                         │
│                                                                         │
│ django-simple-history: Also inserts into acme.todos_historicaltodo      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Workflow 5: Account Deletion (OWNER Only)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ACCOUNT DELETION FLOW                                │
└─────────────────────────────────────────────────────────────────────────┘

OWNER clicks "Delete Account" → Confirms

                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 1: POST /api/customers/account/delete/                             │
│ Triggers Prefect flow: delete_account_flow                              │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 2: Prefect executes deletion tasks                                 │
├─────────────────────────────────────────────────────────────────────────┤
│ Task 1: Get all users in this tenant                                    │
│ Task 2: For each user:                                                  │
│   - Check if user belongs to OTHER tenants                              │
│   - If NO other tenants: Delete from Keycloak + Django                  │
│   - If YES other tenants: Only remove from this tenant's group          │
│ Task 3: Delete Keycloak group                                           │
│ Task 4: Delete TenantUser records                                       │
│ Task 5: Delete DashboardMetrics                                         │
│ Task 6: DROP SCHEMA acme CASCADE (deletes all todos)                    │
│ Task 7: Delete Client record                                            │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Result: Tenant completely removed from system                           │
│ Prefect UI shows: Flow run completed ✓                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. API Reference

### Public Endpoints (No Auth Required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/public/register/` | Create new organization + owner |
| POST | `/api/users/login/` | Authenticate, get JWT token |

### User Management (Auth Required)

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| POST | `/api/users/invite/` | OWNER | Invite user to tenant |
| GET | `/api/customers/users/` | OWNER | List tenant users |
| DELETE | `/api/customers/users/{id}/remove/` | OWNER | Remove user from tenant |
| PUT | `/api/customers/users/{id}/role/` | OWNER | Change user role |

### Todo Operations (Auth Required)

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| GET | `/api/todos/` | ALL | List todos (filtered by role) |
| POST | `/api/todos/` | OWNER, MEMBER | Create todo |
| GET | `/api/todos/{id}/` | ALL | Get todo details |
| PUT | `/api/todos/{id}/` | OWNER, or creator | Update todo |
| DELETE | `/api/todos/{id}/` | OWNER | Soft-delete todo |

### Dashboard & Account (Auth Required)

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| GET | `/api/customers/metrics/dashboard/` | ALL | Get dashboard metrics |
| POST | `/api/customers/orchestration/aggregate-dashboard/` | OWNER | Trigger metric refresh |
| GET | `/api/customers/account/delete-warning/` | OWNER | Get deletion impact |
| POST | `/api/customers/account/delete/` | OWNER | Delete entire account |

### Request/Response Examples

**Login Request:**
```json
POST /api/users/login/
{
  "username": "aowner",
  "password": "secret123"
}
```

**Login Response:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 300,
  "user": {
    "id": 1,
    "username": "aowner",
    "email": "aowner@acme.com"
  },
  "tenant_schema": "acme",
  "role": "OWNER"
}
```

**Create Todo:**
```json
POST /api/todos/
Authorization: Bearer <token>
{
  "title": "Review Q4 report",
  "description": "Check all figures before meeting",
  "due_date": "2026-02-15T10:00:00Z",
  "recurrence_type": "NONE",
  "assigned_to": 2
}
```

---

## 8. Background Jobs (Prefect)

Prefect handles scheduled and triggered background tasks with full visibility.

### Available Flows

| Flow | Schedule | Description |
|------|----------|-------------|
| **Dashboard Aggregation** | Every 1 hour | Refresh metrics for all tenants |
| **Recurring Todo Processing** | Daily at midnight UTC | Generate todo instances from recurring templates |
| **Account Deletion** | Manual (API trigger) | Full tenant cleanup |

### How Recurring Todos Work

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    RECURRING TODO PROCESSING                            │
└─────────────────────────────────────────────────────────────────────────┘

Daily at 00:00 UTC, Prefect runs:

1. For each tenant:
   ┌─────────────────────────────────────────────────────────────────────┐
   │ Find todos where recurrence_type != "NONE" and is_deleted = false   │
   └─────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
2. For each recurring todo:
   ┌─────────────────────────────────────────────────────────────────────┐
   │ Check if should generate today based on recurrence_type:            │
   │   DAILY:   Always generate                                          │
   │   WEEKLY:  If today matches day of week of original                 │
   │   MONTHLY: If today matches day of month of original                │
   └─────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
3. Create new todo instance:
   ┌─────────────────────────────────────────────────────────────────────┐
   │ Todo.objects.create(                                                │
   │   title = original.title,                                           │
   │   parent_todo = original,     # Links to template                   │
   │   recurrence_type = "NONE",   # Instance doesn't recur              │
   │   created_by = original.created_by,                                 │
   │   due_date = calculate_next_due_date(original)                      │
   │ )                                                                   │
   └─────────────────────────────────────────────────────────────────────┘
```

### Monitoring Jobs

Access Prefect UI at: `http://localhost:4200`

- View all flow runs
- See success/failure status
- Check logs for each task
- Manually trigger flows

---

## 9. Frontend Structure

### Pages

| Page | Path | Description |
|------|------|-------------|
| Login | `/login` | User authentication |
| Signup | `/signup` | Organization registration |
| Dashboard | `/dashboard` | Metrics overview, team management |
| Todos | `/todos` | Todo list and management |

### Key Components

```
src/
├── App.js              # Router setup
├── api/
│   ├── axios.js        # HTTP client with auth headers
│   └── tenantUsers.js  # Team management API
├── components/
│   ├── Navbar.js       # Navigation with logout
│   ├── InviteUsers.js  # Invite form (OWNER only)
│   └── TenantUsersList.js  # Team member list
└── pages/
    ├── Login.js        # Login form
    ├── Signup.js       # Registration form
    ├── Dashboard.js    # Metrics display
    └── Todos.js        # Todo CRUD + inline team management
```

### Session Validation

The frontend validates the user's Keycloak session every 5 seconds:
- If session is invalid → Auto-logout
- Prevents stale sessions from accessing data

---

## 10. Project File Structure

```
todo_saas/
├── manage.py               # Django CLI
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # PostgreSQL, Keycloak, Prefect
├── deploy_flows.py         # Register Prefect deployments
│
├── todo_saas/              # Django project settings
│   ├── settings.py         # Configuration
│   ├── urls.py             # URL routing
│   └── utils/
│       ├── auth.py         # JWT authentication
│       ├── rbac.py         # Role permission checks
│       ├── keycloak_admin.py  # Keycloak admin operations
│       └── tenant_from_token.py  # Tenant resolution
│
├── users/                  # User management app
│   ├── models.py           # User model (PUBLIC)
│   ├── views.py            # Login, register, invite
│   └── urls.py             # /api/users/
│
├── customers/              # Tenant management app
│   ├── models.py           # Client, TenantUser, Role (PUBLIC)
│   ├── views.py            # Team management
│   ├── services.py         # KeycloakService
│   ├── orchestration_views.py  # Dashboard, account deletion
│   └── urls.py             # /api/customers/
│
├── todos/                  # Todo app
│   ├── models.py           # Todo model (TENANT)
│   ├── views.py            # CRUD with RBAC
│   └── urls.py             # /api/todos/
│
├── orchestration/          # Prefect flows
│   └── flows.py            # All background jobs
│
├── report/                 # Metrics storage
│   └── models.py           # DashboardMetrics (PUBLIC)
│
└── todo-frontend/          # React application
    ├── package.json
    └── src/
        ├── App.js
        ├── api/
        ├── components/
        └── pages/
```

---

## 11. Running the Application

### Prerequisites
- Docker & Docker Compose
- Python 3.10+
- Node.js 18+

### Start Services

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Setup Python environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Run migrations
python manage.py migrate_schemas --shared

# 4. Start Django
python manage.py runserver

# 5. Deploy Prefect flows (in another terminal)
source venv/bin/activate
python deploy_flows.py

# 6. Start frontend (in another terminal)
cd todo-frontend
npm install
npm start
```

### Service URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Keycloak Admin | http://localhost:8080 (admin/admin) |
| Prefect UI | http://localhost:4200 |

### Environment Variables

Key settings in `.env`:

```bash
# Database
DB_NAME=todo_saas
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

# Keycloak
KEYCLOAK_SERVER_URL=http://localhost:8080
KEYCLOAK_REALM=todo-saas
KEYCLOAK_CLIENT_ID=todo-app
KEYCLOAK_CLIENT_SECRET=<your-secret>
KEYCLOAK_ADMIN_USER=admin
KEYCLOAK_ADMIN_PASSWORD=admin

# Prefect
PREFECT_API_URL=http://127.0.0.1:4200/api
USE_PREFECT_FLOWS=true
```

---

## Summary

This application demonstrates enterprise patterns:

1. **Multi-Tenancy**: Schema-per-tenant isolation in PostgreSQL
2. **Identity Management**: Keycloak handles authentication
3. **Authorization**: Django enforces RBAC (OWNER/MEMBER/VIEWER)
4. **Background Jobs**: Prefect orchestrates scheduled and triggered tasks
5. **Audit Trail**: django-simple-history tracks all changes
6. **Clean Architecture**: Separation of concerns across Django apps
