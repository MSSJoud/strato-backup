#!/usr/bin/env python3
"""
Download Interferograms Script

Description:
Downloads interferograms from URLs listed in a CSV file. Supports authentication via:
1. Earthdata Login Token
2. .netrc file
3. credentials.py (username/password)

Usage:
    python3 download_interferograms.py --input_csv <path_to_csv> --output_dir <path_to_output_directory>

Arguments:
    --input_csv: Path to the CSV file containing interferogram URLs and optional metadata.
    --output_dir: Directory to save the downloaded files.
"""

import os
import pandas as pd
from asf_search import ASFSession, download_url
import argparse
import sys


def authenticate():
    """
    Authenticate with ASF services using the following priority:
    1. Token from a local file.
    2. Credentials in ~/.netrc.
    3. Credentials from credentials.py.
    Returns:
        ASFSession: An authenticated ASF session object.
    """
    session = ASFSession()

    # Try token authentication
    token_file = os.path.expanduser("~/earthdata_token.txt")
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            token = f.read().strip()
        try:
            session.auth_with_token(token)
            print("Authenticated with Earthdata token.")
            return session
        except Exception as e:
            print(f"Token authentication failed: {e}")

    # Try .netrc authentication
    try:
        session.auth_with_creds(None, None)  # Uses .netrc implicitly
        print("Authenticated with .netrc.")
        return session
    except Exception as e:
        print(f".netrc authentication failed: {e}")

    # Try credentials.py
    try:
        from credentials import ASFUsr, ASFPwd
        session.auth_with_creds(ASFUsr, ASFPwd)
        print("Authenticated with credentials.py.")
        return session
    except Exception as e:
        print(f"Credentials.py authentication failed: {e}")

    # If all methods fail
    print("Authentication failed. Please check your credentials or token.")
    sys.exit(1)


def download_granules(input_csv, output_dir):
    """
    Download granules from URLs in a CSV file.
    Args:
        input_csv (str): Path to the CSV file containing granule URLs.
        output_dir (str): Directory to save the downloaded files.
    """
    session = authenticate()

    # Read CSV
    data = pd.read_csv(input_csv)

    # Check for case-insensitive 'URL' column
    url_column = next((col for col in data.columns if col.lower() == 'url'), None)
    if not url_column:
        raise ValueError("CSV file must contain a 'URL' column.")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Download files
    for _, row in data.iterrows():
        url = row[url_column]
        filename = os.path.basename(url)
        filepath = os.path.join(output_dir, filename)

        if os.path.exists(filepath):
            print(f"{filename} already exists. Skipping.")
            continue

        try:
            download_url(url, session=session, path=output_dir)
            print(f"Downloaded {filename} to {filepath}")
        except Exception as e:
            print(f"Failed to download {filename}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Download granules from a CSV file.")
    parser.add_argument('--input_csv', required=True, help="Path to the CSV file containing granule URLs.")
    parser.add_argument('--output_dir', required=True, help="Directory to save the downloaded granules.")
    args = parser.parse_args()

    download_granules(args.input_csv, args.output_dir)


if __name__ == "__main__":
    main()
