import json
import sys


class BaseResource(object):
    def __init__(self, http_client, formatter, resource_name):
        self.resource_name = resource_name
        self.cache = dict()
        self.http_client = http_client
        self.formatter = formatter

    def short_formatter(self, resource):
        return "{}".format(resource['id'])

    def ensure_cache(self):
        if len(self.cache) == 0:
            self.rebuild_cache()

    def rebuild_cache(self):
        for _ in self._list(None, None):
            pass

    def load_data_from_stdin(self):
        data = sys.stdin.read()
        return json.loads(data)

    def _build_resource_url(self, op, args=None, non_parsed=None, id_=None):
        if op == 'get_by_id':
            return '/{}/{}/'.format(self.resource_name, id_)
        elif op == 'list':
            return '/{}'.format(self.resource_name)
        elif op in {'get', 'update', 'delete'}:
            return '/{}/{}'.format(self.resource_name, self.id_getter(getattr(args, self.resource_name[:-1])))
        elif op in {'create'}:
            return '/{}'.format(self.resource_name)

    def _list(self, args, non_parsed):
        next_url = self._build_resource_url('list', args, non_parsed)

        while next_url:
            r = self.http_client.get(next_url)
            data = r.json()
            next_url = data.get('next', None)

            for resource in data['data']:
                if 'name' in resource and 'id' in resource:
                    self.cache[resource['id']] = resource
                yield resource

    def list(self, args, non_parsed):
        for resource in self._list(args, non_parsed):
            if args.list_full:
                self.formatter.print_obj(resource)
                self.formatter.println()
            else:
                self.short_formatter(resource)

    def get_by_id(self, id):
        self.ensure_cache()
        resource = self.cache.get(id)

        if resource is None:
            url = self._build_resource_url('get_by_id', None, None, id_=id)
            url = '/{}/{}'.format(self.resource_name, id)
            r = self.http_client.get(url)
            return r.json()

        return resource

    def get(self, args, non_parsed):
        url = self._build_resource_url('get', args, non_parsed)
        r = self.http_client.get(url)
        self.formatter.print_obj(r.json())

    def create(self, args, non_parsed):
        url = self._build_resource_url('create', args, non_parsed)
        data = self.load_data_from_stdin()
        r = self.http_client.post(url, json=data)
        self.formatter.print_obj(r.json())

    def update(self, args, non_parsed):
        url = self._build_resource_url('update', args, non_parsed)
        data = self.load_data_from_stdin()
        r = self.http_client.patch(url, json=data)
        self.formatter.print_obj(r.json())

    def delete(self, args, non_parsed):
        url = self._build_resource_url('delete', args, non_parsed)
        r = self.http_client.delete(url)


class ServiceResource(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'services')

    def short_formatter(self, resource):
        self.formatter.print_pair(resource['id'], resource['name'])
        self.formatter.println("{}{}".format(resource['host'], resource['path'] or ''), indent=1)
        self.formatter.println()

    def id_getter(self, resource_name):
        r = self.http_client.get('/{}/{}'.format("services", resource_name))
        return r.json()['id']

    def build_parser(self, sb_list, sb_get, sb_create, sb_update, sb_delete):
        list_ = sb_list.add_parser(self.resource_name)
        list_.set_defaults(func=self.list)

        get = sb_get.add_parser(self.resource_name[:-1])
        get.set_defaults(func=self.get)
        get.add_argument("service", help='service id')

        create = sb_create.add_parser(self.resource_name[:-1])
        create.set_defaults(func=self.create)
        # @TODO

        update = sb_update.add_parser(self.resource_name[:-1])
        update.set_defaults(func=self.update)
        update.add_argument("service", help='service id')
        # @TODO

        delete = sb_delete.add_parser(self.resource_name[:-1])
        delete.set_defaults(func=self.delete)
        delete.add_argument("service", help='service id')


