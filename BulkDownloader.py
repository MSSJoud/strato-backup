import os
import sys
import csv
import signal
from pathlib import Path
import asf_search as asf

# Global abort flag
abort = False

# Signal handler to catch interrupts (e.g., Ctrl+C)
def signal_handler(sig, frame):
    global abort
    print("\n > Caught signal. Exiting!")
    abort = True
    sys.exit()

# Custom bulk downloader class
class BulkDownloader:
    def __init__(self, csv_path, output_dir):
        self.csv_path = csv_path
        self.output_dir = Path(output_dir)
        self.total_bytes = 0
        self.total_files = 0
        self.failed_downloads = []
        self.successful_downloads = []
        self.session = self.authenticate()

    def authenticate(self):
        # Load ASF credentials from environment variables
        username = os.getenv("ASF_USERNAME")
        password = os.getenv("ASF_PASSWORD")
        if not username or not password:
            raise ValueError("ASF_USERNAME and ASF_PASSWORD must be set as environment variables.")
        return asf.ASFSession().auth_with_creds(username, password)

    def process_csv(self):
        """Process the CSV file to extract URLs and metadata."""
        granules = []
        try:
            with open(self.csv_path, mode='r') as file:
                reader = csv.DictReader(file)
                if 'URL' not in reader.fieldnames or 'Ascending or Descending?' not in reader.fieldnames:
                    raise ValueError("CSV file must include 'URL' and 'Ascending or Descending?' columns.")
                for row in reader:
                    granules.append({
                        'url': row['URL'],
                        'orbit': row['Ascending or Descending?'].strip().lower()
                    })
        except Exception as e:
            print(f"Error processing CSV: {e}")
            sys.exit(1)
        return granules

    def download_file(self, granule):
        """Download a single granule file."""
        granule_url = granule['url']
        orbit_type = granule['orbit']
        filename = Path(granule_url).name
        orbit_dir = self.output_dir / orbit_type
        orbit_dir.mkdir(parents=True, exist_ok=True)
        file_path = orbit_dir / filename

        if file_path.exists():
            print(f"File {filename} already exists. Skipping download.")
            return

        print(f"Downloading {filename} to {file_path}")
        try:
            asf.download_url(granule_url, session=self.session, path=str(file_path.parent))
            self.successful_downloads.append(filename)
            print(f"Successfully downloaded: {filename}")
        except Exception as e:
            self.failed_downloads.append(granule_url)
            print(f"Failed to download {filename}: {e}")

    def download_granules(self):
        """Download all granules listed in the CSV."""
        granules = self.process_csv()
        self.total_files = len(granules)
        print(f"Found {self.total_files} granules to download.")

        for granule in granules:
            if abort:
                print("Download aborted!")
                break
            self.download_file(granule)

        print(f"\nDownload complete: {len(self.successful_downloads)} succeeded, {len(self.failed_downloads)} failed.")

if __name__ == "__main__":
    # Set up signal handler for interrupt
    signal.signal(signal.SIGINT, signal_handler)

    # Command-line arguments
    if len(sys.argv) != 3:
        print("Usage: python bulk_downloader.py <path_to_csv> <output_directory>")
        sys.exit(1)

    csv_path = sys.argv[1]
    output_dir = sys.argv[2]

    # Ensure paths are valid
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        sys.exit(1)
    if not os.path.isdir(output_dir):
        print(f"Error: Output directory does not exist at {output_dir}")
        sys.exit(1)

    # Start downloading
    downloader = BulkDownloader(csv_path, output_dir)
    downloader.download_granules()
