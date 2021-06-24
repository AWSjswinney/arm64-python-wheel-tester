#!/usr/bin/env python3

import re
import os
import json
import time
import yaml
import subprocess
from datetime import datetime
from collections import defaultdict

def main():
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    with open('packages.yaml') as f:
        packages = yaml.safe_load(f.read())

    results = defaultdict(dict)
    for package in packages['packages']:
        package_main_name = re.findall(r'([\S]+)', package['PIP_NAME'])[0]
        package['main_name'] = package_main_name
        for container in ['amazon-linux2', 'centos8', 'centos8-py38', 'focal']:
            print(f"Now testing {package_main_name} on {container}...")
            result = do_test(package, container)
            results[package_main_name][container] = result
            if result['test-passed']:
                print("passed!")
            print("")

    os.unlink('test-script.py')
    with open('results.json', 'w') as f:
        json.dump(results, f, indent=2)
    subprocess.run(['xz', 'results.json'], check=True)
    # chmod the results so that the host can remove the file when cleaning up
    subprocess.run(['chmod', '777', 'results.json.xz'], check=True)
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.rename('results.json.xz', f'results-{now}.json.xz')

def do_test(package, container):
    result = {
        'test-passed': False,
        'build-required': False,
        'binary-wheel': False,
        'slow-install': False,
    }
    package_name = package['PIP_NAME']
    test_script = package['PKG_TEST']
    package_main_name = package['main_name']
    with open('test-script.py', 'w') as f:
        f.write(test_script)
    wd = os.environ['WORK_PATH']
    start = time.time()
    proc = subprocess.run(['docker', 'run',
            '--interactive', '--rm', '-v', f'{wd}:/io',
            '--env', f'PIP_PACKAGE_LIST={package_name}',
            container,
            'bash', '/io/container-script.sh'],
            encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    if time.time() - start > 60:
        result['slow-install'] = True

    if proc.returncode == 0:
        result['test-passed'] = True

    if re.search(r'Building wheel for', proc.stdout) is not None:
        result['build-required'] = True

    if re.search(f'Downloading {package_main_name}[^\n]*aarch64[^\n]*whl', proc.stdout) is not None:
        result['binary-wheel'] = True

    result['output'] = proc.stdout

    return result


if __name__ == '__main__':
    main()
