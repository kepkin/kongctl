import json
import sys
import collections
import os
import yaml
import re
import uuid

from .yaml_formatter import YamlOutputFormatter
from operator import itemgetter
from urllib.parse import urlparse
from .resource_error import *

_get_verison = None


def get_version(http_client):
    global _get_verison
    if _get_verison is not None:
        return _get_verison

    r = http_client.get('/')
    data = r.json()
    _get_verison = tuple(map(int, data['version'].split('.')))
    return _get_verison


def chain_key_get(d, *keys):
    for key in keys:
        v = d
        for key_part in key.split('.'):
            if not isinstance(v, dict):
                break

            v = v.get(key_part)

        if v:
            return v

    return None


class BaseResource(object):
    def __init__(self, http_client_factory, formatter_factory, resource_name):
        self.resource_name = resource_name
        self.cache = dict()
        self.http_client_factory = http_client_factory
        self.formatter_factory = formatter_factory
        self.cache_http_client = None
        self.cache_formatter = None
        self.cache_logger = None

    @property
    def formatter(self):
        if self.cache_formatter is not None:
            return self.cache_formatter
        self.cache_formatter = self.formatter_factory()
        return self.cache_formatter

    @property
    def logger(self):
        if self.cache_logger is not None:
            return self.cache_logger
        self.cache_logger = self.http_client.get_logger()
        return self.cache_logger

    @property
    def http_client(self):
        if self.cache_http_client is not None:
            return self.cache_http_client
        self.cache_http_client = self.http_client_factory()
        return self.cache_http_client

    @property
    def version(self):
        return get_version(self.http_client)

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

    def _list(self, args, non_parsed, **kwargs):
        next_url = kwargs.get('next_url', None)
        if next_url is None:
            next_url = self.build_resource_url('list', args, non_parsed)

        while next_url:
            r = self.http_client.get(next_url)
            data = r.json()
            next_url = data.get('next', None)

            for resource in data['data']:
                if 'name' in resource and 'id' in resource:
                    self.cache[resource['id']] = resource
                yield resource

    def list(self, args, non_parsed, **kwargs):
        list_ = kwargs.get('list', self._list(args, non_parsed))

        for resource in list_:
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
        try:
            url = self.build_resource_url('get', args, non_parsed)
            r = self.http_client.get(url)
            return r.json()
        except RuntimeError as e:
            raise GetError(args, self.resource_name[:-1], e)

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

    def recursive_delete(self, args, non_parsed):
        url = '/services/' + args.service
        plugin_res = PluginResource(self.http_client_factory, self.formatter_factory)
        route_res = RouteResource(self.http_client_factory, self.formatter_factory)

        plugins = list(plugin_res._list(args, non_parsed))
        routes = list(route_res._list(args, non_parsed))

        plugin_url = url + '/plugins/'
        for plugin in plugins:
            self.http_client.delete(plugin_url + plugin['id'])
            self.logger.info("Deleted plugin: name - {}, id - {} ".format(plugin['name'], plugin['id']))

        route_url = '/routes/'
        for route in routes:
            self.http_client.delete(route_url + route['id'])
            self.logger.info("Deleted route: name - {}, id - {} ".format(route['name'], route['id']))

        self.http_client.delete(url)
        self.logger.info("Deleted service: {}".format(args.service))

    def delete(self, args, non_parsed):
        try:
            if self.resource_name in '{services}' and args.recursive:
                self.recursive_delete(args, non_parsed)
            else:
                url = self.build_resource_url('delete', args, non_parsed)
                self.http_client.delete(url)
        except RuntimeError as e:
            raise DeleteError(args, self.resource_name[:-1], e)


class ServiceResource(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'services')

    def build_resource_url(self, op, args, non_parsed, **kwargs):
        if op in {'list'} and args and args.tag is not None:
            return '/{}?tags={}'.format(self.resource_name, args.tag)
        else:
            return super().build_resource_url(op, args, non_parsed, **kwargs)

    def _list(self, args, non_parsed, **kwargs):
        next_url = self.build_resource_url('list', args, non_parsed)
        return super()._list(args, non_parsed, next_url=next_url)

    def list(self, args, non_parsed, **kwargs):
        return super().list(args, non_parsed, list=self._list(args, non_parsed))

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
        list_.add_argument("-t", "--tag", help="List services where exist this tag")

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
        delete.add_argument("-r", "--recursive", default=False, action='store_true', help="Recursive delete")
        delete.add_argument("service", help='service id')


