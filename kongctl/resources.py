import json
import sys
import collections
import os
import yaml
from .yaml_formatter import YamlOutputFormatter

_get_verison = None
def get_version(http_client):
    global _get_verison
    if _get_verison != None:
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

    def _get(self, args, non_parsed):
        url = self._build_resource_url('get', args, non_parsed)
        r = self.http_client.get(url)
        return r.json()

    def get(self, args, non_parsed):
        r = self._get(args, non_parsed)
        self.formatter.print_obj(r)

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
        elif op in {'list'} and args and args.route is not None:
            return '/{}/{}/{}/'.format('routes', args.route, self.resource_name)
        else:
            return super()._build_resource_url(op, args, non_parsed, **kwargs)

    def create(self, args, non_parsed):
        url = self._build_resource_url('create', args, non_parsed)

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

        self.formatter.print_obj(data)
        print(url)
        r = self.http_client.post(url, json=data)


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


class YamlConfigResource(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'services')

    def get_list(self, args, non_parsed, resource_name):
        data = []

        if resource_name == 'routes':
            lst = RouteResource(self.http_client, self.formatter)
        elif resource_name == 'plugins':
            lst = PluginResource(self.http_client, self.formatter)

        for resource in lst._list(args, non_parsed):
            data.append(resource)
        return data

    def id_getter(self, resource_name):
        r = self.http_client.get('/{}/{}'.format('services', resource_name))
        return r.json()['id']

    def get_config(self, data):
        config_obj = collections.OrderedDict()
        config_obj['services'] = list()

        service = collections.OrderedDict()
        service['name'] = data['service']['name']
        service['url'] = "{protocol}://{host}:{port}".format(**data['service'])

        service['url'] += str(data['service']['path']) if data['service']['path'] != None else ''

        service['routes'] = list()
        for n in data['routes']:
            route = collections.OrderedDict()
            route['name'] = n['id']
            if n['paths']:
                route['paths'] = n['paths']
            service['routes'].append(route)

        config_obj['services'].append(service)

        config_obj['plugins'] = list()
        for n in data['plugins']:
            plugin = collections.OrderedDict()
            plugin['name'] = n['name']
            # plugin['route'] = n['route']
            plugin['protocols'] = n['protocols']
            plugin['run_on'] = n['run_on']
            if n['config']:
                plugin['config'] = n['config']
            config_obj['plugins'].append(plugin)

        return config_obj

    def get_service(self, args, non_parsed):
        data = dict()
        data['service'] = self._get(args, non_parsed)
        data['routes'] = self.get_list(args, non_parsed, 'routes')
        data['plugins'] = self.get_list(args, non_parsed, 'plugins')

        return self.get_config(data)

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
            key = dict()
            args.consumer = data['username']
            for n in KeyAuthResource(self.http_client, self.formatter)._list(args, non_parsed):
                key['key'] = n['key']
                data['keyauth_credentials'].append(key)

            consumer_conf['consumers'].append(data)

        return consumer_conf

    def yaml_consumer(self, args, non_parsed):
        self.formatter.print_obj(self.get_consumer(args, non_parsed))

    def yaml_service(self, args, non_parsed):
        self._header()
        self.formatter.print_obj(self.get_service(args, non_parsed))

    def dump_service(self, args, non_parsed):
        path = './services/'
        data = dict()

        if args.service:
            service_list = list()
            for i in ServiceResource(self.http_client, self.formatter)._list(args, non_parsed):
                if i['name'] == args.service or i['id'] == args.service:
                    service_list.append(i)
        else:
            service_list = ServiceResource(self.http_client, self.formatter)._list(args, non_parsed)

        if not os.path.isdir(path):
            os.mkdir(path)

        for service in service_list:
            args.service = service['name']
            file_path = path + args.service + '.yml'
            file = open(file_path, 'w')
            conf_service = self.get_service(args, non_parsed)
            self._header(file)
            YamlOutputFormatter(file).print_obj(conf_service)

    def dump_consumer(self, args, non_parsed):
        path = './consumers/'
        if not os.path.isdir(path):
            os.mkdir(path)

        consumer = self.get_consumer(args, non_parsed)
        if not args.consumer:
            file_name = args.consumer
        else:
            file_name = 'consumers'

        file_path = path + file_name + '.yml'
        file = open(file_path, 'w')
        YamlOutputFormatter(file).print_obj(consumer)

    def build_parser(self, sb_config):
        service_config = sb_config.add_parser('service')
        service_config.set_defaults(func=self.yaml_service)
        service_config.add_argument("service", help='service id {username or id}')

        consumer_config = sb_config.add_parser('consumer')
        consumer_config.set_defaults(func=self.yaml_consumer)
        consumer_config.add_argument("consumer", default=None, nargs='?', help='consumer id {username or id}')

        dump = sb_config.add_parser('dump')
        sb_dump = dump.add_subparsers()

        dump_service = sb_dump.add_parser('service')
        dump_service.set_defaults(func=self.dump_service)
        dump_service.add_argument("service", default=None, nargs='?', help='service id or None {username or id}')

        dump_consumer = sb_dump.add_parser('consumer')
        dump_consumer.set_defaults(func=self.dump_consumer)
        dump_consumer.add_argument("consumer", default=None, nargs='?', help='consumer id or None {username or id}')

    def _header(self, file=sys.stdout):
        print('_format_version: \"1.1\"', file=file)
        print(file=file)

