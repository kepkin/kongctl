import requests


class HttpClient(object):
    def __init__(self, endpoint, verbose=False):
        self.endpoint = endpoint
        self.verbose = verbose

        if self.verbose:
            print("Constructing HttpClient call: ", self.endpoint)

    @classmethod
    def build_from_args(cls, args):
        return cls(
            endpoint=args.server,
            verbose=args.verbose
        )

    @staticmethod
    def build_parser(parser):
        parser.add_argument("-c", "--ctx", metavar="PATH", help="context file")
        parser.add_argument("-s", "--server", metavar="url", help="Url to kong api")
        parser.add_argument("-v", dest="verbose", action='store_true', default=False, help="verbose mode")

    def request(self, method, url, *args, **kwargs):
        if self.verbose:
            print("Making {} call: {}".format(method, self.endpoint + url, args, kwargs))

        res = requests.request(method, self.endpoint + url, *args, **kwargs)
        if self.verbose:
            print("Recieved {}: {}".format(res.status_code, res.json()))

        if res.status_code not in {200, 201, 204}:
            raise RuntimeError("Return status code: {}".format(res.status_code))

        return res

    def get(self, *args, **kwargs):
        return self.request("get", *args, **kwargs)

    def post(self, *args, **kwargs):
        return self.request("post", *args, **kwargs)

    def patch(self, *args, **kwargs):
        return self.request("patch", *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self.request("delete", *args, **kwargs)
