# profootgn/settings.py (corrigé / déployable)
from pathlib import Path
from dotenv import load_dotenv
import os
from datetime import timedelta
import dj_database_url  # Render/Postgres

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# =========================
# Core
# =========================
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
DEBUG = os.getenv("DEBUG", "True").strip().lower() in {"1", "true", "yes", "on"}

# ALLOWED_HOSTS
# On accepte via env (CSV) + quelques hosts utiles par défaut pour Render/Vercel et ton domaine
_default_hosts = ".onrender.com,.vercel.app,profootgn-api.onrender.com,kanousport.com,www.kanousport.com"
_raw_allowed = os.getenv("ALLOWED_HOSTS", _default_hosts)
ALLOWED_HOSTS = [h.strip() for h in _raw_allowed.split(",") if h.strip()]

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

    # WhiteNoise doit être AVANT 'django.contrib.staticfiles'
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",

    # 3rd party
    "rest_framework",
    "corsheaders",
    "django_filters",

    # locaux
    "clubs",
    "players",
    "matches",
    "stats",
    "news",
    "recruitment",
    "users",
    "ads",
]

# Cloudinary apps si disponible
USE_CLOUDINARY = bool(os.getenv("CLOUDINARY_URL"))
if USE_CLOUDINARY:
    INSTALLED_APPS += ["cloudinary", "cloudinary_storage"]

# =========================
# Middleware
# =========================
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # ← le plus haut possible
    "django.middleware.security.SecurityMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
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
# Database
# =========================
if os.getenv("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.parse(
            os.environ["DATABASE_URL"],
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
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
# Auth / Locale
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
os.makedirs(MEDIA_ROOT, exist_ok=True)

# STORAGES (Django 4.2+/5)
if USE_CLOUDINARY:
    STORAGES = {
        "default": {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
    CLOUDINARY_MEDIA_PREFIX = os.getenv("CLOUDINARY_MEDIA_PREFIX", "profootgn")
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(MEDIA_ROOT)},
        },
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

# Limites/permissions d’upload
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
FILE_UPLOAD_PERMISSIONS = 0o644

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========================
# DRF / JWT
# =========================
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
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
# FRONTEND_ORIGIN (mettre https://www.kanousport.com en prod)
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

# EXTRA origins CSV (par ex previews vercel, autres frontends)
EXTRA_ORIGINS = [o.strip() for o in os.getenv("BACKEND_ALLOWED_ORIGINS", "").split(",") if o.strip()]

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://kanousport.com",
    ]
    CORS_ALLOWED_ORIGIN_REGEXES = []
else:
    # Production: n'autorise que des origines explicites
    CORS_ALLOW_ALL_ORIGINS = False
    # On construit une liste à partir du FRONTEND_ORIGIN + EXTRA_ORIGINS
    # et on ajoute explicitement les possibles front (kanousport) et vercel previews via regex
    explicit_origins = [FRONTEND_ORIGIN] + EXTRA_ORIGINS
    # aussi autoriser l'hostname du frontend vercel par défaut (optionnel)
    explicit_origins = list(dict.fromkeys([*explicit_origins, "https://profootgn-frontend.vercel.app", "https://www.kanousport.com", "https://kanousport.com"]))
    # garder que les valeurs commençant par http/https
    CORS_ALLOWED_ORIGINS = [o for o in explicit_origins if o.startswith(("http://", "https://"))]
    CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://.*\.vercel\.app$"]

# Si tu utilises des cookies/session côté client
CORS_ALLOW_CREDENTIALS = True

# CSRF doit lister des origines EXPLICITES (https://domain)
CSRF_TRUSTED_ORIGINS = [
    o for o in ([FRONTEND_ORIGIN] + EXTRA_ORIGINS + ["https://www.kanousport.com", "https://kanousport.com"]) if o.startswith(("http://", "https://"))
]

# =========================
# Sécurité
# =========================
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = not DEBUG

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# À durcir en prod (ex: 31536000) une fois le domaine final stabilisé
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

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

# =========================
# Logging
# =========================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": True},
        "cloudinary": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
