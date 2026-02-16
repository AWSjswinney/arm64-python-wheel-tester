#!/usr/bin/env python3

import io
import os
import glob
import json
import zipfile
import argparse
import requests
import tempfile
import importlib
import subprocess
from datetime import datetime, timedelta

process_results = importlib.import_module("process-results")

def main():
    parser = argparse.ArgumentParser(description="Generate the static website")
    parser.add_argument('-o', '--output-dir', type=str, help="directory for the generated website", required=True)
    parser.add_argument('--repo', type=str, help="path to the source git repository", default=None)
    parser.add_argument('--website-branch', type=str, help="name of website branch", default=None)
    parser.add_argument('--new-results', type=str, help="result file to add to website", required=True)
    parser.add_argument('--compare-n-days-ago', type=int, help="number of days in the past to compare against", nargs='+')
    parser.add_argument('--github-token', type=str, help="github api token", default=None)
    parser.add_argument('--results-dir', type=str, help="local directory containing previous result files (alternative to github artifacts)", default=None)
    parser.add_argument('--compare-weekday-num', type=int, help="integer weekday number to hinge the summary report on", default=None)
    parser.add_argument('--ignore', type=str, action='append', help='Ignore tests with the specified name; can be used more than once.', default=[])

    args = parser.parse_args()

    generate_website(args.output_dir, args.new_results, args.github_token, args.compare_n_days_ago,
            repo_path=args.repo, website_branch=args.website_branch, compare_weekday_num=args.compare_weekday_num,
            ignore_tests=args.ignore, results_dir=args.results_dir)

def generate_website(output_dir, new_results, github_token, days_ago_list=[], repo_path="/repo", website_branch="gh-pages",
        compare_weekday_num=None, ignore_tests=[], results_dir=None):
    # TODO: checkout the existing gh-pages and update it with a new report rather than replacing it completely
    # clone the repo to a temporary directory and checkout the website branch
    #webrepo = tempfile.mkdtemp()
    #subprocess.run(f'git clone --no-checkout -b {website_branch} {repo_path} {webrepo}', shell=True)

    # download results from previous run
    print("Fetching previous results...")
    if results_dir:
        previous_results = fetch_local_results(results_dir, new_results)
    elif github_token and days_ago_list:
        previous_results = fetch_previous_results(days_ago_list, github_token=github_token)
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
        print(f"Warning: Failed to create output directory {output_dir}: {str(e)}")
        # Try to use a temporary directory instead
        output_dir = tempfile.mkdtemp()
        print(f"Using temporary directory instead: {output_dir}")
        
    try:
        with open(f'{output_dir}/index.html', 'w') as f:
            f.write(html)
        print(f"Website generated successfully at {output_dir}/index.html")
    except Exception as e:
        print(f"Error writing HTML output: {str(e)}")
        return



def fetch_local_results(results_dir, exclude_fname=None):
    """Load result files from a local directory, excluding the current run's file."""
    fnames = sorted(glob.glob(os.path.join(results_dir, 'results-*.json.xz')), reverse=True)
    if exclude_fname:
        exclude_base = os.path.basename(exclude_fname)
        fnames = [f for f in fnames if os.path.basename(f) != exclude_base]
    if not fnames:
        print("Warning: No previous result files found in " + results_dir)
    else:
        print(f"Found {len(fnames)} previous result files in {results_dir}")
    return fnames


def fetch_previous_results(days_ago_list, github_token):
    if len(days_ago_list) == 0:
        return []

    api_date_format = '%Y-%m-%dT%H:%M:%SZ'
    try:
        github_repo = os.environ['GITHUB_REPOSITORY']
        github_api_url = os.environ['GITHUB_API_URL']
    except KeyError:
        print("Warning: GITHUB_REPOSITORY or GITHUB_API_URL environment variables not set")
        return []

    url = f'{github_api_url}/repos/{github_repo}/actions/artifacts'
    try:
        r = requests.get(url, headers={'Accept': 'application/vnd.github.v3+json'})
        if r.status_code != 200:
            print(f"Warning: GitHub API returned status code {r.status_code}")
            return []
    except Exception as e:
        print(f"Warning: Failed to read from GitHub API: {str(e)}")
        return []

    try:
        response_data = r.json()
        if 'artifacts' not in response_data:
            print(f"Warning: No artifacts found in GitHub API response")
            return []
    except Exception as e:
        print(f"Warning: Failed to parse GitHub API response: {str(e)}")
        return []

    days_ago_list = sorted(days_ago_list, reverse=True)
    artifacts = sorted(response_data['artifacts'], reverse=True, key=lambda x: datetime.strptime(x['created_at'], api_date_format))
    now = datetime.utcnow()
    results = []
    for artifact in artifacts:
        if len(days_ago_list) == 0:
            break
        created_at = datetime.strptime(artifact['created_at'], api_date_format)
        if now - timedelta(days=days_ago_list[-1]) > created_at:
            results.append(artifact)
            days_ago_list.pop()

    if len(results) == 0:
        print("Warning: No matching artifacts found for the specified days")
        return []

    result_fnames = []
    previous_results_dir = tempfile.mkdtemp()
    for previous_result in results:
        url = previous_result['archive_download_url']
        try:
            r = requests.get(url, headers={'Accept': 'application/vnd.github.v3+json', 'Authorization': f'Bearer {github_token}'})
            if r.status_code != 200:
                print(f"Warning: Failed to download artifact from {url}, status code: {r.status_code}")
                continue
        except Exception as e:
            print(f"Warning: Failed to download artifact from {url}: {str(e)}")
            continue
            
        try:
            zf = zipfile.ZipFile(io.BytesIO(r.content))
        except zipfile.BadZipFile:
            print(f"Warning: Bad zip file at {previous_result['archive_download_url']}. Skipping.")
            continue

        # find the first xz file
        found_xz = False
        for fname in zf.namelist():
            if fname[-3:] == '.xz':
                found_xz = True
                try:
                    with zf.open(fname) as f:
                        result_fname = f'{previous_results_dir}/{fname}'
                        with open(result_fname, 'wb') as dest_f:
                            dest_f.write(f.read())
                        result_fnames.append(result_fname)
                    break
                except Exception as e:
                    print(f"Warning: Failed to extract {fname} from zip: {str(e)}")
                    continue
        
        if not found_xz:
            print(f"Warning: No .xz file found in artifact {previous_result['name']}")

    if not result_fnames:
        print("Warning: No valid result files were found in the artifacts")
        
    return result_fnames


if __name__ == '__main__':
    main()
