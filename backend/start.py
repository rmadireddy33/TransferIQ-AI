"""Railway entry point. All migrations/seed work remains in FastAPI's lifespan."""
import logging
from logging.config import dictConfig
import os
import sys

import uvicorn

from backend.core.logging import LOG_CONFIG


def server_options(environ=None):
    env = os.environ if environ is None else environ
    value = env.get('PORT', '8000')
    if not value.isdecimal() or not 1 <= int(value) <= 65535:
        raise ValueError('PORT must be an integer from 1 to 65535')
    return dict(app='backend.main:app', host='0.0.0.0', port=int(value),
                workers=1, reload=False, access_log=False, log_config=LOG_CONFIG)


def main():
    sys.dont_write_bytecode = True
    dictConfig(LOG_CONFIG)
    logger = logging.getLogger('transferiq.start')
    try:
        options = server_options()
    except ValueError:
        logger.error('configuration_invalid', extra={'phase': 'port', 'error_type': 'ValueError'})
        raise SystemExit(1) from None
    logger.info('server_starting', extra={'port': options['port']})
    uvicorn.run(**options)


if __name__ == '__main__':
    main()
