from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        # Import signals when Django app is ready
        import core.models  # noqa
