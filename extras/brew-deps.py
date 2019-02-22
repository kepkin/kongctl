#!/usr/bin/env python3
"""
Generate Ruby code with URLs and file hashes for packages from PyPi
(i.e., httpie itself as well as its dependencies) to be included
in the Homebrew formula after a new release of HTTPie has been published
on PyPi.

<https://github.com/Homebrew/homebrew-core/blob/master/Formula/httpie.rb>

"""
import hashlib
import requests


PACKAGES = [
    ('kongctl', 'https://test.pypi.org/pypi/{}/json'),
    ('requests', 'https://pypi.org/pypi/{}/json'),
    ('certifi', 'https://pypi.org/pypi/{}/json'),
    ('termcolor', 'https://pypi.org/pypi/{}/json'),
    ('urllib3', 'https://pypi.org/pypi/{}/json'),
    ('idna', 'https://pypi.org/pypi/{}/json'),
    ('chardet', 'https://pypi.org/pypi/{}/json'),
    ('PySocks', 'https://pypi.org/pypi/{}/json'),
]


def get_package_meta(package_name):
    api_url = package_name[1].format(package_name[0])
    resp = requests.get(api_url).json()
    hasher = hashlib.sha256()
    for release in resp['urls']:
        download_url = release['url']
        if download_url.endswith('.tar.gz'):
            hasher.update(requests.get(download_url).content)
            return {
                'name': package_name[0],
                'url': download_url,
                'sha256': hasher.hexdigest(),
            }
    else:
        raise RuntimeError(
            '{}: download not found: {}'.format(package_name, resp))


def main():
    package_meta_map = {
        package_name[0]: get_package_meta(package_name)
        for package_name in PACKAGES
    }
    kongctl_meta = package_meta_map.pop('kongctl')
    print()
    print('  url "{url}"'.format(url=kongctl_meta['url']))
    print('  sha256 "{sha256}"'.format(sha256=kongctl_meta['sha256']))
    print()
    for dep_meta in package_meta_map.values():
        print('  resource "{name}" do'.format(name=dep_meta['name']))
        print('    url "{url}"'.format(url=dep_meta['url']))
        print('    sha256 "{sha256}"'.format(sha256=dep_meta['sha256']))
        print('  end')
        print('')


if __name__ == '__main__':
    main()
