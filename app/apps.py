from django.apps import AppConfig


class AppConfig(AppConfig):
    name = 'app'

    def ready(self):
        try:
            from django.contrib.auth.models import User

            if not User.objects.filter(username='admin').exists():
                User.objects.create_superuser(
                    username='admin',
                    email='admin@example.com',
                    password='Admin@123'
                )
                print("Admin user created")
        except Exception:
            pass