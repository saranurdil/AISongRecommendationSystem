from flask import Blueprint, request, jsonify
from database import load_tracks_data
from .recommender import get_ml_recommendations, get_loaded_track_ids, get_title_for_id
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity

songs_bp = Blueprint('songs_bp', __name__, url_prefix='/songs')

# load data once
df_full = load_tracks_data()

def search_in_dataframe(df, track_id=None, track_search=None, track_name=None, artists=None):
    """
    search for tracks in the DataFrame
    """
    if df is None or len(df) == 0:
        return None
    
    result = df.copy()
    
    if track_id:
        result = result[result['track_id'].astype(str) == str(track_id)]
    
    if track_search:
        # exact match for track_search
        result = result[result['track_search'].str.lower() == track_search.lower()]
    
    if track_name and artists:
        # match for track_name and partial match for artists
        result = result[
            (result['track_name'].str.lower() == track_name.lower()) & 
            (result['artists'].str.lower().str.contains(artists.lower(), na=False))
        ]
    elif track_name:
        # starts-with search for track_name
        result = result[result['track_name'].str.lower().str.startswith(track_name.lower(), na=False)]
    
    return result

@songs_bp.route('/recommend')
def recommend_songs():

    # Accept either exact song title OR track_id
    target_song = request.args.get('song')
    track_id = request.args.get('track_id')

    # If track_id is provided and no title, try to use the in-memory sample title
    if track_id and not target_song:
        # First, check if this id is in the preloaded sample
        sample_title = get_title_for_id(track_id)
        if sample_title:
            target_song = sample_title  # use normalized title from sample
        else:
            # Not in sample; we can still look up DB to confirm the id exists,
            # but we will return a clear message that recommendation needs an in-sample track.
            
            result = search_in_dataframe(df_full, track_id=track_id)
            if result is None or len(result) == 0:
                return jsonify({"error": f"No song found for track_id={track_id}"}), 404
            
            row = result.iloc[0]
            return jsonify({
                "error": "This track is not in the currently loaded sample for recommendations.",
                "track_id": track_id,
                "track_name": row.get("track_name"),
                "track_search": row.get("track_search"),
                "hint": "Use /songs/search and pick a result where in_sample=true, then call /songs/recommend with that track_id."
            }), 409

    if not target_song:
        return jsonify({"error": "Provide either 'song' (title) or 'track_id'"}), 400

    # call the recommender by title (no changes to their logic)
    recommendations = get_ml_recommendations(target_song)

    if isinstance(recommendations, dict) and "error" in recommendations:
        return jsonify(recommendations), 404

    # attach track_id for each recommendation
    enriched = []
    for rec in (recommendations or []):
        # we'll try exact match on 'track_search' 
        track_search = (rec.get("track_search") or "").strip()
        track_name = (rec.get("track_name") or "").strip()
        artists = (rec.get("artists") or "").strip()
        tid = None
        
        # look up track_id from full dataset
        result = search_tracks(track_search=track_search)
        if result is not None and len(result) > 0:
            tid = result.iloc[0]['track_id']

        else:
            # fallback: try (track_name + artists) if needed
            result = search_tracks(track_name=track_name, artists=artists)
            tid = result.iloc[0]['track_id'] if result is not None and len(result) > 0 else None

        rec = dict(rec)
        if tid:
            rec["track_id"] = tid
        enriched.append(rec)

    return jsonify({
        "input": target_song,
        "recommendations": enriched
    })



