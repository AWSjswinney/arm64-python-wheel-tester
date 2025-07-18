#!/usr/bin/env python3
"""
Extract test results from the index.html file in the arm64-python-wheel-tester-pages directory
and save them in JSON format, matching the structure of the test results JSON files.
"""

import os
import json
import re
import subprocess
from datetime import datetime
from bs4 import BeautifulSoup
import shutil

def get_commit_datetime():
    """Get the commit datetime from git for the pages repository."""
    try:
        # Get the commit datetime in YYYY-MM-DD format
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ad", "--date=format:%Y-%m-%d"],
            check=True, capture_output=True, text=True, cwd="arm64-python-wheel-tester-pages"
        )
        commit_date = result.stdout.strip()
        return commit_date
    except subprocess.CalledProcessError as e:
        print(f"Warning: Could not get commit datetime: {e}")
        # Fallback to current date
        return datetime.now().strftime("%Y-%m-%d")

def get_html_content():
    """
    Get the index.html content from the arm64-python-wheel-tester-pages directory.
    Creates a temporary file in the current working directory.
    """
    # Create a temporary directory in the current working directory
    temp_dir = os.path.join(os.getcwd(), "temp_pages")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Path to the temporary index.html file
    html_path = os.path.join(temp_dir, "index.html")
    
    try:
        # Path to the source index.html file
        source_path = os.path.join(os.getcwd(), "arm64-python-wheel-tester-pages", "index.html")
        
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"index.html not found at {source_path}")
        
        # Copy the index.html file
        shutil.copy2(source_path, html_path)
        
        return html_path
    except Exception as e:
        print(f"Error getting HTML content: {e}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise

def parse_html_results(html_path):
    """Parse the index.html file and extract test results."""
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Get the commit datetime from git
    test_datetime = get_commit_datetime()
    
    # Extract package results
    package_results = {}
    
    # Find all package rows
    wheel_rows = soup.select('tr.wheel-line')
    
    for row in wheel_rows:
        # Get package name
        package_name = row.select_one('td.wheel-name').text.strip()
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
    
    # Create the new structure with test datetime
    results = {
        "executions": {
            test_datetime: package_results
        }
    }
    
    return results

def save_results(results, output_path=None):
    """Save the extracted results to a JSON file in the current working directory."""
    if output_path is None:
        # Generate a filename with current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_path = os.path.join(os.getcwd(), f"extracted-results-{timestamp}.json")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to {output_path}")
    return output_path

def main():
    temp_dir = None
    try:
        # Get the index.html content from the local repository
        html_path = get_html_content()
        temp_dir = os.path.dirname(html_path)
        
        # Parse HTML and extract results
        results = parse_html_results(html_path)
        
        # Save results to JSON file
        output_path = save_results(results)
        
        print(f"Successfully extracted test results from {html_path}")
        print(f"Found data for {len(results['executions'][list(results['executions'].keys())[0]])} packages")
    
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    return 0

if __name__ == "__main__":
    exit(main())
