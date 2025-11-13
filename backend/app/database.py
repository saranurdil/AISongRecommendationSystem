import os
import pandas as pd

# load data from CSV
def load_tracks_data():
    """
    Load tracks data from the local CSV file
    """
    try:
        csv_path = os.path.join(os.path.dirname(__file__), 'cleaned_tracks.csv')
        df = pd.read_csv(csv_path)
        print(f"Loaded {len(df)} records from CSV")
        return df
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return None
