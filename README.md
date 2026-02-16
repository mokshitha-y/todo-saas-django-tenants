# 📝 Todo SaaS — Multi-Tenant Platform

A full-stack **multi-tenant SaaS** application built with Django, React, Keycloak, and Prefect. Each tenant gets its own isolated PostgreSQL schema, enterprise-grade identity management via Keycloak, and automated background workflows via Prefect.

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│  React SPA  │────▶│  Django API  │────▶│  PostgreSQL 15   │
│  (port 3000)│     │  (port 8000) │     │  (port 5432)     │
└─────────────┘     └──────┬───────┘     │  schema-per-     │
                           │             │  tenant isolation │
                    ┌──────▼───────┐     └──────────────────┘
                    │  Keycloak    │
                    │  (port 8080) │
                    │  OIDC / RBAC │
                    └──────────────┘
                    ┌──────────────┐
                    │  Prefect     │
                    │  (port 4200) │
                    │  Workflows   │
                    └──────────────┘
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Multi-Tenancy** | Schema-per-tenant isolation using `django-tenants` |
| **Authentication** | Keycloak OIDC — password grant, token refresh |
| **Role-Based Access** | OWNER, MEMBER, VIEWER roles per tenant |
| **Todo Management** | Full CRUD with assignment, due dates, priority |
| **Recurring Todos** | Automatic daily creation of recurring tasks |
| **User Invitation** | OWNERs invite users; Keycloak + Django sync |
| **Dashboard Metrics** | Aggregated stats across all tenants (hourly) |
| **Account Deletion** | Full cleanup — Keycloak, Django, schema drop |
| **Change Password** | Authenticated password change via Keycloak |
| **Forgot Password** | Unauthenticated reset via username + email |
| **Audit History** | Track todo changes with `django-simple-history` |
| **Prefect Orchestration** | 3 automated workflows with Prefect dashboard |

---

## 🛠️ Tech Stack

### Backend
- **Python 3.11** + **Django 4.2** + **Django REST Framework**
- **django-tenants** — PostgreSQL schema-per-tenant
- **djangorestframework-simplejwt** — JWT tokens with tenant/role claims
- **python-keycloak** — Keycloak Admin REST API client
- **Prefect 3** — Workflow orchestration
- **django-simple-history** — Model change tracking

### Frontend
- **React 18** + **React Router 6**
- **Tailwind CSS** — Utility-first styling
- **Axios** — HTTP client with JWT interceptor

### Infrastructure
- **PostgreSQL 15** — Primary database (3 DBs: app, keycloak, prefect)
- **Keycloak 26.1** — Identity & Access Management
- **Prefect Server** — Background job orchestration
- **Docker Compose** — Infrastructure orchestration

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose

### 1. Clone & Setup

```bash
git clone https://github.com/Mokshitha-original/todo_saas.git
cd todo_saas
```

### 2. Start Infrastructure

```bash
docker-compose up -d
```

This starts PostgreSQL, Keycloak, Prefect, and pgAdmin.

### 3. Backend Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 manage.py migrate
python3 manage.py runserver
```

### 4. Frontend Setup

```bash
cd todo-frontend
npm install
npm start
```

### 5. Prefect Deployments

```bash
python3 deploy_flows.py
```

---

## 🔗 Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Django API | http://localhost:8000 | — |
| React Frontend | http://localhost:3000 | — |
| Keycloak Admin | http://localhost:8080 | `admin` / `admin_password` |
| Prefect Dashboard | http://localhost:4200 | — |
| pgAdmin | http://localhost:5050 | `admin@example.com` / `admin_password` |
| PostgreSQL | localhost:5432 | `postgres` / `postgres` |

---

## 📡 API Endpoints

### Auth (`/api/auth/`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/register/` | Public | Register new tenant + owner |
| POST | `/login/` | Public | Login (Keycloak ROPC) |
| POST | `/invite/` | OWNER | Invite user to tenant |
| POST | `/change-password/` | Authenticated | Change password |
| POST | `/reset-password/` | Public | Reset password |

### Todos (`/api/todos/`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | Authenticated | List todos for tenant |
| POST | `/` | OWNER/MEMBER | Create todo |
| PATCH | `/<id>/` | OWNER/MEMBER | Update todo |
| DELETE | `/<id>/` | OWNER/MEMBER | Soft-delete todo |

