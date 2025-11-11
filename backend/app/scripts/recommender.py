import pandas as pd
import os
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity
from database import supabase

# global variables
similarity_matrix = None
df_sample = None
indices = None

def initialize_recommender():

    global similarity_matrix, df_sample, indices
    print("Intializing recommender engine...")

    # LOAD THE DATA
    # fetch data from the database.
    try:
        response = supabase.table('cleaned_tracks_set').select('*').limit(10000).execute()

        if not response.data:
            print("Error. No data returned from Supabase")
            return

        # convert JSON response to DataFrame
        df_sample = pd.DataFrame(response.data)
        print(f"Loaded {len(df_sample)} records from the database")

        # ML PREPROCESSING
        numerical_features = ['danceability', 'energy', 'loudness', 'tempo', 'valence']

        # drop the rows if essential data is missing
        df_sample = df_sample.dropna(subset=numerical_features + ['track_genre', 'track_search']).reset_index(drop=True)

        # scale the numeric values so that the model understands it
        scaler = MinMaxScaler()
        X_numerical_scaled = pd.DataFrame(
            scaler.fit_transform(df_sample[numerical_features]),
            columns=numerical_features,
            index=df_sample.index
        )

        # one-hot encoding for track genres
        genre_encoded = pd.get_dummies(df_sample['track_genre'], prefix='genre')
        final_features = pd.concat([X_numerical_scaled, genre_encoded], axis=1)

        # CALCULATE SIMILARITY 
        similarity_matrix = cosine_similarity(final_features)

        # create indices map
        indices = pd.Series(df_sample.index, index=df_sample['track_search'].str.lower())
        indices = indices[~indices.index.duplicated(keep='first')]

        print("Engine ready")
    
    except Exception as e:
        print(f"Failed to initialize recommender: {e}")

def get_ml_recommendations(song_title):
    if similarity_matrix is None:
        return {"error": "Recommender is still initializing or failed."}

    song_title = song_title.lower()

    # get the index of the song
    try:
        idx = indices[song_title]
    except KeyError:
        print(song_title)
        return {f"error": "Song not found in the currently loaded sample"}
    
    # get the pairwise similarity score of all songs with the song entered by the user
    sim_scores = list(enumerate(similarity_matrix[idx]))

    # sort the songs based on the similarity score (descending)
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

    # get top 5 songs with highest similarity scores
    sim_scores = sim_scores[1:6]

    # get the songs' indices
    song_indices = [i[0] for i in sim_scores]

    # return recommended songs info
    return df_sample[['track_name', 'artists', 'track_genre', 'track_search']].iloc[song_indices].to_dict(orient='records')


def get_loaded_track_ids():
    """
    Return list of track_ids present in the in-memory df_sample.
    Read-only; no model changes.
    """
    if df_sample is None or 'track_id' not in df_sample.columns:
        return []
    # ensure str for consistent comparison
    return df_sample['track_id'].dropna().astype(str).tolist()


def get_title_for_id(track_id):
    """
    If the given track_id is in the in-memory sample, return the normalized title
    (track_search if available, else track_name). Otherwise return None.
    """
    if df_sample is None:
        return None
    # ensure same dtype comparison
    mask = df_sample['track_id'].astype(str) == str(track_id)
    if not mask.any():
        return None
    row = df_sample.loc[mask].iloc[0]
    title = None
    if 'track_search' in df_sample.columns and pd.notna(row.get('track_search')):
        title = row.get('track_search')
    elif 'track_name' in df_sample.columns and pd.notna(row.get('track_name')):
        title = row.get('track_name')
    return str(title).strip() if title else None
