#!/usr/bin/env python3

import os
import re
import json
import lzma
import math
import argparse
import requests
from collections import defaultdict
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader

def main():
    parser = argparse.ArgumentParser(description="Parse result files and render an HTML page with a status summary")
    parser.add_argument('resultfiles', type=str, nargs='+', metavar='results.json', help='path to a result file')
    parser.add_argument('--ignore', type=str, action='append', help='Ignore tests with the specified name; can be used more than once.', default=[])
    parser.add_argument('-o', '--output-file', type=str, help="file name to write report")
    parser.add_argument('--compare-weekday-num', type=int, help="integer weekday number to hinge the summary report on", default=None)

    args = parser.parse_args()
    html = print_table_by_distro_report(args.resultfiles, args.ignore, args.compare_weekday_num)
    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(html)
    else:
        print(html)

def get_wheels_with_result(wheel_dict, key='test-passed', result=False, ignore_tests=[]):
    wheels = set()
    for wheel_name, wheel_results in wheel_dict.items():
        if wheel_name in ignore_tests:
            continue
        for test_name, test_results in wheel_results.items():
            if test_results[key] == result:
                wheels.add(wheel_name)
    return list(wheels)

def get_failing_tests(wheel_dict, ignore_tests=[]):
    return get_wheels_with_result(wheel_dict, 'test-passed', False, ignore_tests)


def get_package_name_class(test_name):
    if 'conda' in test_name:
        return 'package-conda'
    elif 'apt' in test_name:
        return 'package-os'
    elif 'yum' in test_name:
        return 'package-os'
    else:
        return 'package-pip'

def get_distribution_name(test_name):
    distros = ["amazon-linux2023", "jammy", "noble", "resolute"]
    for distro in distros:
        if distro in test_name:
            return distro
    return None

def get_package_manager_name(test_name):
    names = ['yum', 'apt', 'conda']
    for name in names:
        if name in test_name:
            return name
    return 'pip'


class TestResultFile():
    def __init__(self, fname):
        self.fname = fname
        self.content = None
        self.date = None
        self.wheels = {}

    def add_inferred_meta_data(self):
        for wheel, wheel_dict in self.content.items():
            passed_by_distro = defaultdict(lambda: False)
            self.wheels[wheel] = {}
            self.wheels[wheel]['results'] = wheel_dict
            for test_name, test_name_results in wheel_dict.items():
                distribution = get_distribution_name(test_name)
                test_name_results['distribution'] = distribution
                test_name_results['package_manager'] = get_package_manager_name(test_name)
                passed_by_distro[distribution] |= test_name_results['test-passed']
            self.wheels[wheel]['passed-by-disribution'] = passed_by_distro
            self.wheels[wheel]['each-distribution-has-passing-option'] = len(list(filter(lambda x: not x, passed_by_distro.values()))) == 0

def get_wheel_ranks():
    url = 'https://hugovk.github.io/top-pypi-packages/top-pypi-packages-30-days.min.json'
    try:
        r = requests.get(url)
    except requests.RequestsError:
        print('failed to load top pypi packages list')
        return []

    try:
        packages = r.json()['rows']
        # the list should be sorted already, but lets not assume that
        packages = sorted(packages, key=lambda x: x['download_count'], reverse=True)
        packages = [package['project'] for package in packages]
        return packages
    except KeyError:
        print('unable to parse top pypi packages list; the format may have changed')
        return []

