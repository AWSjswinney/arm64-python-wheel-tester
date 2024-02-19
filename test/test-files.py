#!/usr/bin/env python3

import re
import os
import json
import time
import argparse
import importlib
import itertools
import subprocess
import multiprocessing
from datetime import datetime
from collections import defaultdict

process_results = importlib.import_module("process-results")
generate_website = importlib.import_module("generate-website")

SLOW_INSTALL_TIME = 60
TIMEOUT = 180

def main():
    parser = argparse.ArgumentParser(description="Run wheel tests")
    parser.add_argument('-i', '--inputfile', type=str, help="Input file")
    args = parser.parse_args()

    if args.inputfile is not None and len(args.inputfile) > 0:
        input_file = args.inputfile
    else:
        input_file = "fixture/results-2024-02-19_02-09-51.json.xz"

    # change working directory the path of this script
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    html = process_results.print_table_by_distro_report([input_file], [], None)
    json = process_results.create_output_json(input_file)

    output_dir = 'results'
    try:
        os.mkdir(output_dir)
    except FileExistsError:
        pass

    with open(f'{output_dir}/index.html', 'w') as f:
        f.write(html)

    with open(f'{output_dir}/results.json', 'w') as f:
        f.write(json)


if __name__ == '__main__':
    main()
