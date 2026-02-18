#!/usr/bin/env python3

import os
import glob
import argparse
import tempfile
import importlib

process_results = importlib.import_module("generate-report")

def main():
    parser = argparse.ArgumentParser(description="Generate the static website")
    parser.add_argument('-o', '--output-dir', type=str, help="directory for the generated website", required=True)
    parser.add_argument('--new-results', type=str, help="result file to add to website", required=True)
    parser.add_argument('--results-dir', type=str, help="local directory containing previous result files", default=None)
    parser.add_argument('--compare-weekday-num', type=int, help="integer weekday number to hinge the summary report on", default=None)
    parser.add_argument('--ignore', type=str, action='append', help='Ignore tests with the specified name; can be used more than once.', default=[])

    args = parser.parse_args()

    generate_website(args.output_dir, args.new_results,
            compare_weekday_num=args.compare_weekday_num,
            ignore_tests=args.ignore, results_dir=args.results_dir)

def generate_website(output_dir, new_results, compare_weekday_num=None, ignore_tests=[], results_dir=None):
    print("Fetching previous results...")
    if results_dir:
        previous_results = fetch_local_results(results_dir, new_results)
    else:
        previous_results = []
    
    if not previous_results:
        print("No previous results found. Proceeding with current results only.")
    else:
        print(f"Found {len(previous_results)} previous result files.")

    results = [new_results]
    results.extend(previous_results)
    
    print("Generating HTML report...")
    html = process_results.print_table_by_distro_report(results, compare_weekday_num=compare_weekday_num, ignore_tests=ignore_tests)

    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        print(f"Error: Failed to create output directory {output_dir}: {e}")
        return
        
    with open(f'{output_dir}/index.html', 'w') as f:
        f.write(html)
    print(f"Website generated successfully at {output_dir}/index.html")


def fetch_local_results(results_dir, exclude_fname=None, max_results=2500):
    """Load result files from a local directory, excluding the current run's file.
    
    max_results caps history to limit memory (~0.8 MB per file in memory).
    Default of 2500 keeps usage under ~2 GB.
    """
    fnames = sorted(glob.glob(os.path.join(results_dir, 'results-*.json*')), reverse=True)
    if exclude_fname:
        exclude_base = os.path.basename(exclude_fname)
        fnames = [f for f in fnames if os.path.basename(f) != exclude_base]
    if len(fnames) > max_results:
        print(f"Limiting to {max_results} most recent result files (of {len(fnames)})")
        fnames = fnames[:max_results]
    if not fnames:
        print("Warning: No previous result files found in " + results_dir)
    else:
        print(f"Found {len(fnames)} previous result files in {results_dir}")
    return fnames


if __name__ == '__main__':
    main()
