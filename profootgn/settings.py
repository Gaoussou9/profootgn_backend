# profootgn/settings.py
from pathlib import Path
from dotenv import load_dotenv
import os
from datetime import timedelta

# --- Ajouts pour staging Render/Postgres & statiques ---
import dj_database_url  # <- NEW (Render/Postgres)
# ---------------------

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# =========================
# Core
# =========================
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
DEBUG = os.getenv("DEBUG", "True").strip().lower() in {"1", "true", "yes", "on"}

# Si ALLOWED_HOSTS n'est pas défini, on met une valeur par défaut compatible staging
_default_hosts = ".onrender.com,.vercel.app,localhost,127.0.0.1"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", _default_hosts if not DEBUG else "*").split(",") if h.strip()] or (["*"] if DEBUG else [".onrender.com", ".vercel.app"])

# =========================
# Apps
# =========================
INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # 3rd party
    "rest_framework",
    "corsheaders",
    "django_filters",

    # NEW: pour servir les statiques efficacement (Render)
    "whitenoise.runserver_nostatic",

    # local apps
    "clubs",
    "players",
    "matches",
    "stats",
    "news",
    "recruitment",
    "users",
]

# =========================
# Middleware
# =========================
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # doit rester en tête
    "django.middleware.security.SecurityMiddleware",

    # NEW: compression/caching des statiques en prod/staging
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "profootgn.urls"

# =========================
# Templates
# =========================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # overrides admin/partials
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "profootgn.wsgi.application"

# =========================
# Database (MySQL local / Postgres Render)
# =========================
import dj_database_url

if os.getenv("DATABASE_URL"):
    # Prod/Render: utilise la chaîne postgres://
    DATABASES = {
        "default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=600)
    }
else:
    # Dev local: MySQL
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "profootgn_db"),
            "USER": os.getenv("DB_USER", "Admin"),
            "PASSWORD": os.getenv("DB_PASSWORD", "Admin"),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }


# =========================
# Auth
# =========================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Conakry"
USE_I18N = True
USE_TZ = True

# =========================
# Static / Media
# =========================
STATIC_URL = "/static/"
STATICFILES_DIRS: list[str] = []
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# NEW: stockage statiques via Whitenoise (manifeste compressé)
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========================
# DRF / JWT
# =========================
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    # lecture publique par défaut ; routes d'écriture protégées dans les viewsets
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=6),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# =========================
# CORS / CSRF
# =========================
# En dev (DEBUG=True) on ouvre à tous pour simplifier.
CORS_ALLOW_ALL_ORIGINS = True if DEBUG else False

# Origines explicites (prod/staging)
# Tu peux définir ALLOWED_ORIGINS dans .env (séparées par des virgules).
_origins_env = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
)
CORS_ALLOWED_ORIGINS = [o.strip() for o in _origins_env.split(",") if o.strip()]

# En staging/prod sans ALLOWED_ORIGINS custom, autorise tous les sous-domaines vercel.app
if not DEBUG and not CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGIN_REGEXES = [r"^https:\/\/.*\.vercel\.app$"]
else:
    CORS_ALLOWED_ORIGIN_REGEXES = []

# CSRF doit inclure le schéma (ne supporte pas les regex)
# On dérive depuis CORS_ALLOWED_ORIGINS + ajoute Render/Vercel par défaut en staging/prod
CSRF_TRUSTED_ORIGINS = [o for o in CORS_ALLOWED_ORIGINS if o.startswith(("http://", "https://"))]
if not DEBUG:
    CSRF_TRUSTED_ORIGINS += [
        "https://*.vercel.app",
        "https://*.onrender.com",
    ]

# (décommente si tu utilises des cookies/sessions cross-site)
# CORS_ALLOW_CREDENTIALS = True

# =========================
# Sécurité (staging/prod)
# =========================
# Indique à Django que le proxy (Render) passe du HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
# En prod, tu pourras activer HSTS (ex: 31536000)
SECURE_HSTS_SECONDS = 0

# =========================
# Jazzmin
# =========================
JAZZMIN_SETTINGS = {
    "site_title": "Administration de Django",
    "site_header": "Administration de Django",
    "site_brand": "Administration de Django",
    "welcome_sign": "Tableau de bord",
    "copyright": "LiveFootGn",

    "topmenu_links": [
        {"name": "Accueil", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"app": "players"},
        {"app": "clubs"},
        {"app": "matches"},
        {"app": "recruitment"},
        {"app": "users"},
        {"name": "Espace Admin LiveFootGn", "url": "admin_livefootgn"},
    ],

    "order_with_respect_to": [
        "auth", "players", "clubs", "matches", "stats", "news", "recruitment", "users"
    ],

    "icons": {
        "auth": "fas fa-shield-alt",
        "auth.Group": "fas fa-users-cog",
        "auth.User": "fas fa-user",
        "players": "fas fa-user-friends",
        "players.Player": "fas fa-user",
        "clubs": "fas fa-flag",
        "clubs.Club": "fas fa-shield",
        "matches": "fas fa-futbol",
        "matches.Match": "fas fa-calendar-check",
        "matches.Goal": "fas fa-futbol",
        "matches.Card": "fas fa-square",
        "matches.Round": "fas fa-layer-group",
        "stats": "fas fa-chart-line",
        "news": "fas fa-newspaper",
        "recruitment": "fas fa-briefcase",
        "recruitment.Recruiter": "fas fa-user-tie",
        "recruitment.TrialRequest": "fas fa-clipboard-check",
        "users": "fas fa-id-badge",
        "users.Profile": "fas fa-id-card",
    },

    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "related_modal_active": True,
    "show_sidebar": True,
}

JAZZMIN_UI_TWEAKS = {
    "theme": "flatly",
    "dark_mode_theme": None,
    "navbar": "navbar-white navbar-light",
    "sidebar": "sidebar-dark-primary",
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "fixed_sidebar": True,
    "sidebar_nav_small_text": False,
    "sidebar_nav_flat_style": False,
    "login_logo": None,
}
