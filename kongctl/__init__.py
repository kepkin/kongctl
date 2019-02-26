#!/usr/bin/env python
"""
kongcl - a CLI for kong admin interface.
"""
__version__ = '0.0.2'
__author__ = 'Alexander Nevskiy'
__licence__ = 'BSD'


import sys


def main():
    try:
        from .core import main
        sys.exit(main())
    except KeyboardInterrupt:
        from . import ExitStatus
        sys.exit(ExitStatus.ERROR_CTRL_C)


if __name__ == '__main__':
    main()
