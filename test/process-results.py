#!/usr/bin/env python3

import re
import glob
import json
import argparse
from functools import reduce
from collections import OrderedDict

def main():
    parser = argparse.ArgumentParser(description="Parse result files and render an HTML page with a status summary")
    parser.add_argument('resultfiles', type=str, nargs='+', metavar='results.json', help='path to a result file')

    args = parser.parse_args()
    print_table_report(args.resultfiles)

def get_tests_with_result(wheel_dict, key='test-passed', result=False):
    tests = []
    for test_name, test_results in wheel_dict.items():
        if test_results[key] == result:
            tests.append(test_name)
    return tests

def get_failing_tests(wheel_dict):
    return get_tests_with_result(wheel_dict, 'test-passed', False)

def get_build_required(wheel_dict):
    return get_tests_with_result(wheel_dict, 'build-required', True)

def get_build_required(wheel_dict):
    return get_tests_with_result(wheel_dict, 'build-required', True)

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
    with open('report.html', 'w') as f:
        f.write(html)
        
def get_wheel_report_cell(wheel, wheel_dict):
    failing = get_failing_tests(wheel_dict)
    build_required = get_build_required(wheel_dict)
    slow_install = get_tests_with_result(wheel_dict, 'slow-install', True)
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

def print_table_report(test_results_fname_list):
    test_results_list = []
    for fname in test_results_fname_list:
        with open(fname) as f:
            test_results_list.append(json.load(f))
    
    all_keys = set()
    for test_results in test_results_list:
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
                test_results_cache[test_results_i] = get_wheel_report_cell(wheel, wheel_dict)
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
    with open('report.html', 'w') as f:
        f.write(html)
        
HTML_HEADER = '''
<!doctype html>
<html>
<head>
<style type="text/css">

table.python-wheel-report td, table.python-wheel-report th {
    padding: 5px;
    border-width: 0px;
    margin: 5px;
    font-family: monospace;
}

table.python-wheel-report span.perfect-score {
    color: white;
/* Permalink - use to edit and share this gradient: https://colorzilla.com/gradient-editor/#bfd255+0,8eb92a+50,72aa00+51,9ecb2d+100;Green+Gloss */
background: #bfd255; /* Old browsers */
background: linear-gradient(to bottom,  #bfd255 0%,#8eb92a 50%,#72aa00 51%,#9ecb2d 100%);
}

table.python-wheel-report span.test-name {
    color: white;
/* Permalink - use to edit and share this gradient: https://colorzilla.com/gradient-editor/#f85032+0,f16f5c+50,f6290c+51,f02f17+71,e73827+100;Red+Gloss+%231 */
background: #f85032; /* Old browsers */
background: linear-gradient(to bottom,  #f85032 0%,#f16f5c 50%,#f6290c 51%,#f02f17 71%,#e73827 100%);
}

table.python-wheel-report span.all-passed {
    color: white;
/* Permalink - use to edit and share this gradient: https://colorzilla.com/gradient-editor/#bfd255+0,8eb92a+50,72aa00+51,9ecb2d+100;Green+Gloss */
background: #bfd255; /* Old browsers */
background: linear-gradient(to bottom,  #bfd255 0%,#8eb92a 50%,#72aa00 51%,#9ecb2d 100%);
}

table.python-wheel-report span.build-required {
    color: white;
/* Permalink - use to edit and share this gradient: https://colorzilla.com/gradient-editor/#ffd65e+0,febf04+100;Yellow+3D+%232 */
background: #ffd65e; /* Old browsers */
background: linear-gradient(to bottom,  #ffd65e 0%,#febf04 100%);
}

table.python-wheel-report span.slow-install {
    color: white;
/* Permalink - use to edit and share this gradient: https://colorzilla.com/gradient-editor/#ffd65e+0,febf04+100;Yellow+3D+%232 */
background: #ffd65e; /* Old browsers */
background: linear-gradient(to bottom,  #ffd65e 0%,#febf04 100%);
}


table.python-wheel-report span.badge {
    border-radius: 4px;
    margin: 3px;
    padding: 2px;
}


table.python-wheel-report tr.odd {
    background-color: #f1f1f1;
}

table.python-wheel-report td.wheel-name.different {
    background: #d1ffd9;
    font-style: italic;
}



</style>
</head>
<body>
'''

HTML_FOOTER = '''
</body>
</html>
'''

if __name__ == '__main__':
    main()