class RouteResource(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'routes')

    def short_formatter(self, resource, indent=0):
        hosts = resource.get('hosts', None) or ['*']
        paths = resource.get('paths', None) or ['/']

        ref = ServiceResource(self.http_client_factory, self.formatter_factory)
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

        ref = ServiceResource(self.http_client_factory, self.formatter_factory)
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
        return chain_key_get(d, *keys)

    def short_formatter(self, resource):
        service_name = '*all*'
        route_res = None
        service_id = self._chain_key_get(resource, 'service.id', 'service_id')
        if service_id:
            ref = ServiceResource(self.http_client_factory, self.formatter_factory)
            service_name = ref.get_by_id(service_id)['name']

        route_ref = RouteResource(self.http_client_factory, self.formatter_factory)
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

        service_ref = ServiceResource(self.http_client_factory, self.formatter_factory)
        route_ref = RouteResource(self.http_client_factory, self.formatter_factory)

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
        print("qq" * 20)
        r = self.http_client.get(self.build_resource_url('list', args, non_parsed))
        print("qq" * 20)
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


class JwtSecrets(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'jwt')

    def build_resource_url(self, op, args=None, non_parsed=None, id_=None):
        if op == 'get_by_id':
            raise NotImplemented()
        elif op == 'list':
            return '/consumers/{}/{}/'.format(args.consumer, self.resource_name)
        elif op in {'get', 'update', 'delete'}:
            return '/consumers/{}/{}/{}'.format(args.consumer, self.resource_name, args.jwt)
        elif op in {'create'}:
            return '/consumers/{}/{}/'.format(args.consumer, self.resource_name)

    def short_formatter(self, resource):
        self.formatter.print_pair('id', resource['id'])
        self.formatter.print_pair('key', resource['key'], indent=1)
        self.formatter.print_pair('secret', resource['secret'], indent=1)
        self.formatter.println()

    def id_getter(self, resource_name):
        raise NotImplemented()

    def build_parser(self, sb_list, sb_get, sb_create, sb_update, sb_delete):
        list_ = sb_list.add_parser(self.resource_name)
        list_.set_defaults(func=self.list)
        list_.add_argument("consumer", help='consumer id {username or id}')

        get = sb_get.add_parser(self.resource_name)
        get.set_defaults(func=self.get)
        get.add_argument("consumer", help='consumer id {username or id}')
        get.add_argument("jwt", help='id of jwt')

        create = sb_create.add_parser(self.resource_name)
        create.add_argument("consumer", help='Will apply plugin data to this consumer {username or id}')
        create.set_defaults(func=self.create)

        update = sb_update.add_parser(self.resource_name)
        update.set_defaults(func=self.update)
        update.add_argument("consumer", help='Will apply plugin data to this consumer {username or id}')
        update.add_argument("jwt", help='id of jwt')

        delete = sb_delete.add_parser(self.resource_name)
        delete.set_defaults(func=self.delete)
        delete.add_argument("consumer", help='consumer id {username or id}')
        delete.add_argument("jwt", help='id of jwt')


