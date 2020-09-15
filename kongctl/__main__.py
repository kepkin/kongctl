from .json_formatter import JsonOutputFormatter
from .yaml_formatter import YamlOutputFormatter
from .client import HttpClient
from .resources import *
from . import __version__

import logging
import argparse
import sys


def build_http_client_parser(parser):
    parser.add_argument("-c", "--ctx", metavar="PATH", help="context file")
    parser.add_argument("-s", "--server", metavar="url", default=argparse.SUPPRESS, help="Url to kong api")
    parser.add_argument("--timeout", default=5, type=int, help="Timeout in seconds")
    parser.add_argument("-v", dest="verbose", action='store_true', default=False, help="verbose mode")
    parser.add_argument("-vv", dest="super_verbose", action='store_true', default=False, help="super verbose mode")


def build_app_config(args):
    config = {'client': {}, 'var_map': {}}
    config['client'].update(HttpClient.default_opts)

    if args.ctx:
        ctx_path = os.path.expanduser(args.ctx)
        if not (os.path.isfile(ctx_path) and os.path.exists(ctx_path)):
            ctx_path = os.path.expanduser(os.path.join("~", ".kongctl", ctx_path))
        data_conf = json.load(open(ctx_path))

        config['client'].update(data_conf.get('client', {}))
        config['var_map'].update(data_conf.get('var_map', {}))

    return config


def build_http_client(app_config):
    return HttpClient(**app_config['client'])


def main():
    try:
        parser = argparse.ArgumentParser(description='Kong command line client for admin api.')
        parser.add_argument('--version', action='store_true', default=False, help='Get tool version')

        def usage_func(args, *_, **__):
            if args.version:
                print(__version__)
                return

            parser.print_help()

        parser.set_defaults(func=usage_func)
        build_http_client_parser(parser)

        sb = parser.add_subparsers(help='')
        list_ = sb.add_parser('list', help='Get all resources')
        get = sb.add_parser('get', help='Get particular resource')
        create = sb.add_parser('create', help='Create resource')
        update = sb.add_parser('update', help='Update resource')
        delete = sb.add_parser('delete', help='Delete resource')
        config = sb.add_parser('config', help='Get yaml config file', description="Assembling yaml config file")
        ensure = sb.add_parser('ensure', help='Create: service, plugins and routes from config file',
                               description='Add the service of its paths and plugins or plugins not have services and '
                                           'routes or consumers and their key-auth from the configuration file to the '
                                           'Kong server.')
        snapshot = sb.add_parser('snapshot', help='Snapshot all services from config .yaml file')

        args, _ = parser.parse_known_args()
        app_config = build_app_config(args)

        def get_http_client():
            http_client = build_http_client(app_config)
            return http_client

        def get_formatter():
            if args.yml:
                return YamlOutputFormatter()
            else:
                return JsonOutputFormatter()

        parser.add_argument('-y', '--yml', default=False, action='store_true', help='Yaml conversion')
        list_.add_argument('-f', dest="list_full", action='store_true', default=False,
                           help='Get full description of resource')

        sb_list = list_.add_subparsers()
        sb_get = get.add_subparsers()
        sb_create = create.add_subparsers()
        sb_update = update.add_subparsers()
        sb_delete = delete.add_subparsers()
        sb_config = config.add_subparsers()

        SnapshotsResource(get_http_client, get_formatter).build_parser(snapshot)
        EnsureResource(get_http_client, get_formatter, app_config.get('var_map', {})).build_parser(ensure)
        YamlConfigResource(get_http_client, get_formatter).build_parser(sb_config)
        ServiceResource(get_http_client, get_formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
        RouteResource(get_http_client, get_formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
        PluginResource(get_http_client, get_formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
        PluginSchemaResource(get_http_client, get_formatter).build_parser(sb_list, sb_get, sb_create, sb_update,
                                                                          sb_delete)
        ConsumerResource(get_http_client, get_formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
        KeyAuthResource(get_http_client, get_formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
        JwtSecrets(get_http_client, get_formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)

        args, non_parsed = parser.parse_known_args()
        try:
            args.func(args, non_parsed)

        except KeyboardInterrupt:
            sys.exit(0)

        except Exception as e:
            print(e)
            sys.exit(1)

    except Exception as e:
        logging.getLogger(__name__).fatal(e)
        raise


if __name__ == '__main__':
    main()
