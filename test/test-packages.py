#!/usr/bin/env python3

import re
import os
import time
import yaml
import subprocess

def main():
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    with open('packages.yaml') as f:
        packages = yaml.safe_load(f.read())

    for package in packages['packages']:
        for container in ['amazon-linux2', 'centos8', 'centos8-py38', 'focal']:
            print(f"Now testing {package} on {container}...")
            do_test2(package, container)
            print("")


def do_test(package, container):
    package_name = package['PIP_NAME']
    pip_list = re.findall(r'([\S]+)', package_name)
    if 'PIP_ARGS' in package:
        pip_list = re.findall(r'([\S]+)', package['PIP_ARGS']) + pip_list
    test_script = package['PKG_TEST']
    try:
        for i in range(3):
            try:
                subprocess.run(['docker', 'create', '-t', '--rm', '--name', 'wheel-test', container, 'bash'], check=True)
                break
            except subprocess.CalledProcessError:
                time.sleep(1)
        subprocess.run(['docker', 'start', 'wheel-test'], check=True)
        subprocess.run(['docker', 'exec', '-i', 'wheel-test', 'pip3', 'install'] + pip_list, check=True)
        try:
            subprocess.run(['docker', 'exec', '-i', 'wheel-test', 'python3'], encoding='utf-8', input=package['PKG_TEST'], check=True)
            print(f"Test passed for package: {package['PIP_NAME']}")
        except subprocess.CalledProcessError:
            print(f"Test failed for package: {package['PIP_NAME']}")
    finally:
        print("Stopping container...")
        subprocess.run(['docker', 'stop', 'wheel-test'])
        subprocess.run(['docker', 'wait', 'wheel-test'])
        print("Container stopped.")

def do_test2(package, container):
    package_name = package['PIP_NAME']
    test_script = package['PKG_TEST']
    with open('test-script.py', 'w') as f:
        f.write(test_script)
    wd = os.environ['WORK_PATH']
    proc = subprocess.run(['docker', 'run',
            '--interactive', '--rm', '-v', f'{wd}:/io',
            '--env', f'PIP_PACKAGE_LIST={package_name}',
            container,
            'bash', '/io/container-script.sh'])
    return proc.returncode == 0


if __name__ == '__main__':
    main()
