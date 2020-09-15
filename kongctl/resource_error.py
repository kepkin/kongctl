class GetError(Exception):
    def __init__(self, args, request_name, e):
        self.data_args = args
        self.data_req_name = request_name
        self.data_e = e

    def __str__(self):
        return "Get: {} - {}; Error: {}".format(self.data_req_name, getattr(self.data_args, self.data_req_name),
                                                self.data_e)


class DeleteError(Exception):
    def __init__(self, args, request_name, e):
        self.data_args = args
        self.data_req_name = request_name
        self.data_e = e

    def __str__(self):
        recursive_delete = ''
        if getattr(self.data_args, 'recursive', False):
            recursive_delete = ' recursive'
        return "Delete{}: {} - {}; Error: {}".format(recursive_delete, self.data_req_name,
                                                     getattr(self.data_args, self.data_req_name), self.data_e)


class ConfigGetError(Exception):
    def __init__(self, e):
        self.data_e = e

    def __str__(self):
        return "Config method {}".format(self.data_e)


class DumpServiceError(Exception):
    def __init__(self, args):
        self.data_service = getattr(args, 'service')

    def __str__(self):
        return "Service dump: {} not found".format(self.data_service)


class EnsureKeyAuthError(Exception):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "Consumer {} in keyauth_credentials missing field key".format(self.name)


class EnsureServiceError(Exception):
    def __init__(self, e):
        self.data_e = e

    def __str__(self):
        return "Service missing field: {}".format(self.data_e)


class SnapshotConfigMissingFieldError(Exception):
    def __init__(self, e):
        self.data_e = e

    def __str__(self):
        return "Field {} not present in config file".format(self.data_e)
