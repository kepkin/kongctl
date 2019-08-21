import logging
import sys


class LoggerConfig(object):
    def __init__(self, name='__name__', stream_handler=sys.stderr):
        self.logger_name = name
        self.stream_handler = logging.StreamHandler(stream_handler)
        self.simple_formatter = logging.Formatter('%(levelname)s, %(asctime)s, %(module)s - %(message)s')
        self.super_verbose_formatter = logging.Formatter(
            '%(levelname)s, %(asctime)s, %(module)s, func %(funcName)s, line %(lineno)d - %(message)s')
        self.stream_handler.setFormatter(self.simple_formatter)

    def get_simple_logger(self):
        logger = logging.getLogger(self.logger_name)
        logger.setLevel(logging.INFO)
        logger.addHandler(self.stream_handler)

        return logger

    def get_verbose_logger(self):
        logger = logging.getLogger(self.logger_name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(self.stream_handler)

        return logger

    def get_super_verbose_logger(self):
        logger = logging.getLogger(self.logger_name)
        logger.setLevel(logging.DEBUG)
        self.stream_handler.setFormatter(self.super_verbose_formatter)
        logger.addHandler(self.stream_handler)

        return logger
