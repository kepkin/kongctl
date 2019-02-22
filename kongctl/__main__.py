
from .json_formatter import JsonOutputFormatter
from .client import HttpClient
from .resources import *

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description='Kong command line client for admin api.')

    def usage_func(*args, **kwargs):
        parser.print_help()

    parser.set_defaults(func=usage_func)
    HttpClient.build_parser(parser)

    sb = parser.add_subparsers(help='sub-command help')
    list_ = sb.add_parser('list',   help='')
    get = sb.add_parser('get',    help='Get all services')
    create = sb.add_parser('create', help='Get all services')
    update = sb.add_parser('update', help='Get all services')
    delete = sb.add_parser('delete', help='Get all services')

    base_args, _ = parser.parse_known_args()
    httpClient = HttpClient.build_from_args(base_args)
    formatter = JsonOutputFormatter()

    list_.add_argument('-f', dest="list_full", action='store_true', default=False, help='Get full description of resource')

    sb_list = list_.add_subparsers()
    sb_get = get.add_subparsers()
    sb_create = create.add_subparsers()
    sb_update = update.add_subparsers()
    sb_delete = delete.add_subparsers()

    ServiceResource(httpClient, formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
    RouteResource(httpClient, formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)
    PluginResource(httpClient, formatter).build_parser(sb_list, sb_get, sb_create, sb_update, sb_delete)

    args, non_parsed = parser.parse_known_args()
    try:
        args.func(args, non_parsed)

    except KeyboardInterrupt:
        sys.exit(0)

    except Exception as ex:
        print("Error: ", ex)


if __name__ == '__main__':
    main()