class RouteResource(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'routes')

    def short_formatter(self, resource, indent=0):
        hosts = resource.get('hosts', None) or ['*']
        paths = resource.get('paths', None) or ['/']

        ref = ServiceResource(self.http_client, self.formatter)
        self.formatter.print_pair(resource['id'], ref.get_by_id(resource['service']['id'])['name'], indent=indent)

        ops = []
        for h in hosts:
            for p in paths:
                self.formatter.println(h + p, indent=indent + 1)

        self.formatter.println()

    def id_getter(self, resource_name):
        r = self.http_client.get('/{}/{}'.format("routes", resource_name))
        return r.json()['id']

    def _build_resource_url(self, op, args, non_parsed, **kwargs):
        if op in {'list'} and args and args.service is not None:
            return '/{}/{}/{}/'.format('services', args.service, self.resource_name)
        else:
            return super()._build_resource_url(op, args, non_parsed, **kwargs)

    def create(self, args, non_parsed):
        url = self._build_resource_url('create', args, non_parsed)

        ref = ServiceResource(self.http_client, self.formatter)
        service_id = ref.id_getter(args.service)

        data = self.load_data_from_stdin()
        data['service'] = {'id': service_id}

        r = self.http_client.post(url, json=data)
        self.formatter.print_obj(r.json())

    def build_parser(self, sb_list, sb_get, sb_create, sb_update, sb_delete):
        list_ = sb_list.add_parser(self.resource_name)
        list_.set_defaults(func=self.list)
        list_.add_argument('-s', "--service", default=None, help='service name or id')

        get = sb_get.add_parser(self.resource_name[:-1])
        get.set_defaults(func=self.get)
        get.add_argument("route", help='route id')

        create = sb_create.add_parser(self.resource_name[:-1])
        create.add_argument('-s', "--service", default=None, help='service name or id')
        create.set_defaults(func=self.create)
        # @TODO

        update = sb_update.add_parser(self.resource_name[:-1])
        update.set_defaults(func=self.update)
        update.add_argument("route", help='route id')
        # @TODO

        delete = sb_delete.add_parser(self.resource_name[:-1])
        delete.set_defaults(func=self.delete)
        delete.add_argument("route", help='route id')


class PluginResource(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'plugins')

    @staticmethod
    def _chain_key_get(d, *keys):
        for key in keys:
            v = d
            for key_part in key.split('.'):
                if not isinstance(v, dict):
                    break

                v = v.get(key_part)

            if v:
                return v

        return None

    def short_formatter(self, resource):
        service_name = '*all*'
        route_res = None
        service_id = self._chain_key_get(resource, 'service.id', 'service_id')
        if service_id:
            ref = ServiceResource(self.http_client, self.formatter)
            service_name = ref.get_by_id(service_id)['name']

        route_ref = RouteResource(self.http_client, self.formatter)
        route_id = self._chain_key_get(resource, 'route.id', 'route_id')
        if route_id:
            route_res = route_ref.get_by_id(route_id)

        self.formatter.print_header("{}: {} (service {}) {}".format(resource['id'], resource['name'], service_name, 'on' if resource['enabled'] else 'off'))
        self.formatter.print_pair('Service', service_name, indent=1)

        if route_res:
            self.formatter.print_pair('Route', '', indent=1)
            route_ref.short_formatter(route_res, indent=2)
        else:
            self.formatter.print_pair('Route', '*all*', indent=1)

    def id_getter(self, resource_name):
        r = self.http_client.get('/{}/{}'.format("plugins", resource_name))
        return r.json()['id']

    def _build_resource_url(self, op, args, non_parsed, **kwargs):
        if op in {'list'} and args and args.service is not None:
            return '/{}/{}/{}/'.format('services', args.service, self.resource_name)
        else:
            return super()._build_resource_url(op, args, non_parsed, **kwargs)

    def create(self, args, non_parsed):
        url = self._build_resource_url('create', args, non_parsed)

        service_ref = ServiceResource(self.http_client, self.formatter)
        route_ref = RouteResource(self.http_client, self.formatter)

        data = self.load_data_from_stdin()

        if args.service:
            data['service'] = {'id': service_ref.id_getter(args.service)}

        if args.route:
            data['route'] = {'id': route_ref.id_getter(args.route)}

        r = self.http_client.post(url, json=data)
        self.formatter.print_obj(r.json())

    def build_parser(self, sb_list, sb_get, sb_create, sb_update, sb_delete):
        list_ = sb_list.add_parser(self.resource_name)
        list_.set_defaults(func=self.list)
        list_.add_argument('-s', "--service", default=None, help='Will list plugins for this service (name or id)')

        get = sb_get.add_parser(self.resource_name[:-1])
        get.set_defaults(func=self.get)
        get.add_argument("plugin", help='plugin id')

        create = sb_create.add_parser(self.resource_name[:-1])
        create.add_argument('-s', "--service", default=None, help='Will apply plugin to this service (name or id)')
        create.add_argument('-r', "--route", default=None, help='Will apply plugin to this route id')
        create.set_defaults(func=self.create)
        # @TODO

        update = sb_update.add_parser(self.resource_name[:-1])
        update.set_defaults(func=self.update)
        update.add_argument("plugin", help='plugin id')
        # @TODO

        delete = sb_delete.add_parser(self.resource_name[:-1])
        delete.set_defaults(func=self.delete)
        delete.add_argument("plugin", help='plugin id')