class YamlConfigResource(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'services')

    def get_list(self, args, non_parsed, resource_name):
        data = []

        if resource_name == 'routes':
            lst = RouteResource(self.http_client_factory, self.formatter_factory)
        elif resource_name == 'plugins':
            lst = PluginResource(self.http_client_factory, self.formatter_factory)
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
            if not data.get('tags'):
                data.pop('tags', None)
            if data.get('route') is None:
                data.pop('route', None)
        elif resource_type in '{jwt}':
            data.pop('consumer', None)
        return data

    @staticmethod
    def plugin_sort(plugin):
        route_name = ""
        if plugin.get('route'):
            if 'name' in plugin['route']:
                route_name = plugin['route']['name']

        return "{}-{}".format(plugin['name'], route_name)

    @staticmethod
    def is_valid_uuid(val):
        try:
            uuid.UUID(str(val))
            return True
        except ValueError:
            return False

    def get_config(self, data, args, non_parsed):
        route_res = RouteResource(self.http_client_factory, self.formatter_factory)

        config_obj = collections.OrderedDict()
        config_obj['services'] = list()

        service = collections.OrderedDict()
        service['name'] = data['service']['name']
        service['url'] = "{protocol}://{host}:{port}".format(**data['service'])

        service['url'] += str(data['service'].get('path')) if data['service'].get('path') is not None else ''

        self.logger.info('Config service: {}'.format(service['name']))

        service['routes'] = list()
        for n in data['routes']:
            route = collections.OrderedDict()
            route.update(n)
            route = self.del_config_attr('route', route)
            if 'name' not in route:
                route['name'] = n['id']
            if self.is_valid_uuid(route['name']):
                route['name'] += '_route'
            self.logger.info('Route: {}'.format(route['name']))
            service['routes'].append(route)

        service['routes'] = sorted(service['routes'], key=itemgetter('name'))

        service['plugins'] = list()
        for n in data['plugins']:
            plugin = collections.OrderedDict()
            plugin['name'] = n['name']
            plugin.update(n)
            route_id = chain_key_get(n, 'route.id', 'route_id')
            if route_id is not None:
                plugin['route'] = {'id': route_id}
            else:
                plugin['route'] = None

            if plugin.get('route'):
                args.route = plugin['route'].pop('id')
                route = route_res._get(args, non_parsed)

                plugin['route']['name'] = route.get('name', route['id'])
                if self.is_valid_uuid(plugin['route']['name']):
                    plugin['route']['name'] += '_route'

            plugin['protocols'] = n.get('protocols')
            plugin['run_on'] = n.get('run_on', 'first')
            if 'config' not in n:
                plugin['config'] = dict()
            else:
                plugin['config'] = n['config']

            plugin = self.del_config_attr('plugin', plugin)
            self.logger.info('Plugin: {}'.format(plugin['name']))
            service['plugins'].append(plugin)

        service['plugins'] = sorted(service['plugins'], key=self.plugin_sort)
        config_obj['services'].append(service)

        return config_obj

    def get_service(self, args, non_parsed):
        data = collections.OrderedDict()

        try:
            data['service'] = self._get(args, non_parsed)
        except GetError as e:
            raise ConfigGetError(e)

        data['routes'] = self.get_list(args, non_parsed, 'routes')
        data['plugins'] = self.get_list(args, non_parsed, 'plugins')

        return self.get_config(data, args, non_parsed)

    def get_consumer(self, args, non_parsed):
        self.logger.info('Processing consumers')
        consumer_res = ConsumerResource(self.http_client_factory, self.formatter_factory)
        key_auth_res = KeyAuthResource(self.http_client_factory, self.formatter_factory)
        jwt_res = JwtSecrets(self.http_client_factory, self.formatter_factory)
        consumer_conf = dict()
        consumer_conf['consumers'] = list()

        if args.consumer:
            consumer_list = list()
            for consumer in consumer_res._list(args, non_parsed):
                if consumer['username'] == args.consumer:
                    consumer_list.append(consumer)
        else:
            consumer_list = consumer_res._list(args, non_parsed)

        for consumer in consumer_list:
            data = dict()

            data['username'] = consumer['username']

            self.logger.info('Consumer: {}'.format(data['username']))
            data['keyauth_credentials'] = list()
            args.consumer = data['username']
            for key in key_auth_res._list(args, non_parsed):
                self.logger.info('Key: {}'.format(key['key']))
                data['keyauth_credentials'].append({"key": key['key']})

            for jwt in jwt_res._list(args, non_parsed):
                if not data.get('jwt_secrets'):
                    data['jwt_secrets'] = list()
                self.logger.info('jwt: key - {}'.format(jwt['key']))
                val = self.del_config_attr('jwt', jwt)
                data['jwt_secrets'].append(val)

            consumer_conf['consumers'].append(data)

        return consumer_conf

    def get_plugin(self, args, non_parsed):
        self.logger.info('Processing plugins')
        args.list_full = None
        plugins = PluginResource(self.http_client_factory, self.formatter_factory)._list(args, non_parsed)
        data = list()

        for plug in plugins:
            service_id = chain_key_get(plug, 'service.id', 'service_id')
            route_id = chain_key_get(plug, 'route.id', 'route_id')
            if not service_id and not route_id:
                self.logger.info('Plugin: {}'.format(plug['name']))
                data.append(plug)

        return data

    def yaml_consumer(self, args, non_parsed):
        self.logger.debug("Print output consumers.yaml file")
        self.formatter.print_obj(self.get_consumer(args, non_parsed))

    def yaml_service(self, args, non_parsed):
        self.logger.debug("Print output config.yaml file")
        conf_service = self.get_service(args, non_parsed)
        self._header()
        self.formatter.print_obj(conf_service)

    def yaml_service_group(self, args, non_parsed):
        service_res = ServiceResource(self.http_client_factory, self.formatter_factory)

        args.tag = args.group_name

        service_list = service_res._list(args, non_parsed)

        config = {
            'service_group': args.group_name,
            'services': [],
        }
        for service in service_list:
            args.service = service['name']

            current_service = self.get_service(args, non_parsed)

            # Берем 0 элемент т.к. get_service возвращает только один сервис
            config['services'].append(current_service['services'][0])

        self._header()
        self.formatter.print_obj(config)

    def yaml_plugin(self, args, non_parsed):
        self.logger.debug("Print output plugins.yaml file")
        self.formatter.print_obj(self.get_plugin(args, non_parsed))

    def dump_service(self, args, non_parsed):
        service_res = ServiceResource(self.http_client_factory, self.formatter_factory)
        path = './config/services/'
        data = dict()

        if args.service:
            service_list = list()
            for service in service_res._list(args, non_parsed):
                if service['name'] == args.service or service['id'] == args.service:
                    service_list.append(service)
            if not service_list:
                raise DumpServiceError(args)
        else:
            service_list = service_res._list(args, non_parsed)

        if not os.path.isdir(path):
            os.makedirs(path)

        for service in service_list:
            args.service = service['name']
            self.logger.info("Processing: {}".format(service['name']))
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
        service_config = sb_config.add_parser('service',
                                              description='Service its routes and plugins print config file in stdout.')
        service_config.set_defaults(func=self.yaml_service)
        service_config.add_argument("service", help='service id {username or id}')

        service_group_config = sb_config.add_parser('serviceGroup',
                                                    description='Service its routes and plugins print config file in '
                                                                'stdout by group name.')
        service_group_config.set_defaults(func=self.yaml_service_group)
        service_group_config.add_argument("group_name", default=None, nargs='?', help='service group name')

        consumer_config = sb_config.add_parser('consumer',
                                               description='Consumers and their key-auth print config file in stdout.')
        consumer_config.set_defaults(func=self.yaml_consumer)
        consumer_config.add_argument("consumer", default=None, nargs='?', help='consumer id {username or id}')

        plugin_config = sb_config.add_parser('plugin',
                                             description='Plugins not connected to services and routes print config '
                                                         'file in stdout.')
        plugin_config.set_defaults(func=self.yaml_plugin)
        # @TODO: ambigous arguments.. should be deleted
        plugin_config.add_argument("-s", "--service", default=None, nargs='?',
                                   help='service id or None {username or id}')
        plugin_config.add_argument("-r", "--route", default=None, nargs='?', help='route id or None {username or id}')

        dump = sb_config.add_parser('dump', description='Dump config file')
        sb_dump = dump.add_subparsers()

        dump_plugins = sb_dump.add_parser('plugin', description='Plugins not connected to services and routes dump in '
                                                                'config file.')
        dump_plugins.set_defaults(func=self.dump_plugin)
        dump_plugins.add_argument("-s", "--service", default=None, nargs='?',
                                  help='service id or None {username or id}')
        dump_plugins.add_argument("-r", "--route", default=None, nargs='?', help='route id or None {username or id}')

        dump_service = sb_dump.add_parser('service', description='Service its routes and plugins dump in config file. '
                                                                 'If id not received will be dump all services with '
                                                                 'server.')
        dump_service.set_defaults(func=self.dump_service)
        dump_service.add_argument("service", default=None, nargs='?', help='service id or None {username or id}')

        dump_consumer = sb_dump.add_parser('consumer', description='Consumers and their key-auth dump in config file.')
        dump_consumer.set_defaults(func=self.dump_consumer)
        dump_consumer.add_argument("consumer", default=None, nargs='?', help='consumer id or None {username or id}')

    def _header(self, file=sys.stdout):
        file.write('_format_version: \"{}\"'.format(".".join(map(str, self.version))))
        file.write('\n\n')


