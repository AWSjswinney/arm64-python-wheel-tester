#!/bin/bash

set -e

cd /io
yum install -y $PACKAGE_LIST
/usr/bin/python3 test-script.py
