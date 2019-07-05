import json
import sys
import collections
import os
import yaml
from .yaml_formatter import YamlOutputFormatter
from operator import itemgetter

_get_verison = None


def get_version(http_client):
    global _get_verison
    if _get_verison is not None:
        return _get_verison

    r = http_client.get('/')
    data = r.json()
    _get_verison = tuple(map(int, data['version'].split('.')))
    return _get_verison


class BaseResource(object):
    def __init__(self, http_client, formatter, resource_name):
        self.resource_name = resource_name
        self.cache = dict()
        self.http_client = http_client
        self.formatter = formatter
        self.version = get_version(http_client)

    def short_formatter(self, resource):
        return "{}".format(resource['id'])

    def ensure_cache(self):
        if len(self.cache) == 0:
            self.rebuild_cache()

    def rebuild_cache(self):
        for _ in self._list(None, None):
            pass

    def id_getter(self, name):
        raise NotImplementedError()

    @staticmethod
    def load_data_from_stdin():
        data = sys.stdin.read()
        return json.loads(data)

    def build_resource_url(self, op, args=None, non_parsed=None, id_=None):
        if op == 'get_by_id':
            return '/{}/{}/'.format(self.resource_name, id_)
        elif op == 'list':
            return '/{}'.format(self.resource_name)
        elif op in {'get', 'update', 'delete'}:
            return '/{}/{}'.format(self.resource_name, self.id_getter(getattr(args, self.resource_name[:-1])))
        elif op in {'create'}:
            return '/{}'.format(self.resource_name)

    def _list(self, args, non_parsed):
        next_url = self.build_resource_url('list', args, non_parsed)
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

    def get_by_id(self, id_):
        self.ensure_cache()
        resource = self.cache.get(id_)

        if resource is None:
            url = '/{}/{}'.format(self.resource_name, id_)
            r = self.http_client.get(url)
            return r.json()

        return resource

    def _get(self, args, non_parsed):
        url = self.build_resource_url('get', args, non_parsed)
        r = self.http_client.get(url)
        return r.json()

    def get(self, args, non_parsed):
        r = self._get(args, non_parsed)
        self.formatter.print_obj(r)

    def create(self, args, non_parsed):
        url = self.build_resource_url('create', args, non_parsed)
        data = self.load_data_from_stdin()
        r = self.http_client.post(url, json=data)
        self.formatter.print_obj(r.json())

    def update(self, args, non_parsed):
        url = self.build_resource_url('update', args, non_parsed)
        data = self.load_data_from_stdin()
        r = self.http_client.patch(url, json=data)
        self.formatter.print_obj(r.json())

    def delete(self, args, non_parsed):
        url = self.build_resource_url('delete', args, non_parsed)
        self.http_client.delete(url)


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

        for h in hosts:
            for p in paths:
                self.formatter.println(h + p, indent=indent + 1)

        self.formatter.println()

    def id_getter(self, resource_name):
        r = self.http_client.get('/{}/{}'.format("routes", resource_name))
        return r.json()['id']

    def build_resource_url(self, op, args, non_parsed, **kwargs):
        if op in {'list'} and args and args.service is not None:
            return '/{}/{}/{}/'.format('services', args.service, self.resource_name)
        else:
            return super().build_resource_url(op, args, non_parsed, **kwargs)

    def create(self, args, non_parsed):
        url = self.build_resource_url('create', args, non_parsed)

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

        self.formatter.print_header("{}: {} (service {}) {}".format(resource['id'], resource['name'], service_name,
                                                                    'on' if resource['enabled'] else 'off'))
        self.formatter.print_pair('Service', service_name, indent=1)

        if route_res:
            self.formatter.print_pair('Route', '', indent=1)
            route_ref.short_formatter(route_res, indent=2)
        else:
            self.formatter.print_pair('Route', '*all*', indent=1)

    def id_getter(self, resource_name):
        r = self.http_client.get('/{}/{}'.format("plugins", resource_name))
        return r.json()['id']

    def build_resource_url(self, op, args, non_parsed, **kwargs):
        if op in {'list'} and args and args.service is not None:
            return '/{}/{}/{}/'.format('services', args.service, self.resource_name)
        elif op in {'list'} and args and args.route is not None:
            return '/{}/{}/{}/'.format('routes', args.route, self.resource_name)
        else:
            return super().build_resource_url(op, args, non_parsed, **kwargs)

    def create(self, args, non_parsed):
        url = self.build_resource_url('create', args, non_parsed)

        service_ref = ServiceResource(self.http_client, self.formatter)
        route_ref = RouteResource(self.http_client, self.formatter)

        data = self.load_data_from_stdin()

        if args.service:
            if self.version[0] < 1:
                data['service_id'] = service_ref.id_getter(args.service)
            else:
                data['service'] = {'id': service_ref.id_getter(args.service)}

        if args.route:
            if self.version[0] < 1:
                data['route_id'] = route_ref.id_getter(args.route)
            else:
                data['route'] = {'id': route_ref.id_getter(args.route)}

        r = self.http_client.post(url, json=data)
        self.formatter.print_obj(r.json())

    def build_parser(self, sb_list, sb_get, sb_create, sb_update, sb_delete):
        list_ = sb_list.add_parser(self.resource_name)
        list_.set_defaults(func=self.list)
        list_.add_argument('-s', "--service", default=None, help='Will list plugins for this service (name or id)')
        list_.add_argument('-r', "--route", default=None, help='Will list plugins for this route (name or id)')

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
        r = self.http_client.get(self.build_resource_url('list', args, non_parsed))
        data = r.json()

        for resource in data['enabled_plugins']:
            yield resource

    def build_resource_url(self, op, args=None, non_parsed=None, id_=None):
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
        url = self.build_resource_url('create', args, non_parsed)

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

    def build_resource_url(self, op, args=None, non_parsed=None, id_=None):
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