class EnsureResource(BaseResource):
    def __init__(self, http_client, formatter, var_map):
        super().__init__(http_client, formatter, 'services')
        self.var_map = var_map

    def id_plugin_route(self, plugin, args, non_parsed):
        if plugin['route']:
            current_routes = RouteResource(self.http_client_factory, self.formatter_factory)._list(args, non_parsed)
            for route in current_routes:
                if route['name'] == plugin['route']['name']:
                    return route['id']

        raise RuntimeError("Can't find such route {}".format(plugin['route']['name']))

    def remove_missing_services_from_service_group(self, service_group, services, args, non_parsed):
        if service_group is None:
            return

        service_res = ServiceResource(self.http_client_factory, self.formatter_factory)

        args.tag = service_group

        service_list = service_res._list(args, non_parsed)

        service_names = [service['name'] for service in services]
        for service in service_list:
            if service['name'] not in service_names:
                self.logger.info(
                    "Recursive delete service {} from service_group {}".format(service['name'], service_group))

                args.service = service['name']
                service_res.recursive_delete(args, non_parsed)

        return

    def service_update(self, service_group, data, args, non_parsed):
        self.logger.info("Create or patch service: {}".format(data['name']))
        service_res = ServiceResource(self.http_client_factory, self.formatter_factory)

        args.service = data['name']

        url = service_res.build_resource_url('create', args, non_parsed)
        try:
            current_service = service_res._get(args, non_parsed)
        except GetError:
            current_service = None

        if current_service:
            if current_service['name'] == data['name']:
                url += '/' + service_res.id_getter(data['name'])

                old_url = "{protocol}://{host}:{port}".format(**current_service)
                old_url += str(current_service['path']) if current_service['path'] is not None else ''

                service = dict()
                current_tags = current_service['tags'] if current_service['tags'] else [None]
                if service_group not in current_tags:
                    service['tags'] = service_group if service_group else ''
                elif old_url == data['url']:
                    return url

                u = urlparse(data['url'])

                service['name'] = data['name']
                service['protocol'] = u.scheme
                service['host'] = u.netloc.replace(":" + str(u.port), '')
                service['path'] = u.path
                service['port'] = u.port

                self.http_client.patch(url, data=service)
                return url

        data['tags'] = service_group if service_group else ''
        self.http_client.post(url, data=data)
        return url + '/' + service_res.id_getter(data['name'])

    @staticmethod
    def find_route_url(current_routes, route_name):
        for old in current_routes:
            if old['name'] == route_name:
                return '/routes/' + old['id']
        return None

    def route_update(self, routes, args, non_parsed):
        route_res = RouteResource(self.http_client_factory, self.formatter_factory)
        service_res = ServiceResource(self.http_client_factory, self.formatter_factory)

        current_routes = list(route_res._list(args, non_parsed))
        old_list = list()
        for new in routes:
            try:
                self.logger.info("Route: {}".format(new['name']))
            except KeyError:
                raise KeyError("In route missing field \'name\'")

            for old in current_routes:
                if new['name'] == old['name'] not in old_list:
                    old_list.append(old['name'])

        for old in current_routes:
            if old['name'] not in old_list:
                args.route = old['id']
                route_res.delete(args, non_parsed)

        service_id = service_res.id_getter(args.service)
        for new in routes:
            new['service'] = {"id": service_id}
            self.http_client.put('/routes/' + new['name'], json=new)

    @staticmethod
    def find_plugin_url(current_plugins, plugin_name):
        for old in current_plugins:
            if old['name'] == plugin_name:
                return '/plugins/' + old['id']
        return None

    def var_map_insert_config(self, config):
        for k, v in self.var_map.items():
            vv = json.dumps(v)
            config = config.replace('${{{}}}'.format(k), vv)
        return config

    def plugin_update(self, plugins, url, args, non_parsed):
        plugin_res = PluginResource(self.http_client_factory, self.formatter_factory)
        yaml_res = YamlConfigResource(self.http_client_factory, self.formatter_factory)

        current_plugins = list(plugin_res._list(args, non_parsed))

        ident_list = list()
        old_list = list()
        for new in plugins:
            try:
                self.logger.info("Plugin: {}".format(new['name']))
            except KeyError:
                raise KeyError("In plugin missing field \'name\'")

            if new.get('route'):
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
        service_group = conf.get('service_group', None)

        self.remove_missing_services_from_service_group(service_group, conf['services'], args, non_parsed)

        for service in conf['services']:
            routes = service['routes']
            plugins = service['plugins']

            try:
                data = {
                    'name': service['name'],
                    'url': service['url'],
                }
            except Exception as e:
                raise EnsureServiceError(e)

            url = self.service_update(service_group, data, args, non_parsed)
            self.route_update(routes, args, non_parsed)
            self.plugin_update(plugins, url + '/plugins', args, non_parsed)

    def plugin_required(self, conf, args, non_parsed):
        plugin_res = PluginResource(self.http_client_factory, self.formatter_factory)

        url = plugin_res.build_resource_url('create', args, non_parsed) + '/'
        for plugin in conf:
            self.logger.info('Plugin: {}'.format(plugin['name']))
            self.http_client.put(url + plugin['id'], json=plugin)

    def jwt_consumer(self, url, consumer, args, non_parsed):
        jwt_res = JwtSecrets(self.http_client_factory, self.formatter_factory)

        url += consumer['username']
        args.jwt = consumer['username']
        jwt_list = list(jwt_res._list(args, non_parsed))

        ident_list = list()
        if not consumer.get('jwt_secrets'):
            consumer['jwt_secrets'] = list()
        for new_jwt in consumer['jwt_secrets']:
            try:
                self.logger.info('jwt: key - {}'.format(new_jwt['key']))
            except KeyError:
                raise KeyError("In jwt_secrets missing field \'key\'")

            for current_jwt in jwt_list:
                cmp = YamlConfigResource.del_config_attr('jwt', current_jwt)
                if json.dumps(new_jwt, sort_keys=True) == json.dumps(cmp, sort_keys=True):
                    ident_list.append(new_jwt['key'])

        for current_jwt in jwt_list:
            if current_jwt['key'] in ident_list:
                continue
            self.http_client.delete(url + "/jwt/{}/".format(current_jwt['id']))

        for jwt in consumer['jwt_secrets']:
            if jwt['key'] in ident_list:
                continue
            self.http_client.post(url + '/jwt', json=jwt)

    def consumer_required(self, conf, args, non_parsed):
        consumer_res = ConsumerResource(self.http_client_factory, self.formatter_factory)
        key_auth_res = KeyAuthResource(self.http_client_factory, self.formatter_factory)

        consumers = conf['consumers']

        url = consumer_res.build_resource_url('create', args, non_parsed) + '/'
        for consumer in consumers:
            self.logger.info('Consumer: {}'.format(consumer['username']))
            user = dict()
            key = dict()

            user['username'] = consumer['username']
            self.http_client.put(url + consumer['username'], json=user)

            args.consumer = user['username']
            old_key = key_auth_res._list(args, non_parsed)

            ident_list = list()
            for k in old_key:
                for key in consumer['keyauth_credentials']:
                    try:
                        key['key']
                    except Exception:
                        raise EnsureKeyAuthError(user['username'])

                    if k['key'] == key['key']:
                        ident_list.append(k['key'])
                        break
                if k['key'] not in ident_list:
                    args.keyauth = k['id']
                    key_auth_res.delete(args, non_parsed)

            for key in consumer['keyauth_credentials']:
                self.logger.info('key: {}'.format(key['key']))
                if key['key'] not in ident_list:
                    self.http_client.post(url + consumer['username'] + '/key-auth/', json=key)
            self.jwt_consumer(url, consumer, args, non_parsed)

    def get_yaml_file(self, args, non_parsed):
        self.logger.info("Process the file or directory")

        services = []
        plugins = []
        consumers = []

        if os.path.isdir(args.path):
            folder = os.listdir(args.path)

            if os.path.isabs(args.path):
                config_path = args.path + '/'
            else:
                config_path = os.getcwd() + '/' + args.path + '/'

            for dr in folder:
                sub_dr_path = config_path + dr
                if not os.path.isdir(sub_dr_path):
                    continue
                sub_dr = os.listdir(sub_dr_path)
                for file in sub_dr:
                    full_path = os.path.join(args.path, dr, file)
                    if dr in '{services}':
                        services.append(full_path)
                    elif dr in '{plugins}':
                        plugins.append(full_path)
                    elif dr in '{consumers}':
                        consumers.append(full_path)

        else:
            # @TODO: analyze magically what is it: service/plugin/consumer
            file_path = args.path[args.path.rfind("/"):]

            if "consumers" in file_path:
                consumers.append(args.path)
            elif "plugins" in file_path:
                plugins.append(args.path)
            else:
                services.append(args.path)

        for path in services:
            self.logger.info("Processing service: {}".format("stdin" if path is "-" else path))
            if path is "-":
                f = sys.stdin
            else:
                f = open(path)
            parsed_config = self.var_map_insert_config(f.read())
            conf = yaml.safe_load(parsed_config)
            self.service_required(conf, args, non_parsed)

        for path in plugins:
            self.logger.info("Processing plugins: {}".format(path))
            f = open(path)
            parsed_config = self.var_map_insert_config(f.read())
            conf = yaml.safe_load(parsed_config)
            self.plugin_required(conf, args, non_parsed)

        for path in consumers:
            self.logger.info("Processing consumers: {}".format(path))
            f = open(path)
            parsed_config = self.var_map_insert_config(f.read())
            conf = yaml.safe_load(parsed_config)
            self.consumer_required(conf, args, non_parsed)

    def build_parser(self, ensure):
        ensure.set_defaults(func=self.get_yaml_file)
        ensure.add_argument('path', help='directory or yaml config file if path == - then read config from stdin')


