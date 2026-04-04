import os
from django.core.asgi import get_asgi_application


def _enable_datadog_if_configured():
	enabled = os.getenv('DD_TRACE_ENABLED', 'false').lower() == 'true'
	if not enabled:
		return

	try:
		from ddtrace import config, patch_all

		patch_all(django=True)
		config.django['service_name'] = os.getenv('DD_SERVICE', 'crackcms-backend')
	except Exception:
		# Datadog must never block application boot.
		pass


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
_enable_datadog_if_configured()
application = get_asgi_application()
