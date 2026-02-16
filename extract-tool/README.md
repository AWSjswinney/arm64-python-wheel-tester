# Test Results Extraction Script

This script extracts test results from the index.html file in a repository
for a range of commits and saves them in JSON format, matching the structure
of the test results JSON files used by the project.

## Purpose

Instead of downloading GitHub artifacts to get previous test results, this script
allows you to extract the test results directly from multiple commits in a repository,
which contains the rendered website with all the test results.

The intent is to extract results from the `gh-pages` branch and save them in a
structured JSON format. In the future, `generate-website.py` can be updated to
consume this format directly, eliminating the need to fetch history via the GitHub
artifacts API.

## Requirements

- Python 3.7+
- BeautifulSoup4
- tqdm (for progress bar)
- Git (with access to the repository)

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the script from the `extract-tool` directory:

```bash
python extract_results.py [OPTIONS]
```

### Command-line Arguments

- `--repo PATH`: Path to the repository (default: arm64-python-wheel-tester-pages)
- `--commits N`: Number of commits to process if commit-range is not specified (default: 10)
- `--commit-range RANGE`: Git commit range (e.g., "abcdef..master")
- `--output FILE`: Output file path (default: extracted-results-TIMESTAMP.json)
- `--processes N`: Number of processes to use for parallel processing (default: number of CPU cores)

### Examples

Process the last 5 commits:

```bash
python extract_results.py --commits 5
```

Process a specific commit range:

```bash
python extract_results.py --commit-range "abcdef..master"
```

Process commits from a different repository:

```bash
python extract_results.py --repo /path/to/repo --commit-range "HEAD~5..HEAD"
```

Use 4 processes for parallel processing:

```bash
python extract_results.py --processes 4
```

## How It Works

The script will:
1. Get a list of commits in the repository based on the specified range or number
2. Process commits in parallel using multiple processes:
   - Extract the index.html content at each commit via `git show`
   - Parse the HTML to extract test results
   - Add the results to the output structure, keyed by the commit datetime
3. Display a progress bar to track the processing
4. Save all results to a single JSON file

## Integration with generate-website.py

This script is the first step toward replacing the GitHub artifacts-based history
in `generate-website.py`. The workflow will be:

1. Run this script to extract historical results from the `gh-pages` branch
2. Update `generate-website.py` to read from the extracted JSON instead of fetching artifacts
3. Going forward, save new results in this JSON format alongside the HTML

This integration is not yet complete.

## Limitations

- `runtime` and `output` fields are always default values (0.0 and "") since they
  are not present in the HTML.
- `binary-wheel` is always `false` — the HTML does not contain a distinct badge for
  this field.

## JSON Structure

The generated JSON file follows this structure:

```json
{
  "executions": {
    "YYYY-MM-DD HH:MM:SS": {
      "package_name": {
        "distribution_name": {
          "test-passed": true|false,
          "build-required": true|false,
          "binary-wheel": false,
          "slow-install": true|false,
          "latest-version": "version_string",
          "installed-version": "version_string",
          "timeout": true|false,
          "runtime": 0.0,
          "output": ""
        }
      }
    }
  }
}
```