class YamlConfigResource(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'services')

    def get_list(self, args, non_parsed, resource_name):
        data = []

        if resource_name == 'routes':
            lst = RouteResource(self.http_client, self.formatter)
        elif resource_name == 'plugins':
            lst = PluginResource(self.http_client, self.formatter)
        else:
            raise RuntimeError("Unsupported resource: {}".format(resource_name))

        for resource in lst._list(args, non_parsed):
            data.append(resource)
        return data

    def id_getter(self, resource_name):
        r = self.http_client.get('/{}/{}'.format('services', resource_name))
        return r.json()['id']

    @staticmethod
    def del_config_attr(resource_type, conf):
        data = dict(conf)
        data.pop('service', None)
        data.pop('created_at', None)
        data.pop('id', None)

        if resource_type in '{route}':
            data.pop('preserve_host', None)
            data.pop('updated_at', None)
        elif resource_type in '{plugin}':
            if not data['tags']:
                data.pop('tags', None)
        return data

    @staticmethod
    def plugin_sort(plugin):
        route_name = ""
        if plugin['route']:
            if plugin['route']['name']:
                route_name = plugin['route']['name']

        return "{}-{}".format(plugin['name'], route_name)

    def get_config(self, data, args, non_parsed):
        route_res = RouteResource(self.http_client, self.formatter)

        config_obj = collections.OrderedDict()
        config_obj['services'] = list()

        service = collections.OrderedDict()
        service['name'] = data['service']['name']
        service['url'] = "{protocol}://{host}:{port}".format(**data['service'])

        service['url'] += str(data['service']['path']) if data['service']['path'] is not None else ''

        service['routes'] = list()
        for n in data['routes']:
            route = collections.OrderedDict()
            route.update(n)
            route = self.del_config_attr('route', route)
            if not route['name']:
                route['name'] = n['id']
            service['routes'].append(route)

        service['routes'] = sorted(service['routes'], key=itemgetter('name'))
        config_obj['services'].append(service)

        config_obj['plugins'] = list()
        for n in data['plugins']:
            plugin = collections.OrderedDict()
            plugin['name'] = n['name']
            plugin['route'] = n['route']

            if plugin['route']:
                args.route = plugin['route'].pop('id')
                route = route_res._get(args, non_parsed)

                plugin['route']['name'] = route['name'] if route['name'] else route['id']

            plugin['protocols'] = n['protocols']
            plugin['run_on'] = n['run_on']
            if not n['config']:
                plugin['config'] = dict()
            plugin.update(n)

            plugin = self.del_config_attr('plugin', plugin)
            config_obj['plugins'].append(plugin)

        config_obj['plugins'] = sorted(config_obj['plugins'], key=self.plugin_sort)
        return config_obj

    def get_service(self, args, non_parsed):
        data = collections.OrderedDict()
        data['service'] = self._get(args, non_parsed)
        data['routes'] = self.get_list(args, non_parsed, 'routes')
        data['plugins'] = self.get_list(args, non_parsed, 'plugins')

        return self.get_config(data, args, non_parsed)

    def get_consumer(self, args, non_parsed):
        consumer_conf = dict()
        consumer_conf['consumers'] = list()

        if args.consumer:
            consumer_list = list()
            for consumer in ConsumerResource(self.http_client, self.formatter)._list(args, non_parsed):
                if consumer['username'] == args.consumer:
                    consumer_list.append(consumer)
        else:
            consumer_list = ConsumerResource(self.http_client, self.formatter)._list(args, non_parsed)

        for consumer in consumer_list:
            data = dict()

            data['username'] = consumer['username']

            data['keyauth_credentials'] = list()
            args.consumer = data['username']
            for key in KeyAuthResource(self.http_client, self.formatter)._list(args, non_parsed):
                data['keyauth_credentials'].append({"key": key['key']})

            consumer_conf['consumers'].append(data)

        return consumer_conf

    def get_plugin(self, args, non_parsed):
        args.list_full = None
        plugins = PluginResource(self.http_client, self.formatter)._list(args, non_parsed)
        data = list()

        for plug in plugins:
            if not plug['service'] and not plug['route']:
                data.append(plug)

        return data

    def yaml_consumer(self, args, non_parsed):
        self.formatter.print_obj(self.get_consumer(args, non_parsed))

    def yaml_service(self, args, non_parsed):
        self._header()
        self.formatter.print_obj(self.get_service(args, non_parsed))

    def yaml_plugin(self, args, non_parsed):
        self.formatter.print_obj(self.get_plugin(args, non_parsed))

    def dump_service(self, args, non_parsed):
        path = './config/services/'
        data = dict()

        if args.service:
            service_list = list()
            for i in ServiceResource(self.http_client, self.formatter)._list(args, non_parsed):
                if i['name'] == args.service or i['id'] == args.service:
                    service_list.append(i)
        else:
            service_list = ServiceResource(self.http_client, self.formatter)._list(args, non_parsed)

        if not os.path.isdir(path):
            os.makedirs(path)

        for service in service_list:
            args.service = service['name']
            file_path = path + args.service + '.yml'
            file = open(file_path, 'w')
            conf_service = self.get_service(args, non_parsed)
            self._header(file)
            YamlOutputFormatter(file).print_obj(conf_service)

    def dump_consumer(self, args, non_parsed):
        path = './config/consumers/'
        if not os.path.isdir(path):
            os.makedirs(path)

        consumer = self.get_consumer(args, non_parsed)
        if not args.consumer:
            file_name = args.consumer
        else:
            file_name = 'consumers'

        file_path = path + file_name + '.yml'
        file = open(file_path, 'w')
        YamlOutputFormatter(file).print_obj(consumer)

    def dump_plugin(self, args, non_parsed):
        plugins = self.get_plugin(args, non_parsed)

        if plugins:
            path = './config/plugins/'
            if not os.path.isdir(path):
                os.makedirs(path)
            file_path = path + 'plugins.yml'
            file = open(file_path, 'w')
            YamlOutputFormatter(file).print_obj(plugins)

    def build_parser(self, sb_config):
        service_config = sb_config.add_parser('service')
        service_config.set_defaults(func=self.yaml_service)
        service_config.add_argument("service", help='service id {username or id}')

        consumer_config = sb_config.add_parser('consumer')
        consumer_config.set_defaults(func=self.yaml_consumer)
        consumer_config.add_argument("consumer", default=None, nargs='?', help='consumer id {username or id}')

        plugin_config = sb_config.add_parser('plugin')
        plugin_config.set_defaults(func=self.yaml_plugin)
        # @TODO: ambigous arguments.. should be deleted
        plugin_config.add_argument("-s", "--service", default=None, nargs='?',
                                   help='service id or None {username or id}')
        plugin_config.add_argument("-r", "--route", default=None, nargs='?', help='route id or None {username or id}')

        dump = sb_config.add_parser('dump')
        sb_dump = dump.add_subparsers()

        dump_plugins = sb_dump.add_parser('plugin')
        dump_plugins.set_defaults(func=self.dump_plugin)
        dump_plugins.add_argument("-s", "--service", default=None, nargs='?',
                                  help='service id or None {username or id}')
        dump_plugins.add_argument("-r", "--route", default=None, nargs='?', help='route id or None {username or id}')

        dump_service = sb_dump.add_parser('service')
        dump_service.set_defaults(func=self.dump_service)
        dump_service.add_argument("service", default=None, nargs='?', help='service id or None {username or id}')

        dump_consumer = sb_dump.add_parser('consumer')
        dump_consumer.set_defaults(func=self.dump_consumer)
        dump_consumer.add_argument("consumer", default=None, nargs='?', help='consumer id or None {username or id}')

    @staticmethod
    def _header(file=sys.stdout):
        file.write('_format_version: \"1.1\"')
        file.write('\n\n')


