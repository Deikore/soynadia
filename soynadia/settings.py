"""
Django settings for soynadia project.
"""

from pathlib import Path
import os
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, False)
)

# Read .env file if it exists
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default='django-insecure-development-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# CSRF Trusted Origins (required for Cloudflare Tunnel and reverse proxies)
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

# If CSRF_TRUSTED_ORIGINS is empty, try to derive from ALLOWED_HOSTS
if not CSRF_TRUSTED_ORIGINS and ALLOWED_HOSTS:
    # Auto-generate CSRF_TRUSTED_ORIGINS from ALLOWED_HOSTS
    # For Cloudflare Tunnel, use https://
    CSRF_TRUSTED_ORIGINS = [
        f"https://{host}" if not host.startswith('http') else host
        for host in ALLOWED_HOSTS
        if host not in ['localhost', '127.0.0.1', '*']
    ]
    # Add http:// for localhost in development
    if DEBUG:
        CSRF_TRUSTED_ORIGINS.extend([
            f"http://{host}" for host in ALLOWED_HOSTS
            if host in ['localhost', '127.0.0.1']
        ])


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'users',
    'voters',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Security headers - only set COOP/COEP when using HTTPS
# These headers require HTTPS to be trusted by browsers
if not DEBUG:
    # Only set Cross-Origin headers when we're actually using HTTPS
    # Check if we're behind a proxy that indicates HTTPS
    SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'
    SECURE_CROSS_ORIGIN_EMBEDDER_POLICY = None  # Don't set COEP unless needed

ROOT_URLCONF = 'soynadia.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'soynadia.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('POSTGRES_DB', default='soynadia'),
        'USER': env('POSTGRES_USER', default='postgres'),
        'PASSWORD': env('POSTGRES_PASSWORD', default='postgres'),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
    }
}


# Custom User Model
AUTH_USER_MODEL = 'users.CustomUser'


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 10,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Password hashers (Argon2 is the most secure)
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'es-co'

TIME_ZONE = 'America/Bogota'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []

# WhiteNoise configuration
# Using StaticFilesStorage instead of CompressedStaticFilesStorage to avoid issues with compressed files
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# WhiteNoise settings
WHITENOISE_USE_FINDERS = True  # Allow WhiteNoise to serve files from STATICFILES_DIRS
WHITENOISE_AUTOREFRESH = True  # Auto-refresh in development

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Authentication settings
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'


# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'voters.authentication.ApiKeyAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}


# Security settings for production
# Only apply strict security when actually using HTTPS (detected via proxy headers)
# This prevents warnings when accessing via HTTP or untrusted origins
if not DEBUG:
    # Check if we should enforce HTTPS (only when behind a proxy that indicates HTTPS)
    # These will be set based on X-Forwarded-Proto header from proxy
    SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)
    SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=0)  # Disabled by default, enable when using HTTPS
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True if SECURE_HSTS_SECONDS > 0 else False
    SECURE_HSTS_PRELOAD = True if SECURE_HSTS_SECONDS > 0 else False
    SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=False)
    CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=False)
    
    # Cross-Origin headers - only set when using HTTPS
    # These cause warnings if set on HTTP or untrusted origins
    SECURE_CROSS_ORIGIN_OPENER_POLICY = None  # Don't set unless explicitly needed with HTTPS
    SECURE_CROSS_ORIGIN_EMBEDDER_POLICY = None

# Proxy settings (for Cloudflare Tunnel and reverse proxies)
# Trust proxy headers from Nginx/Cloudflare
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Cloudflare sends CF-Visitor header to indicate original scheme
# Django will trust X-Forwarded-Proto from Nginx
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
