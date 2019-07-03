#!/usr/bin/env python
# This is purely the result of trial and error.

import codecs

from setuptools import find_packages
from distutils.core import setup

import kongctl

install_requires = [
    'requests>=2.21.0',
    'termcolor==1.1.0',
    'PyYAML>=5.1.1',
]


def long_description():
    with codecs.open('README.rst', encoding='utf8') as f:
        return f.read()


setup(
    name='kongctl',
    version=kongctl.__version__,
    description=kongctl.__doc__.strip(),
    long_description=long_description(),
    url='https://github.com/kepkin/kongctl',
    download_url='https://github.com/kepkin/kongctl',
    author=kongctl.__author__,
    author_email='kepkin@gmail.com',
    license=kongctl.__licence__,
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'kongctl = kongctl.__main__:main',
        ],
    },
    setup_requires=['wheel'],
    # extras_require=extras_require,
    install_requires=install_requires,
    # tests_require=tests_require,
    # cmdclass={'test': PyTest},
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.1',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: BSD License',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development',
        'Topic :: System :: Networking',
        'Topic :: Terminals',
        'Topic :: Text Processing',
        'Topic :: Utilities'
    ],
)
