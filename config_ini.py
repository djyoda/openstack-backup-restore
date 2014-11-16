#!/usr/bin/env python

import os.path
import logging.config

LOGGING_CONF = os.path.join(os.path.dirname(__file__),
                            "logging.ini")
logging.config.fileConfig(LOGGING_CONF)