class SnapshotsResource(BaseResource):
    def __init__(self, http_client, formatter):
        super().__init__(http_client, formatter, 'snapshot')

    def make_snapshot(self, args, non_parsed, services):
        yaml_config_resource = YamlConfigResource(self.http_client_factory, self.formatter_factory)
        snapshot = {
            'services': []
        }

        for service in services:
            try:
                args.service = service['name']
            except KeyError as e:
                raise SnapshotConfigMissingFieldError(e)

            current_service = yaml_config_resource.get_service(args, non_parsed)

            # Берем 0 элемент т.к. get_service возвращает только один сервис
            snapshot['services'].append(current_service['services'][0])

        return snapshot

    def save_snapshot(self, args, non_parsed, snapshot):
        if args.file is not None:
            with open(args.file, 'w') as f:
                YamlOutputFormatter(f).print_obj(snapshot)
        else:
            self.formatter.print_obj(snapshot)

    def snapshot_handler(self, args, non_parsed):
        with open(args.path) as f:
            conf = yaml.safe_load(f.read())

            try:
                services = conf['services']
            except KeyError as e:
                raise SnapshotConfigMissingFieldError(e)

            snapshot = self.make_snapshot(args, non_parsed, services)
            self.save_snapshot(args, non_parsed, snapshot)

    def build_parser(self, snapshot):
        snapshot.set_defaults(func=self.snapshot_handler)
        snapshot.add_argument('path', help='directory or yaml config file')
        snapshot.add_argument('-f', '--file', help='the file where the payment will be saved')
