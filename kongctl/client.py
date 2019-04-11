import argparse
import json
import os.path
import requests


class HttpClient(object):
    _default_opts = {
        "timeout": 5,
        "verbose": False,
        "server": "localhost:8001",
    }

    def __init__(self, server, timeout, auth=None, verbose=False, **kwargs):
        self.endpoint = server
        self.verbose = verbose
        self.timeout = timeout
        self.session = requests.Session()

        if self.endpoint[0:4] != "http":
            self.endpoint = "http://" + self.endpoint

        if auth:
            if auth.get('type') == 'basic':
                self.session.auth = (auth.get('user'), auth.get('password'))

        if self.verbose:
            print("Constructing HttpClient call: ", self.endpoint)

    @classmethod
    def build_from_args(cls, args):
        opts = dict()
        opts.update(cls._default_opts)

        if args.ctx:
            ctx_path = os.path.expanduser(args.ctx)
            if not os.path.exists(ctx_path):
                ctx_path = os.path.expanduser(os.path.join("~", ".kongctl", ctx_path))

            opts.update(json.load(open(ctx_path)))

        opts.update(vars(args))

        return cls(**opts)

    @staticmethod
    def build_parser(parser):
        parser.add_argument("-c", "--ctx", metavar="PATH", help="context file")
        parser.add_argument("-s", "--server", metavar="url", default=argparse.SUPPRESS, help="Url to kong api")
        parser.add_argument("-v", dest="verbose", action='store_true', default=False, help="verbose mode")

    def request(self, method, url, *args, **kwargs):
        if self.verbose:
            print("Making {} call: {}".format(method, self.endpoint + url, args, kwargs))

        kwargs['timeout'] = self.timeout
        res = self.session.request(method, self.endpoint + url, *args, **kwargs)
        if self.verbose:
            json_body = None
            try:
                json_body = res.json()
            except Exception:
                pass
            print("Recieved {}: {}".format(res.status_code, json_body))

        if res.status_code not in {200, 201, 204}:
            raise RuntimeError("Return status code: {}".format(res.status_code))

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
