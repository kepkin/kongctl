from .json_formatter import JsonOutputFormatter
from .yaml_formatter import YamlOutputFormatter
from .client import HttpClient
from .resources import *
from . import __version__

import logging
import argparse
import sys


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
        HttpClient.build_parser(parser)

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

        def get_http_client():
            base_args, _ = parser.parse_known_args()
            http_client = HttpClient.build_from_args(base_args)
            return http_client

        def get_formatter():
            args, _ = parser.parse_known_args()
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

        EnsureResource(get_http_client, get_formatter).build_parser(ensure)
        YamlConfigResource(get_http_client, get_formatter).build_parser(sb_config)
        ServiceResource(get_http_client, get_formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
        RouteResource(get_http_client, get_formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
        PluginResource(get_http_client, get_formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
        PluginSchemaResource(get_http_client, get_formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
        ConsumerResource(get_http_client, get_formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
        KeyAuthResource(get_http_client, get_formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
        JwtSecrets(get_http_client, get_formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)

        args, non_parsed = parser.parse_known_args()
        try:
            args.func(args, non_parsed)

        except KeyboardInterrupt:
            sys.exit(0)
    except Exception as e:
        raise
        logging.getLogger('__name__').fatal(e)


if __name__ == '__main__':
    main()
