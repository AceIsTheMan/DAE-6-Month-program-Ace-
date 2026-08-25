import django

# This line uses the module, which clears the "not accessed" warning!
print(django.get_version()) 

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}