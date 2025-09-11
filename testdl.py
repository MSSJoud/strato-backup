import pandas as pd
import asf_search as asf
import os

def download_first_url(csv_path):
    """
    Downloads the first URL from the specified CSV file to the current directory.

    Args:
        csv_path (str): Path to the CSV file containing the URLs.
    """
    # Load CSV and fetch the first URL
    try:
        granules = pd.read_csv(csv_path)
        first_url = granules.iloc[0]['URL']
        filename = first_url.split('/')[-1]

        # Authenticate ASF Session
        username = os.getenv('ASF_USERNAME')
        password = os.getenv('ASF_PASSWORD')
        if not username or not password:
            raise ValueError("ASF_USERNAME and ASF_PASSWORD must be set as environment variables.")

        session = asf.ASFSession().auth_with_creds(username, password)

        # Download the file using the ASF session
        print(f"Downloading {filename} to the current directory...")
        response = asf.download_url(first_url, session=session)
        
        # Save the file
        with open(filename, 'wb') as file:
            file.write(response.content)

        print(f"Downloaded: {filename}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    csv_file = './LakeVictoria/filter_granules.csv'  # Update with your CSV file name if different
    download_first_url(csv_file)
