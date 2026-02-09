"""
Django settings for todo_saas project.
"""

from pathlib import Path
from datetime import timedelta
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-i5jgyl@lkq4oeb5%q!fkpcpij&zv==&3v*q5$n%z_kds@d0vsd'

DEBUG = True

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
]

# ============================
# APPLICATIONS
# ============================

SHARED_APPS = (
    "django_tenants",
    "customers",          # tenants + tenant-user mapping
    "users",              # ✅ USERS IN PUBLIC SCHEMA
    "orchestration",      # ✅ Prefect workflow orchestration
    "report",             # ✅ Aggregated reports
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
)

TENANT_APPS = (
    "todos",              # ✅ TENANT-ISOLATED DATA ONLY
    "simple_history",
)

INSTALLED_APPS = (
    list(SHARED_APPS)
    + [app for app in TENANT_APPS if app not in SHARED_APPS]
    + [
        "rest_framework",
        "corsheaders",
        "rest_framework.authtoken",
    ]
)

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",

    "todo_saas.utils.tenant_from_token.TenantFromTokenMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ============================
# URL CONFIG
# ============================

ROOT_URLCONF = "todo_saas.urls"
PUBLIC_SCHEMA_URLCONF = "todo_saas.urls"  # same URLs for public + tenant

# ============================
# TEMPLATES
# ============================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "todo_saas.wsgi.application"

# ============================
# DATABASE (POSTGRES + TENANTS)
# ============================

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": os.getenv("DB_NAME", "todo_saas_dev"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

DATABASE_ROUTERS = (
    "django_tenants.routers.TenantSyncRouter",
)

TENANT_MODEL = "customers.Client"

# ❌ DOMAINS NOT USED ANYMORE
# TENANT_DOMAIN_MODEL = "customers.Domain"

# ============================
# AUTH
# ============================

AUTH_USER_MODEL = "users.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ============================
# DJANGO REST FRAMEWORK
# ============================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "todo_saas.utils.auth.CsrfExemptSessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# ============================
# JWT
# ============================

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ============================
# CORS
# ============================

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# ============================
# I18N / STATIC
# ============================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================
# KEYCLOAK CONFIG
# ============================

KEYCLOAK_SERVER_URL = os.environ.get("KEYCLOAK_SERVER_URL", "http://localhost:8080/")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "todo-saas")
KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "todo-backend")
KEYCLOAK_CLIENT_SECRET = os.environ.get("KEYCLOAK_CLIENT_SECRET", "Qz3Ibes8gaNQCQkehsCWsHQYHmcRHV2u")
KEYCLOAK_ADMIN_USER = os.environ.get("KEYCLOAK_ADMIN_USER", "admin")
KEYCLOAK_ADMIN_PASSWORD = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "admin")

# ============================
# PREFECT CONFIG
# ============================

# Prefect configuration is mostly handled via environment variables
# but we can add constants here if needed for flow logic.
PREFECT_API_URL = os.environ.get("PREFECT_API_URL", "http://127.0.0.1:4200/api")

# ============================
# LOGGING CONFIG
# ============================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name} {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "level": "INFO",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "todo_saas.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
            "level": "INFO",
        },
        "audit_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "audit_trail.log"),
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
            "level": "INFO",
        },
        "keycloak_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "keycloak.log"),
            "maxBytes": 1024 * 1024 * 5,
            "backupCount": 3,
            "formatter": "verbose",
            "level": "DEBUG",
        },
        "prefect_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "prefect.log"),
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
            "level": "INFO",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "todos.models": {
            "handlers": ["console", "audit_file"],
            "level": "INFO",
            "propagate": False,
        },
        "customers.services": {
            "handlers": ["console", "keycloak_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "todo_saas.utils.keycloak_admin": {
            "handlers": ["console", "keycloak_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "todo_saas.utils.audit": {
            "handlers": ["console", "audit_file"],
            "level": "INFO",
            "propagate": False,
        },
        "todo_saas.utils.rbac": {
            "handlers": ["console", "audit_file"],
            "level": "INFO",
            "propagate": False,
        },
        "orchestration": {
            "handlers": ["console", "prefect_file"],
            "level": "INFO",
            "propagate": False,
        },
        "users.serializers": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "customers.views": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
}

# Create logs directory if it doesn't exist
LOG_DIR = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
