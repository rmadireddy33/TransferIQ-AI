"""JSON console logging: no request headers, bodies, SQL parameters or traceback text."""
from datetime import datetime, timezone
import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record):
        message = record.getMessage()
        # Uvicorn's lifespan logger can place a whole traceback in the message.
        if 'Traceback (most recent call last)' in message:
            message = 'Application lifecycle failed; inspect startup_failed event'
        payload = dict(timestamp=datetime.now(timezone.utc).isoformat(),
                       level=record.levelname, logger=record.name, event=message)
        for name in ('phase', 'error_type', 'schema_version', 'seed_rows', 'seed_documents', 'port'):
            if hasattr(record, name):
                payload[name] = getattr(record, name)
        if record.exc_info:
            payload['error_type'] = record.exc_info[0].__name__
        return json.dumps(payload)


LOG_CONFIG = {
    'version': 1, 'disable_existing_loggers': False,
    'formatters': {'json': {'()': 'backend.core.logging.JsonFormatter'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'stream': 'ext://sys.stdout', 'formatter': 'json'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'uvicorn': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'uvicorn.error': {'level': 'INFO', 'propagate': True},
        'uvicorn.access': {'handlers': [], 'level': 'WARNING', 'propagate': False},
    },
}
