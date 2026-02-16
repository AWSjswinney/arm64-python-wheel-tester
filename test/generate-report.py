#!/usr/bin/env python3

import os
import re
import glob
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
    parser.add_argument('--by-test', action='store_true', help="print results by test (distro)")
    parser.add_argument('-o', '--output-file', type=str, help="file name to write report")
    parser.add_argument('--compare-weekday-num', type=int, help="integer weekday number to hinge the summary report on", default=None)

    args = parser.parse_args()
    if args.by_test:
        html = print_table_by_distro_report(args.resultfiles, args.ignore, args.compare_weekday_num)
    else:
        html = print_table_report(args.resultfiles, args.ignore)
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

def get_build_required(wheel_dict, ignore_tests=[]):
    return get_tests_with_result(wheel_dict, 'build-required', True, ignore_tests)

def get_build_required(wheel_dict, ignore_tests=[]):
    return get_tests_with_result(wheel_dict, 'build-required', True, ignore_tests)

def print_report(all_wheels):
    passing = []
    failing = []
    for wheel, wheel_dict in all_wheels.items():
        failed_tests = get_failing_tests(wheel_dict)
        if len(failed_tests) == 0:
            passing.append((wheel, wheel_dict))
        else:
            failing.append((wheel, wheel_dict))
    html = []
    html.append(f'<h1>Passing - {len(passing)}</h1>')
    html.append('<ul>')
    for wheel, wheel_dict in passing:
        html.append(f'<li>{wheel}</li>')
    html.append('</ul>')

    html.append(f'<h1>Failing - {len(failing)}</h1>')
    html.append('<ul>')
    for wheel, wheel_dict in failing:
        html.append(f'<li>{wheel}</li>')
    html.append('</ul>')

    html = '\n'.join(html)
    return html

def get_wheel_report_cell(wheel, wheel_dict, ignore_tests):
    failing = get_failing_tests(wheel_dict, ignore_tests=ignore_tests)
    build_required = get_build_required(wheel_dict, ignore_tests=ignore_tests)
    slow_install = get_tests_with_result(wheel_dict, 'slow-install', True, ignore_tests=ignore_tests)
    badges = set()

    cell_text = []
    cell_text.append('<div>')
    if len(failing) == 0 and len(build_required) == 0 and len(slow_install) == 0:
        cell_text.append('<span class="perfect-score badge">perfect score</span> ')
        badges.add('perfect-score')
    elif len(failing) == 0:
        cell_text.append('<span class="all-passed badge">all-passed</span> ')
        badges.add('all-passed')
    if len(build_required) > 0:
        cell_text.append('<span class="build-required badge">build required</span> ')
        badges.add('build-required')
    if len(slow_install) > 0:
        cell_text.append('<span class="slow-install badge">slow-install</span> ')
        badges.add('slow-install')
    for test_name in failing:
        cell_text.append(f'<span class="test-name badge">{test_name}</span>')
        badges.add(test_name)

    cell_text.append('</div>')
    return ('\n'.join(cell_text), badges)

def load_result_files(test_results_fname_list):
    for fname in test_results_fname_list:
        if re.search(r'\.xz$', fname) is not None:
            with lzma.open(fname) as f:
                yield json.load(f), fname
        else:
            with open(fname) as f:
                yield json.load(f), fname


def print_table_report(test_results_fname_list, ignore_tests=[]):
    test_results_list = []
    if ignore_tests is None:
        ignore_tests = []

    all_keys = set()
    for test_results, fname in load_result_files(test_results_fname_list):
        test_results_list.append(test_results)
        all_keys.update(test_results.keys())
    all_keys = sorted(list(all_keys), key=str.lower)

    html = []
    html.append(HTML_HEADER)
    html.append('<table class="python-wheel-report">')
    html.append('<tr>')
    html.append('<th></th>')
    for i, test_results in enumerate(test_results_list):
        html.append(f'<th>{test_results_fname_list[i]}</th>')
    html.append('</tr>')
    for i, wheel in enumerate(all_keys):
        test_results_cache = {}
        for test_results_i, test_results in enumerate(test_results_list):
            if wheel in test_results:
                wheel_dict = test_results[wheel]
                test_results_cache[test_results_i] = get_wheel_report_cell(wheel, wheel_dict, ignore_tests)
        # check to see if the sets returned as item index 1 are all the same
        badge_set = None
        wheel_differences = False
        for s in map(lambda x: x[1][1], test_results_cache.items()):
            if badge_set is None:
                badge_set = s
            elif badge_set != s:
                wheel_differences = True
                break
        wheel_differences = 'different' if wheel_differences else ''
        odd_even = 'even' if (i+1) % 2 == 0 else 'odd'
        html.append(f'<tr class="wheel-line {odd_even}">')
        html.append(f'<td class="wheel-name {wheel_differences}">{wheel}</td>')
        for test_results_i, test_results in enumerate(test_results_list):
            html.append('<td class="wheel-report">')
            if wheel in test_results:
                html.append(test_results_cache[test_results_i][0])
            html.append('</td>')
        html.append('</tr>')
    html.append('</table>')
    html.append(HTML_FOOTER)
    html = '\n'.join(html)
    return html


def make_badge(classes=[], text=""):
    classes.append('badge')
    classes = " ".join(classes)
    return f'<span class="{classes}">{text}</span>'

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
    distros = ["amazon-linux2", "centos8", "focal", "jammy", "noble"]
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
                    return '<br /><span class="file-indicator">last passed on ' + tf.date.strftime("%B %d, %Y") + '</span>'
            except KeyError:
                continue
        return ''

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
