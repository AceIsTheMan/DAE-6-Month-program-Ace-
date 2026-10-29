# Inside your project's settings.py tab
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Ensure DIRS points to your template folder if you keep them in a root folder
        'DIRS': [BASE_DIR / 'templates'], 
        'APP_DIRS': True, # <--- THIS MUST BE TRUE TO AUTOMATICALLY FIND TEMPLATE FOLDERS!!!
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