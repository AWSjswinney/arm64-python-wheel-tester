#!/bin/bash

set -e

cd /io
pip3 install $PIP_EXTRA_ARGS $PIP_PACKAGE_LIST
python3 test-script.py
