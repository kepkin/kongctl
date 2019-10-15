import argparse
import json
import os.path
import requests
import logging
import logging.config
import yaml
from .logger import LoggerConfig


class HttpClient(object):
    logger_init_flag = False

    _default_opts = {
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

    @classmethod
    def build_from_args(cls, args):
        opts = dict()
        opts.update(cls._default_opts)

        if args.ctx:
            ctx_path = os.path.expanduser(args.ctx)
            if not (os.path.isfile(ctx_path) and os.path.exists(ctx_path)):
                ctx_path = os.path.expanduser(os.path.join("~", ".kongctl", ctx_path))

            opts.update(json.load(open(ctx_path)))

        opts.update(vars(args))

        return cls(**opts)

    @staticmethod
    def build_parser(parser):
        parser.add_argument("-c", "--ctx", metavar="PATH", help="context file")
        parser.add_argument("-s", "--server", metavar="url", default=argparse.SUPPRESS, help="Url to kong api")
        parser.add_argument("--timeout", default=5, type=int, help="Timeout in seconds")
        parser.add_argument("-v", dest="verbose", action='store_true', default=False, help="verbose mode")
        parser.add_argument("-vv", dest="super_verbose", action='store_true', default=False, help="super verbose mode")

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

        json_body = None
        try:
            json_body = res.json()
        except Exception:
            pass

        if self.super_verbose:
            self.logger.debug('Recieved {}:\n{}'.format(res.status_code, json_body))

        if res.status_code not in {200, 201, 204}:
            raise RuntimeError("Recieved {}: {}".format(res.status_code, res.json()))

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
