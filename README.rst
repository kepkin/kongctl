A command line client for kong admin API
========================================

This tool ease kong management like getting routes for service name (not id):

.. code-block:: bash

    kongctl -s https://localhost:8001 list routes -s example-service

    1ba43640-6977-4d6a-9804-6e0032d77bb1: example-service
      example.com/

    d091d9c4-fde8-4982-b984-8376bd544aaf: example-service
      example.com/api/v1

You can store your configuration in multiple yaml files and apply them individually. Let's assume you have configuration like this:

.. code-block:: yaml

    _format_version: "1.1"
    
    services: 
      - name: orders-service
        url: http://kubernetes-inner.host:80/path-to-ns/orders
        routes: 
          - name: orders-root
            strip_path: true
            hosts:
              - orders.example.com
            
        plugins: 
          - name: jwt
            enabled: false
            route:
              name: orders-root
            
            run_on: first
            config: 
              key_claim_name: iss
              cookie_names: {}
              secret_is_base64: false
              maximum_expiration: 0
              anonymous: 
              run_on_preflight: true
              uri_param_names: 
                - jwt

Now you can call the following command to apply it:

.. code-block:: bash

    kongctl -s https://localhost:8001 ensure order-service.yaml


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
    cat  > ~/.kongctl/qa-env << EOF
    {
      "client": {
        "server": "https://my-kong.url:8001",
        "auth": {
          "password": "pass",
          "type": "basic",
          "user": "user"
        }
      },
      "var_map": {
        "VAR1": "VALUE1",
        "VAR2": "VALUE2"
      }
    }
    EOF

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
