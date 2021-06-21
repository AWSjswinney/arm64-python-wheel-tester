#!/usr/bin/env python3

import re
import yaml
import subprocess

def main():
    with open('packages.yaml') as f:
        packages = yaml.safe_load(f.read())

    #for container in ['amazon-linux2', 'centos8', 'centos8-py38', 'focal']:
    for container in ['focal']:
        for package in packages['packages']:
            print(package)
            do_test(package, container)


def do_test(package, container):
    package_name = package['PIP_NAME']
    pip_list = re.findall(r'([\S]+)', package_name)
    test_script = package['PKG_TEST']
    try:
        subprocess.run(['docker', 'create', '-t', '--rm', '--name', 'wheel-test', container, 'bash'], check=True)
        subprocess.run(['docker', 'start', 'wheel-test'], check=True)
        subprocess.run(['docker', 'exec', '-i', 'wheel-test', 'pip3', 'install'] + pip_list, check=True)
        try:
            subprocess.run(['docker', 'exec', '-i', 'wheel-test', 'python3'], encoding='utf-8', input=package['PKG_TEST'], check=True)
        except subprocess.CalledProcessError:
            print(f"Test failed for package: {package['PIP_NAME']}")
    finally:
        subprocess.run(['docker', 'stop', 'wheel-test'])

if __name__ == '__main__':
    main()
