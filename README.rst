A command line client for kong admin API
========================================

This tool ease kong management like getting routes for service name (not id):

.. code-block:: bash

    kongctl -s https://localhost:8001 list routes -s example-service

    1ba43640-6977-4d6a-9804-6e0032d77bb1: example-service
      example.com/

    d091d9c4-fde8-4982-b984-8376bd544aaf: example-service
      example.com/api/v1


Installation
============

.. code-block:: bash

    brew tap kepkin/kongctl
    brew install kongctl

or

.. code-block:: bash

    pip3 install kongctl


Quick guide to usage
====================

.. code-block:: bash

    mkdir ~/.kongctl
    echo '{
        "server": "my-kong.url:8001",
        "auth": {
            "type": "basic",
            "user": "user",
            "password": "pass"
        }
    }' > ~/.kongctl/qa-env

    kong -c qa-env list services


TODO
====

 - Support for OIDC authorization
 - Get stubs for create operation
 - Support all key-auth like plugins
 - Support update from cmd args
 - Support yaml
 - Sort by id?
 - list command filter option
 - Autocomplete
 - Add images instead of code in README (to show color support)
