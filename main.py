#!/usr/bin/python3
import sys
import os
import logging
from gnucash_rest import app

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))

    logger.debug(sys.argv)
    app.run(host='0.0.0.0')