@songs_bp.route('/search')
def search_songs():

    search_query = request.args.get('q')

    if not search_query:
        return jsonify({"error": "A search query 'q' is required."}), 400

    try:
        # search in the full dataset
        if df_full is not None:

            # partial matching
            mask = df_full['track_name'].str.lower().str.contains(search_query.lower(), na=False)
            results_df = df_full[mask]

        else:
            results_df = pd.DataFrame()
        
        # limit to 20 results
        results_df = results_df.head(20)
        
        loaded_ids = set(get_loaded_track_ids())
        results = []
        
        for _, row in results_df.iterrows():
            result_item = {
                "track_id": row.get("track_id"),
                "track_name": row.get("track_name"),
                "artists": row.get("artists"),
                "album_name": row.get("album_name"),
                "in_sample": (str(row.get("track_id")) in loaded_ids)
            }
            results.append(result_item)

        return jsonify({
            "message": f"Found {len(results)} results for '{search_query}'", 
            "results": results
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@songs_bp.route('/details/<track_id>')
def get_song_details(track_id):
    try:
        result = search_in_dataframe(df_full, track_id=track_id)
        if result is None or len(result) == 0:
            return jsonify({"error": f"No song found for track_id={track_id}"}), 404
        
        return jsonify(result.iloc[0].to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@songs_bp.route('/recommend_full')
def recommend_full():
    """
    Full-dataset recommendations (no dependency on in-memory sample).
    Params:
      - track_id OR song (prefer exact 'track_search' like 'Love Song - Sara Bareilles')
      - k (int, default 10)
      - same_genre (bool, default true)
    """
    target_song = request.args.get('song', type=str)
    track_id = request.args.get('track_id', type=str)
    k = request.args.get('k', default=10, type=int)
    same_genre = request.args.get('same_genre', default='true', type=str).lower() == 'true'

    if not (target_song or track_id):
        return jsonify({"error": "Provide either 'song' or 'track_id'"}), 400

    if df_full is None:
        return jsonify({"error": "Dataset not loaded"}), 500

    # resolve target row from DB
    try:
        if track_id:
            target_df = search_in_dataframe(df_full, track_id=track_id)
        else:
            # prefer exact match on track_search = "Title - Artist"
            target_df = search_in_dataframe(df_full, track_search=target_song)
            if target_df is None or len(target_df) == 0:
                # fallback: try track_name ilike (first match)
                target_df = search_in_dataframe(df_full, track_name=target_song)
        
        if target_df is None or len(target_df) == 0:
            return jsonify({"error": "Target song not found in dataset."}), 404
        
        target = target_df.iloc[0]
    except Exception as e:
        return jsonify({"error": f"Lookup failed: {e}"}), 500

    # fetch candidate rows (entire table or filtered by genre) 
    feature_cols = [
        'danceability', 'energy', 'loudness', 'tempo', 'valence'
    ]
    meta_cols = ["track_id", "track_name", "artists", "track_genre", "track_search"]

    try:
        # filter candidates
        candidates = df_full.copy()
        if same_genre and target.get("track_genre"):
            candidates = candidates[candidates['track_genre'] == target["track_genre"]]
        
        # exclude the target itself
        candidates = candidates[candidates['track_id'] != target['track_id']]
        
        if len(candidates) == 0:
            return jsonify({"input": target.get("track_search") or target.get("track_name"), "recommendations": []})

        # vectorize + similarity
        # build DataFrame for candidates and target
        df_candidates = candidates[meta_cols + feature_cols].copy()
        
        # numeric dtype, replace missing with 0
        for col in feature_cols:
            df_candidates[col] = pd.to_numeric(df_candidates[col], errors="coerce").fillna(0.0)
        
        # create target vector
        t_vec = np.array([[pd.to_numeric(target.get(col, 0.0), errors="coerce") for col in feature_cols]], dtype=float)

        X = df_candidates[feature_cols].astype(float).values
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
        ts = scaler.transform(t_vec)

        sims = cosine_similarity(ts, Xs)[0]  # shape: (n_candidates,)
        df_candidates["similarity"] = sims

        # top-k similar songs
        top = df_candidates.sort_values("similarity", ascending=False).head(k)
        recs = top[["track_id", "track_name", "artists", "track_genre", "track_search", "similarity"]].to_dict(orient="records")

        return jsonify({
            "input": target.get("track_search") or target.get("track_name"),
            "same_genre": same_genre,
            "k": k,
            "recommendations": recs
        })
    except Exception as e:
        return jsonify({"error": f"Similarity calculation failed: {e}"}), 500