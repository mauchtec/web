"""Simple notification helper used by `voip.approve_webhook`.

This is a lightweight placeholder that attempts a best-effort notification.
Projects can replace or extend this module to integrate real FCM/WebSocket
delivery. The function `send_push(recipient, payload)` returns True on
success and raises on fatal errors.
"""
import logging

logger = logging.getLogger(__name__)


def send_push(recipient_identifier, payload):
    """Send a push notification.

    This placeholder simply logs the payload. If `recipient_identifier` is
    None it's treated as a broadcast. Returns True on success.
    """
    try:
        if recipient_identifier:
            logger.info("send_push to %s: %s", recipient_identifier, payload)
        else:
            logger.info("send_push broadcast: %s", payload)
        return True
    except Exception as e:
        logger.exception("send_push failed: %s", e)
        raise
