import logging
import logging.config

import requests

from .logger import LoggerConfig


class HttpClient(object):
    logger_init_flag = False
    success_codes = {
        200,
        201,
        204,
    }
    skip_decode_codes = {
        204,
        502,
        503,
    }

    default_opts = {
        "timeout": 5,
        "additional_time": 5,
        "verbose": False,
        "server": "localhost:8001",
    }

    def __init__(self, server, timeout, additional_time, auth=None, super_verbose=False, verbose=False, **kwargs):
        self.endpoint = server
        self.verbose = verbose
        self.super_verbose = super_verbose
        self.timeout = timeout
        self.additional_time = additional_time
        self.session = requests.Session()
        self.logger = self.get_logger()

        if self.endpoint[0:4] != "http":
            self.endpoint = "http://" + self.endpoint

        if auth:
            if auth.get('type') == 'basic':
                self.session.auth = (auth.get('user'), auth.get('password'))

        self.logger.debug("Constructing HttpClient call: {}".format(self.endpoint))

    def get_logger(self, name='__name__'):
        if HttpClient.logger_init_flag:
            return logging.getLogger(name)

        logger_config = LoggerConfig()
        HttpClient.logger_init_flag = True

        if self.verbose:
            return logger_config.get_verbose_logger()
        elif self.super_verbose:
            return logger_config.get_super_verbose_logger()
        return logger_config.get_simple_logger()

    def request(self, method, url, *args, **kwargs):
        self.logger.debug("Making {} call: {}".format(method, self.endpoint + url, args, kwargs))
        payload = kwargs.get('json')
        if payload:
            self.logger.debug("Payload: {}".format(payload))

        try:
            kwargs['timeout'] = self.timeout
            res = self.session.request(method, self.endpoint + url, *args, **kwargs)
        except requests.exceptions.ReadTimeout:
            kwargs['timeout'] += self.additional_time
            res = self.session.request(method, self.endpoint + url, *args, **kwargs)

        response_content = res.text

        if res.status_code not in self.skip_decode_codes:
            try:
                response_content = res.json()
            except Exception as e:
                raise RuntimeError("Failed to decode json on request {} {} ({}): {}".format(method, url, res.status_code, res.text)) from e

        if self.super_verbose:
            self.logger.debug('Received {}:\n{}'.format(res.status_code, response_content))

        if res.status_code not in self.success_codes:
            raise RuntimeError("Received {}: {}".format(res.status_code, response_content))

        return res

    def get(self, *args, **kwargs):
        return self.request("get", *args, **kwargs)

    def post(self, *args, **kwargs):
        return self.request("post", *args, **kwargs)

    def patch(self, *args, **kwargs):
        return self.request("patch", *args, **kwargs)

    def put(self, *args, **kwargs):
        return self.request("put", *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self.request("delete", *args, **kwargs)
