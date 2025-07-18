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
import shutil
import argparse

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

def get_html_content_for_commit(repo_path, commit_hash):
    """
    Get the index.html content for a specific commit.
    Creates a temporary file in the current working directory.
    
    Args:
        repo_path: Path to the repository
        commit_hash: Git commit hash
        
    Returns:
        Tuple of (html_path, temp_dir) or (None, None) if there was an error
    """
    # Create a temporary directory in the current working directory
    temp_dir = os.path.join(os.getcwd(), f"temp_pages_{commit_hash[:8]}")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Path to the temporary index.html file
    html_path = os.path.join(temp_dir, "index.html")
    
    try:
        # Extract the index.html content from the specific commit
        result = subprocess.run(
            ["git", "show", f"{commit_hash}:index.html"],
            check=True, capture_output=True, text=True, cwd=repo_path
        )
        
        # Write the content to the temporary file
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(result.stdout)
        
        return html_path, temp_dir
    except subprocess.CalledProcessError as e:
        print(f"Error extracting content for commit {commit_hash}: {e}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return None, None

def parse_html_results(html_path):
    """
    Parse the index.html file and extract test results.
    
    Args:
        html_path: Path to the HTML file
        
    Returns:
        Dictionary of package results
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
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
            
            # The class will be something like "test-column package-pip" or "test-column package-os"
            # We need to extract the column header to get the distribution name
            col_index = list(col.parent.children).index(col)
            
            # Find the corresponding header cell
            header_row = soup.select_one('thead tr')
            if header_row and col_index < len(list(header_row.children)):
                header_cell = list(header_row.children)[col_index]
                dist_name = header_cell.text.strip()
            else:
                # Fallback to using the class name
                dist_name = col.get('class')[0].split('-')[-1]
            
            # Check if this is a distribution we want to track
            # The class will contain something like "test-column package-pip" or "test-column package-os"
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
                
                # Add to results
                # Map the distribution name to match the format in the reference JSON
                dist_key = dist_name
                if dist_name == 'focal':
                    dist_key = 'focal'
                elif dist_name == 'focal-apt':
                    dist_key = 'focal-apt'
                elif dist_name == 'jammy':
                    dist_key = 'jammy'
                elif dist_name == 'jammy-apt':
                    dist_key = 'jammy-apt'
                elif dist_name == 'noble':
                    dist_key = 'noble'
                elif dist_name == 'amazon-linux2023':
                    dist_key = 'amazon-linux2023'
                elif dist_name == 'amazon-linux2023-yum':
                    dist_key = 'amazon-linux2023-yum'
                
                package_results[package_name][dist_key] = dist_results
    
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
    args = parser.parse_args()
    
    # Initialize the results structure
    results = {"executions": {}}
    
    # Get the list of commits
    commits = get_commit_list(args.repo, args.commit_range, args.commits)
    print(f"Found {len(commits)} commits to process")
    
    try:
        # Process each commit
        for i, (commit_hash, commit_datetime) in enumerate(commits):
            print(f"Processing commit {i+1}/{len(commits)}: {commit_hash[:8]} ({commit_datetime})")
            
            # Get the HTML content for this commit
            html_path, temp_dir = get_html_content_for_commit(args.repo, commit_hash)
            if not html_path:
                print(f"Skipping commit {commit_hash[:8]} due to error")
                continue
            
            try:
                # Parse HTML and extract results
                package_results = parse_html_results(html_path)
                
                # Add to the results structure
                results["executions"][commit_datetime] = package_results
                
                print(f"Successfully extracted test results for {len(package_results)} packages")
                
            finally:
                # Clean up temporary directory
                if temp_dir and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
        
        # Save all results to a single JSON file
        output_path = args.output
        if not output_path:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_path = os.path.join(os.getcwd(), f"extracted-results-{timestamp}.json")
        
        save_results(results, output_path)
        
        print(f"Processed {len(results['executions'])} commits")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
