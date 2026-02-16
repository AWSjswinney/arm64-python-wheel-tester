#!/usr/bin/env python3
"""
Extract test results from the index.html file in a repository
for a range of commits and save them in JSON format.
"""

import os
import json
import re
import subprocess
from datetime import datetime
from bs4 import BeautifulSoup
import argparse
import multiprocessing
from multiprocessing import Pool
from tqdm import tqdm

def get_commit_list(repo_path, commit_range=None, num_commits=10):
    """
    Get a list of commits in the repository.
    
    Args:
        repo_path: Path to the repository
        commit_range: Git commit range (e.g., 'abcdef..master')
        num_commits: Number of commits to retrieve if commit_range is not specified
        
    Returns:
        List of (commit_hash, commit_datetime) tuples
    """
    try:
        # Construct the git log command
        git_cmd = ["git", "log", "--format=%H %ad", "--date=format:%Y-%m-%d %H:%M:%S"]
        
        if commit_range:
            git_cmd.append(commit_range)
        else:
            git_cmd.append(f"-{num_commits}")
        
        # Get the list of commits
        result = subprocess.run(
            git_cmd,
            check=True, capture_output=True, text=True, cwd=repo_path
        )
        
        # Parse the output into a list of (commit_hash, commit_datetime) tuples
        commits = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split(' ', 1)
                if len(parts) == 2:
                    commit_hash, commit_datetime = parts
                    commits.append((commit_hash, commit_datetime))
        
        return commits
    except subprocess.CalledProcessError as e:
        print(f"Warning: Could not get commit list: {e}")
        return []

def process_commit(args):
    """
    Process a single commit (to be used with multiprocessing).
    
    Args:
        args: Tuple of (repo_path, commit_hash, commit_datetime)
        
    Returns:
        Tuple of (commit_datetime, package_results) or (commit_datetime, None) if there was an error
    """
    repo_path, commit_hash, commit_datetime = args
    
    try:
        result = subprocess.run(
            ["git", "show", f"{commit_hash}:index.html"],
            check=True, capture_output=True, text=True, cwd=repo_path
        )
        package_results = parse_html_results(result.stdout)
        return commit_datetime, package_results
    except Exception as e:
        print(f"Error processing commit {commit_hash[:8]} ({commit_datetime}): {e}")
        return commit_datetime, None

def parse_html_results(html_content):
    """
    Parse HTML content and extract test results.
    
    Args:
        html_content: HTML string
        
    Returns:
        Dictionary of package results
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract package results
    package_results = {}
    
    # Find all package rows
    wheel_rows = soup.select('tr.wheel-line')
    
    for row in wheel_rows:
        # Get package name
        package_name_elem = row.select_one('td.wheel-name')
        if not package_name_elem:
            continue
            
        package_name = package_name_elem.text.strip()
        package_results[package_name] = {}
        
        # Get all test columns
        test_columns = row.select('td.test-column')
        
        for col in test_columns:
            # Extract distribution name from class
            dist_class = col.get('class', [])
            if not dist_class or len(dist_class) < 2:
                continue
            
            # Use element-only indexing to avoid whitespace text nodes
            col_index = col.parent.find_all('td').index(col)
            
            # Find the corresponding header cell
            header_row = soup.select_one('thead tr')
            if header_row:
                header_cells = header_row.find_all('th')
                if col_index < len(header_cells):
                    dist_name = header_cells[col_index].text.strip()
                else:
                    dist_name = dist_class[1].split('-')[-1]
            else:
                dist_name = dist_class[1].split('-')[-1]
            
            if 'package-pip' in dist_class or 'package-os' in dist_class:
                # Initialize distribution results with default values
                dist_results = {
                    "test-passed": False,
                    "build-required": False,
                    "binary-wheel": False,
                    "slow-install": False,
                    "latest-version": None,
                    "installed-version": None,
                    "timeout": False,
                    "runtime": 0.0,
                    "output": ""
                }
                
                # Check for passed badge
                passed_badge = col.select_one('span.passed.badge')
                if passed_badge and 'passed' in passed_badge.text:
                    dist_results["test-passed"] = True
                
                # Check for installed version
                version_badge = col.select('span.passed.badge')
                for badge in version_badge:
                    if 'installed version' in badge.text:
                        version_match = re.search(r'installed version ([\d\.]+)', badge.text)
                        if version_match:
                            dist_results["installed-version"] = version_match.group(1)
                            # Assume latest version is the same as installed version
                            dist_results["latest-version"] = version_match.group(1)
                
                # Check for build required badge
                build_badge = col.select_one('span.build.badge')
                if build_badge and 'build' in build_badge.text:
                    dist_results["build-required"] = True
                
                # Check for binary wheel badge
                binary_badge = col.select_one('span.binary.badge')
                if binary_badge and 'binary' in binary_badge.text:
                    dist_results["binary-wheel"] = True
                
                # Check for slow install badge
                slow_badge = col.select_one('span.slow.badge')
                if slow_badge and 'slow' in slow_badge.text:
                    dist_results["slow-install"] = True
                
                # Check for timeout badge
                timeout_badge = col.select_one('span.timeout.badge')
                if timeout_badge and 'timeout' in timeout_badge.text:
                    dist_results["timeout"] = True
                
                package_results[package_name][dist_name] = dist_results
    
    return package_results

def save_results(results, output_path=None):
    """
    Save the extracted results to a JSON file in the current working directory.
    
    Args:
        results: Dictionary of results
        output_path: Path to the output file (optional)
        
    Returns:
        Path to the saved file
    """
    if output_path is None:
        # Generate a filename with current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_path = os.path.join(os.getcwd(), f"extracted-results-{timestamp}.json")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to {output_path}")
    return output_path

def main():
    parser = argparse.ArgumentParser(description='Extract test results from multiple commits.')
    parser.add_argument('--repo', type=str, default='arm64-python-wheel-tester-pages',
                        help='Path to the repository (default: arm64-python-wheel-tester-pages)')
    parser.add_argument('--commits', type=int, default=10,
                        help='Number of commits to process if commit-range is not specified (default: 10)')
    parser.add_argument('--commit-range', type=str,
                        help='Git commit range (e.g., "abcdef..master")')
    parser.add_argument('--output', type=str,
                        help='Output file path (default: extracted-results-TIMESTAMP.json)')
    parser.add_argument('--processes', type=int, default=multiprocessing.cpu_count(),
                        help=f'Number of processes to use (default: {multiprocessing.cpu_count()})')
    args = parser.parse_args()
    
    # Initialize the results structure
    results = {"executions": {}}
    
    # Get the list of commits
    commits = get_commit_list(args.repo, args.commit_range, args.commits)
    print(f"Found {len(commits)} commits to process")
    
    try:
        # Prepare arguments for multiprocessing
        process_args = [(args.repo, commit_hash, commit_datetime) for commit_hash, commit_datetime in commits]
        
        # Process commits in parallel with a progress bar
        with Pool(processes=args.processes) as pool:
            for commit_datetime, package_results in tqdm(
                pool.imap_unordered(process_commit, process_args),
                total=len(commits),
                desc="Processing commits"
            ):
                if package_results is not None:
                    results["executions"][commit_datetime] = package_results
                else:
                    print(f"Failed to extract test results for {commit_datetime}")
        
        # Save all results to a single JSON file
        output_path = args.output
        if not output_path:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_path = os.path.join(os.getcwd(), f"extracted-results-{timestamp}.json")
        
        save_results(results, output_path)
        
        print(f"Processed {len(results['executions'])} commits successfully")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