def print_table_by_distro_report(test_results_fname_list, ignore_tests=[], compare_weekday_num=None):

    test_results_list = []
    for fname in test_results_fname_list:
        test_result_file = TestResultFile(fname)
        if re.search(r'\.xz$', fname) is not None:
            with lzma.open(fname) as f:
                test_result_file.content = json.load(f)
        else:
            with open(fname) as f:
                test_result_file.content = json.load(f)

        mo = re.search(r'[^/]-([0-9\-_]+)\.json(?:\.xz)?$', fname)
        if mo is not None:
            test_result_file.date = datetime.strptime(mo.group(1), "%Y-%m-%d_%H-%M-%S")
        test_result_file.add_inferred_meta_data()
        test_results_list.append(test_result_file)

    # Sort the test result files by date because code that follows assumes this order.
    test_results_list = sorted(test_results_list, key=lambda x: x.date, reverse=True)

    # get a sorted list of all the wheel names
    wheel_name_set = set()
    # get a sorted list of all the test_names (distros, plus extra, e.g. centos-python38)
    all_test_names = set()
    for test_result in test_results_list:
        wheel_name_set.update(test_result.content.keys())
        for wheel, wheel_dict in test_result.content.items():
            for test_name, test_name_results in wheel_dict.items():
                if test_name not in ignore_tests:
                    all_test_names.add(test_name)
    wheel_name_set = sorted(list(wheel_name_set), key=str.lower)
    all_test_names = sorted(list(all_test_names))

    # get the wheel popularity ranking
    wheel_ranks = get_wheel_ranks()
    leading_zeros = math.floor(math.log10(len(wheel_ranks))) + 1
    wheel_rank_format = f'{{n:0{leading_zeros}d}}'

    # Build summary rows for the comparison table
    summary_rows = []
    if type(compare_weekday_num) is int:
        reference_date = test_results_list[0].date
        reference_date = reference_date.replace(hour=23, minute=59)
        reference_date = reference_date - timedelta(days=reference_date.weekday()) + timedelta(days=compare_weekday_num)
        if test_results_list[0].date.weekday() <= compare_weekday_num:
            reference_date -= timedelta(days=7)

        reference_test_file = None
        for tf in test_results_list:
            if tf.date < reference_date:
                reference_test_file = tf
                break

        files_to_summarize = [test_results_list[0]]
        if reference_test_file is not None and reference_test_file.content is not None:
            files_to_summarize = [reference_test_file, test_results_list[0]]
        else:
            print("Warning: No valid reference test file found for comparison")

        labels = ['date', 'number of wheels', 'all tests passed', 'some tests failed', 'each dist has passing option']
        columns = []
        for tf in files_to_summarize:
            count = len(tf.content)
            failures = len(get_failing_tests(tf.content))
            passing_options = len([w for w in tf.wheels.values() if w['each-distribution-has-passing-option']])
            columns.append([tf.date.strftime("%A, %B %d, %Y"), count, count - failures, failures, passing_options])

        has_ref = len(columns) == 2
        for i, label in enumerate(labels):
            values = [col[i] for col in columns]
            if label == 'date':
                diff = None
            elif has_ref:
                d = values[-1] - values[0]
                diff = f"+{d}" if d >= 0 else str(d)
            else:
                diff = "N/A"
            summary_rows.append((label, values, diff))

    # Helper to find last passing date for a wheel/test
    def date_of_last_passing(wheel, test_name):
        for tf in test_results_list[1:]:
            try:
                if test_name == 'each-distribution-has-passing-option':
                    passed = tf.wheels[wheel][test_name]
                else:
                    passed = tf.content[wheel][test_name]['test-passed']
                if passed:
                    return tf.date.strftime("%B %d, %Y")
            except KeyError:
                continue
        return None

    # Build wheel data for the template
    current = test_results_list[0]
    wheels = []
    for wheel_name in wheel_name_set:
        try:
            rank = wheel_rank_format.format(n=wheel_ranks.index(wheel_name) + 1)
        except (IndexError, ValueError):
            rank = '~'

        distro_passing = None
        distro_last_passing = ''
        if wheel_name in current.wheels:
            distro_passing = current.wheels[wheel_name]['each-distribution-has-passing-option']
            if not distro_passing:
                distro_last_passing = date_of_last_passing(wheel_name, 'each-distribution-has-passing-option')

        results = {}
        last_passing = {}
        if wheel_name in current.content:
            results = current.content[wheel_name]
            for test_name in all_test_names:
                if test_name in results and (not results[test_name]['test-passed'] or results[test_name].get('timeout')):
                    last_passing[test_name] = date_of_last_passing(wheel_name, test_name)

        wheels.append({
            'name': wheel_name,
            'rank': rank,
            'distro_passing': distro_passing,
            'distro_last_passing': distro_last_passing,
            'results': results,
            'last_passing': last_passing,
        })

    # Render template
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=False)
    env.filters['tail_lines'] = lambda text, n=20: '\n'.join(text.splitlines()[-n:])
    template = env.get_template('report.html')
    return template.render(
        pretty_date=current.date.strftime("%B %d, %Y"),
        summary_rows=summary_rows,
        all_test_names=all_test_names,
        wheels=wheels,
        current_date=current.date,
        get_package_name_class=get_package_name_class,
    )


if __name__ == '__main__':
    main()
