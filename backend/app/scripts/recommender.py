import pandas as pd
import os
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity
from database import supabase
import time

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


def get_performance_metrics(song_title):

    # check if the song exists and get its details for comparison
    try:
        input_song_details = df_sample.iloc[indices[song_title.lower()]]
        input_genre = input_song_details['track_genre']
        input_artist = input_song_details['artists']

    except KeyError:
        return {"error": f"Song '{song_title}' not found in the sample"}

    # measure the speed
    start_time = time.time()
    recommendations = get_ml_recommendations(song_title)
    end_time = time.time()


    # calculate duration in ms
    query_duration_ms = (end_time - start_time) * 1000

    # handle if the recommendation fails
    if isinstance(recommendations, dict) and "error" in recommendations:
        return {"error": recommendations["error"]}

    # calculate quality metrics

    # find the percentage of recommendations that share the same genre
    matching_genres = 0
    for song in recommendations: 
        if song['track_genre'] == input_genre:
            matching_genres += 1
    
    # find a score from 0 to 1
    genre_relevance = matching_genres / len(recommendations)

    # find the percentage of recommendations that come from diverse artists
    different_artists = 0
    for song in recommendations:
        if song['artists'] != input_artist:
            different_artists += 1
    
    # find a score from 0 to 1
    artist_diversity = different_artists / len(recommendations)

    return{
        "input_song": song_title,
        "input_genre": input_genre,
        "query_speed_ms": round(query_duration_ms, 2),
        "metrics": {
            "genre_relevance": genre_relevance,
            "artist_diversity": artist_diversity
        },
        "recommendations": recommendations
    }

def run_batch_evals(n_songs=100):
    """
    Run the evaluation on n songs to calculate average metrics fro the whole system
    """

    if df_sample is None:
        return {"error": "Recommender not initialized."}

    # select songs to test
    test_songs = df_sample.sample(n_songs)

    total_speed = 0
    total_genre_relevance = 0
    total_artist_diversity = 0
    successful_runs = 0

    print(f"Running evaluation on {n_songs} random songs...")

    for _, song in test_songs.iterrows():
        song_title = song['track_search']
        metrics = get_performance_metrics(song_title)

        if "error" not in metrics:
            total_speed += metrics['query_speed_ms']
            total_genre_relevance += metrics['metrics']['genre_relevance']
            total_artist_diversity += metrics['metrics']['artist_diversity']
            successful_runs += 1

    if successful_runs == 0:
        return {"error": "All evaluation runs failed."}

    # return averages
    return {
        "total_songs_tested": successful_runs,
        "average_query_speed_ms": round(total_speed / successful_runs, 2),
        "average_genre_relevance": round(total_genre_relevance / successful_runs, 4),
        "average_artist_diversity": round(total_artist_diversity / successful_runs, 4)
    }