class EnsureResource(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'services')

    def id_plugin_route(self, plugin, args, non_parsed):
        if plugin['route']:
            current_routes = RouteResource(self.http_client, self.formatter)._list(args, non_parsed)
            for route in current_routes:
                if route['name'] == plugin['route']['name']:
                    return route['id']

        raise RuntimeError("Can't find such route {}".format(plugin['route']['name']))

    def service_update(self, data, args, non_parsed):
        service_res = ServiceResource(self.http_client, self.formatter)

        args.service = data['name']

        url = service_res.build_resource_url('create')
        try:
            current_service = service_res._get(args, non_parsed)
        except RuntimeError:
            current_service = None

        if current_service:
            if current_service['name'] == data['name']:
                url += '/' + service_res.id_getter(data['name'])

                old_url = "{protocol}://{host}:{port}".format(**current_service)
                old_url += str(current_service['path']) if current_service['path'] is not None else ''
                if old_url == data['url']:
                    return url
                self.http_client.patch(url, data=data)
                return url

        self.http_client.post(url, data=data)
        return url + '/' + service_res.id_getter(data['name'])

    @staticmethod
    def find_route_url(current_routes, route_name):
        for old in current_routes:
            if old['name'] == route_name:
                return '/routes/' + old['id']
        return None

    def route_update(self, routes, url, args, non_parsed):
        route_res = RouteResource(self.http_client, self.formatter)
        yaml_res = YamlConfigResource(self.http_client, self.formatter)

        current_routes = list(route_res._list(args, non_parsed))
        ident_list = list()
        old_list = list()
        for new in routes:
            for old in current_routes:
                if new['name'] == old['name'] not in old_list:
                    old_list.append(old['name'])
                cmp = yaml_res.del_config_attr('route', old)
                if json.dumps(new, sort_keys=True) == json.dumps(cmp, sort_keys=True):
                    ident_list.append(old['name'])

        for old in current_routes:
            if old['name'] not in old_list:
                args.route = old['id']
                route_res.delete(args, non_parsed)

        for new in routes:
            if new['name'] in ident_list:
                continue

            if new['name'] in old_list:
                route_id = self.find_route_url(current_routes, new['name'])

                if route_id is None:
                    raise RuntimeError("Can't find old route: {}".format(new['name']))

                self.http_client.patch(route_id, json=new)
            else:
                self.http_client.post(url, json=new)

    @staticmethod
    def find_plugin_url(current_plugins, plugin_name):
        for old in current_plugins:
            if old['name'] == plugin_name:
                return '/plugins/' + old['id']
        return None

    def plugin_update(self, plugins, url, args, non_parsed):
        plugin_res = PluginResource(self.http_client, self.formatter)
        yaml_res = YamlConfigResource(self.http_client, self.formatter)

        current_plugins = list(plugin_res._list(args, non_parsed))

        ident_list = list()
        old_list = list()
        for new in plugins:
            if new['route']:
                new['route']['id'] = self.id_plugin_route(new, args, non_parsed)
                new['route'].pop('name', None)
            for old in current_plugins:
                if old['name'] == new['name'] not in old_list:
                    old_list.append(old['name'])
                cmp = yaml_res.del_config_attr('plugin', old)
                if json.dumps(cmp, sort_keys=True) == json.dumps(new, sort_keys=True):
                    ident_list.append(old['name'])

        for old in current_plugins:
            if old['name'] not in old_list:
                args.plugin = old['id']
                plugin_res.delete(args, non_parsed)

        for new in plugins:
            if new['name'] in ident_list:
                continue

            if new['name'] in old_list:
                plugin_id = self.find_plugin_url(current_plugins, new['name'])

                if plugin_id is None:
                    raise RuntimeError("Can't find old plugin: {}".format(new['name']))

                self.http_client.patch(plugin_id, json=new)
            else:
                self.http_client.post(url, json=new)

    def service_required(self, conf, args, non_parsed):
        service = conf['services'][0]
        routes = service['routes']
        plugins = conf['plugins']

        data = dict()
        data['name'] = service['name']
        data['url'] = service['url']

        url = self.service_update(data, args, non_parsed)
        self.route_update(routes, url + '/routes', args, non_parsed)
        self.plugin_update(plugins, url + '/plugins', args, non_parsed)

    def plugin_required(self, conf, args, non_parsed):
        plugin_res = PluginResource(self.http_client, self.formatter)

        url = plugin_res.build_resource_url('create', args, non_parsed) + '/'
        for plugin in conf:
            self.http_client.put(url + plugin['id'], json=plugin)

    def consumer_required(self, conf, args, non_parsed):
        consumer_res = ConsumerResource(self.http_client, self.formatter)
        consumers = conf['consumers']

        url = consumer_res.build_resource_url('create', args, non_parsed) + '/'
        for consumer in consumers:
            user = dict()
            key = dict()

            user['username'] = consumer['username']
            self.http_client.put(url + consumer['username'], json=user)
            if consumer['keyauth_credentials']:
                key['key'] = consumer['keyauth_credentials'][0]['key']
                self.http_client.put(url + consumer['username'] + '/key-auth/' + key['key'], json=key)

    def get_yaml_file(self, args, non_parsed):
        folder = list()
        if os.path.isdir(args.path):
            folder = os.listdir(args.path)
            os.chdir(args.path)
        else:
            folder.append(args.path)

        for dr in folder:
            sub_dr = os.listdir(dr)
            for file in sub_dr:
                print(file)
                f = open(dr + '/' + file, 'r')
                conf = yaml.safe_load(f.read())
                if dr in '{services}':
                    self.service_required(conf, args, non_parsed)
                elif dr in '{plugins}':
                    self.plugin_required(conf, args, non_parsed)
                elif dr in '{consumers}':
                    self.consumer_required(conf, args, non_parsed)

    def build_parser(self, ensure):
        ensure.set_defaults(func=self.get_yaml_file)
        ensure.add_argument('path', help='directory yaml config')