class PluginSchemaResource(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'plugins/schema')

    def short_formatter(self, resource):
        self.formatter.println(resource)

    def id_getter(self, resource_name):
        raise NotImplemented()

    def _list(self, args, non_parsed):
        r = self.http_client.get(self._build_resource_url('list', args, non_parsed))
        data = r.json()

        for resource in data['enabled_plugins']:
            yield resource

    def _build_resource_url(self, op, args=None, non_parsed=None, id_=None):
        if op == 'get':
            return '/plugins/schema/{}'.format(args.plugin)
        elif op == 'list':
            return '/plugins/enabled/'
        else:
            raise NotImplemented()

    def build_parser(self, sb_list, sb_get, sb_create, sb_update, sb_delete):
        list_ = sb_list.add_parser('pluginSchema')
        list_.set_defaults(func=self.list)

        get = sb_get.add_parser('pluginSchema')
        get.set_defaults(func=self.get)
        get.add_argument("plugin", help='plugin name')


class ConsumerResource(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'consumers')

    def short_formatter(self, resource):
        self.formatter.print_pair(resource['id'], resource['username'], indent=1)

    def id_getter(self, resource_name):
        r = self.http_client.get('/{}/{}'.format("consumers", resource_name))
        return r.json()['id']

    def create(self, args, non_parsed):
        url = self._build_resource_url('create', args, non_parsed)

        data = self.load_data_from_stdin()
        data['username'] = args.username

        r = self.http_client.post(url, json=data)
        self.formatter.print_obj(r.json())

    def build_parser(self, sb_list, sb_get, sb_create, sb_update, sb_delete):
        list_ = sb_list.add_parser(self.resource_name)
        list_.set_defaults(func=self.list)

        get = sb_get.add_parser(self.resource_name[:-1])
        get.set_defaults(func=self.get)
        get.add_argument("consumer", help='consumer id')

        create = sb_create.add_parser(self.resource_name[:-1])
        create.add_argument("-u", "--username", default=None, help="consumer's username")
        create.set_defaults(func=self.create)
        # @TODO

        update = sb_update.add_parser(self.resource_name[:-1])
        update.set_defaults(func=self.update)
        update.add_argument("consumer", help='consumer id')
        # @TODO

        delete = sb_delete.add_parser(self.resource_name[:-1])
        delete.set_defaults(func=self.delete)
        delete.add_argument("consumer", help='consumer id')


class KeyAuthResource(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'keyAuth')

    def short_formatter(self, resource):
        self.formatter.print_pair('key', resource['key'], indent=0)

    def _build_resource_url(self, op, args=None, non_parsed=None, id_=None):
        if op == 'get_by_id':
            raise NotImplemented()
        elif op == 'list':
            return '/consumers/{}/key-auth/'.format(args.consumer)
        elif op in {'get', 'update', 'delete'}:
            return '/consumers/{}/key-auth/{}'.format(args.consumer, args.keyauth)
        elif op in {'create'}:
            return '/consumers/{}/key-auth/'.format(args.consumer)

    def id_getter(self, resource_name):
        raise NotImplemented()

    def build_parser(self, sb_list, sb_get, sb_create, sb_update, sb_delete):
        list_ = sb_list.add_parser(self.resource_name)
        list_.set_defaults(func=self.list)
        list_.add_argument("consumer", help='consumer id {username or id}')

        get = sb_get.add_parser(self.resource_name)
        get.set_defaults(func=self.get)
        get.add_argument("consumer", help='consumer id {username or id}')
        get.add_argument("keyauth", help='id of keyauth')

        create = sb_create.add_parser(self.resource_name)
        create.add_argument("consumer", help='Will apply plugin data to this consumer {username or id}')
        create.set_defaults(func=self.create)

        update = sb_update.add_parser(self.resource_name)
        update.set_defaults(func=self.update)
        update.add_argument("consumer", help='Will apply plugin data to this consumer {username or id}')
        update.add_argument("keyauth", help='id of keyauth')

        delete = sb_delete.add_parser(self.resource_name)
        delete.set_defaults(func=self.delete)
        delete.add_argument("consumer", help='consumer id {username or id}')
        delete.add_argument("keyauth", help='id of keyauth')