class EnsureResource(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'services')

    def service_check_update(self, data, args, non_parsed):
        service_res = ServiceResource(self.http_client, self.formatter)

        args.service = data['name']
        current_service = service_res._list(args, non_parsed)

        status = 'create'
        for old in current_service:
            if old['name'] == data['name']:
                status = 'change'

                old_url = "{protocol}://{host}:{port}".format(**old)
                old_url += str(old['path']) if old['path'] != None else ''
                if old_url == data['url']:
                    return 'break'
        return status

    def route_update(self, routes, url, args, non_parsed):
        route_res = RouteResource(self.http_client, self.formatter)

        current_routes = list(route_res._list(args, non_parsed))
        ident_list = list()
        old_list = list()
        for new in routes:
            for old in current_routes:
                if old['name'] not in old_list:
                    old_list.append(old['name'])
                if new['name'] == old['name']:
                    if 'paths' in old and 'paths' in new and old['paths'] == new['paths']:
                        ident_list.append(old['name'])

        for new in routes:
            if new['name'] not in ident_list and 'paths' in new:
                if new['name'] in old_list:
                    for old in current_routes:
                        if old['name'] == new['name']:
                            route_id = '/routes/' + old['id']
                    self.http_client.patch(route_id, data=new)
                else:
                    self.http_client.post(url, data=new)

    def plugin_update(self, plugins, url, args, non_parsed):
        plugin_res = PluginResource(self.http_client, self.formatter)

        current_plugins = list(plugin_res._list(args, non_parsed))
        ident_list = list()
        old_list = list()
        for new in plugins:
            for old in current_plugins:
                if old['name'] not in old_list:
                    old_list.append(old['name'])
                if new['name'] == old['name'] and old['protocols'] == new['protocols'] and old['run_on'] == new['run_on']:
                    if 'config' in new and 'config' in old:
                        if json.dumps(old['config'], sort_keys=True) == json.dumps(new['config'], sort_keys=True):
                            ident_list.append(old['name'])

        for new in plugins:
            if new['name'] not in ident_list:
                if new['name'] in old_list:
                    for old in current_plugins:
                        if old['name'] == new['name']:
                            plugin_id = '/' + old['id']
                    self.http_client.patch(url + plugin_id, json=new)
                else:
                    self.http_client.post(url, json=new)

    def prepare_required(self, conf, args, non_parsed):
        service = conf['services'][0]
        plugins = conf['plugins']

        data = dict()
        data['name'] = service['name']
        data['url'] = service['url']

        url = self._build_resource_url('create')
        service_status = self.service_check_update(data, args, non_parsed)

        if service_status in {'change'}:
            self.http_client.patch(url + '/' + ServiceResource(self.http_client, self.formatter).id_getter(data['name']), data=data)
        elif service_status in {'create'}:
            self.http_client.post(self._build_resource_url('create'), data=data)

        url += '/' + ServiceResource(self.http_client, self.formatter).id_getter(data['name'])
        self.route_update(service['routes'], url + '/routes', args, non_parsed)
        self.plugin_update(plugins, url + '/plugins', args, non_parsed)

    def get_yaml_file(self, args, non_parsed):
        files = list()
        if os.path.isdir(args.path):
            files = os.listdir(args.path)
            os.chdir(args.path)
        else:
            files.append(args.path)

        for file in files:
            if os.path.isfile(file):
                print(file)
                f = open(file, 'r')
                conf = yaml.safe_load(f.read())
                self.prepare_required(conf, args, non_parsed)

    def build_parser(self, ensure):
        ensure.set_defaults(func=self.get_yaml_file)
        ensure.add_argument('path', help='file or directory yaml config')