### Customers (`/api/customers/`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/users/` | Authenticated | List tenant users |
| POST | `/users/<id>/remove/` | OWNER | Remove user from tenant |
| PATCH | `/users/<id>/role/` | OWNER | Update user role |
| GET | `/metrics/dashboard/` | OWNER | Get dashboard metrics |
| POST | `/orchestration/aggregate-dashboard/` | OWNER | Trigger aggregation |
| GET | `/account/delete-warning/` | OWNER | Pre-deletion summary |
| DELETE | `/account/delete/` | OWNER | Delete tenant account |

---

## ⚙️ Prefect Workflows

Three automated workflows managed via Prefect:

| Workflow | Schedule | Description |
|----------|----------|-------------|
| **Dashboard Aggregation** | Hourly | Aggregates metrics across all tenants |
| **Account Deletion** | Manual trigger | 6-step cleanup (Keycloak → Django → schema drop) |
| **Recurring Todos** | Daily (midnight UTC) | Creates new instances of recurring todos |

---

## 🗂️ Project Structure

```
todo_saas/
├── manage.py
├── requirements.txt
├── docker-compose.yml
├── deploy_flows.py              # Prefect deployment registration
├── init-db.sql/                 # PostgreSQL initialization
│
├── todo_saas/                   # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── utils/
│       ├── auth.py              # JWT authentication
│       ├── rbac.py              # Role-based permissions
│       ├── keycloak_admin.py    # Keycloak admin utilities
│       └── tenant_from_token.py # Tenant resolution middleware
│
├── users/                       # Auth & user management
│   ├── models.py                # Custom User model (keycloak_id)
│   ├── views.py                 # Register, Login, Invite, Password
│   └── urls.py
│
├── customers/                   # Tenant & org management
│   ├── models.py                # Client, TenantUser, Organization, Role
│   ├── views.py                 # User management, role updates
│   ├── services.py              # KeycloakService wrapper
│   ├── orchestration_views.py   # Dashboard metrics, account deletion
│   └── urls.py
│
├── todos/                       # Todo CRUD
│   ├── models.py                # Todo model with history tracking
│   ├── views.py                 # CRUD views
│   └── serializers.py
│
├── orchestration/               # Prefect flows
│   └── flows.py                 # All @flow and @task definitions
│
├── report/                      # Reporting models
│   └── models.py                # DashboardMetrics
│
└── todo-frontend/               # React SPA
    └── src/
        ├── App.js               # Router setup
        ├── api/axios.js         # Axios with JWT interceptor
        ├── pages/               # Login, Signup, Todos, Dashboard...
        ├── components/          # Navbar, TodoItem, TodoHistory...
        └── hooks/               # useSessionValidator
```

---

## 🔒 Multi-Tenant Model

```
Public Schema                    Tenant Schema (per org)
┌────────────────┐               ┌────────────────┐
│ users_user     │               │ todos_todo      │
│ customers_     │               │ todos_history   │
│   client       │               │ report_         │
│   tenantuser   │               │   dashboardmetr │
│   organization │               └────────────────┘
│   role         │
│   rolesmap     │
└────────────────┘
```

- **Public schema**: Users, tenants, roles, organizations (shared)
- **Tenant schema**: Todos, history, metrics (isolated per tenant)
- Each tenant's data is completely isolated at the database level

---

## 🔑 Environment Variables

Create a `.env` file in the project root:

```env
# Database
DATABASE_NAME=todo_saas_dev
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_HOST=localhost
DATABASE_PORT=5432

# Keycloak
KEYCLOAK_SERVER_URL=http://localhost:8080
KEYCLOAK_REALM=todo-saas
KEYCLOAK_ADMIN_USER=admin
KEYCLOAK_ADMIN_PASSWORD=admin_password
KEYCLOAK_CLIENT_ID=todo-backend
KEYCLOAK_CLIENT_SECRET=<your-client-secret>

# Prefect
PREFECT_API_URL=http://localhost:4200/api
```

---

## 📜 License

This project is for educational and demonstration purposes.

---

## 👤 Author

**Mokshitha Yeruva**  
GitHub: [@mokshitha-y](https://github.com/mokshitha-y)
