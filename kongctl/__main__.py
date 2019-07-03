
from .json_formatter import JsonOutputFormatter
from .yaml_formatter import YamlOutputFormatter
from .client import HttpClient
from .resources import *
from . import __version__

import argparse
import sys


def main():
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
    config = sb.add_parser('config', help='Config yaml resource')
    ensure = sb.add_parser('ensure', help='Create config yaml')

    base_args, _ = parser.parse_known_args()
    http_client = HttpClient.build_from_args(base_args)
    parser.add_argument('-y', '--yml', default=False, action='store_true', help='Yaml conversion')

    args, _ = parser.parse_known_args()
    if args.yml:
        formatter = YamlOutputFormatter()
    else:
        formatter = JsonOutputFormatter()
    list_.add_argument('-f', dest="list_full", action='store_true', default=False,
                       help='Get full description of resource')

    sb_list = list_.add_subparsers()
    sb_get = get.add_subparsers()
    sb_create = create.add_subparsers()
    sb_update = update.add_subparsers()
    sb_delete = delete.add_subparsers()
    sb_config = config.add_subparsers()

    EnsureResource(http_client, formatter).build_parser(ensure)
    YamlConfigResource(http_client, formatter).build_parser(sb_config)
    ServiceResource(http_client, formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
    RouteResource(http_client, formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
    PluginResource(http_client, formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
    PluginSchemaResource(http_client, formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
    ConsumerResource(http_client, formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
    KeyAuthResource(http_client, formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)

    args, non_parsed = parser.parse_known_args()
    try:
        args.func(args, non_parsed)

    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == '__main__':
    main()
