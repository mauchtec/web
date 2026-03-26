try:
	from .celery import app as celery_app
except Exception:
	# If Celery isn't installed or celery app fails to import, don't break Django startup.
	celery_app = None
	try:
		import logging

		logger = logging.getLogger(__name__)
		logger.warning(
			"Celery is not available in the environment. Background tasks will "
			"fall back to in-process threads. Install Celery and a broker to "
			"enable async task processing."
		)
	except Exception:
		# If logging itself fails for any reason, silently ignore to avoid
		# interfering with Django startup.
		pass

# Expose the Celery app as a module-level variable for `celery -A AccessControll worker`
__all__ = ('celery_app',)
