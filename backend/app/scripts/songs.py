from flask import Blueprint, request, jsonify
from database import supabase
from .recommender import get_ml_recommendations, get_loaded_track_ids, get_title_for_id
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity

songs_bp = Blueprint('songs_bp', __name__, url_prefix='/songs')


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
            try:
                res = supabase.table('cleaned_tracks_set')\
                    .select("track_name, track_search")\
                    .eq("track_id", track_id)\
                    .single()\
                    .execute()
                row = res.data
                if not row:
                    return jsonify({"error": f"No song found for track_id={track_id}"}), 404
                return jsonify({
                    "error": "This track is not in the currently loaded sample for recommendations.",
                    "track_id": track_id,
                    "track_name": row.get("track_name"),
                    "track_search": row.get("track_search"),
                    "hint": "Use /songs/search and pick a result where in_sample=true, then call /songs/recommend with that track_id."
                }), 409
            except Exception as e:
                return jsonify({"error": str(e)}), 500

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

        # prefer lookup by track_search (normalized "Title - Artist")
        if track_search:
            try:
                r = supabase.table('cleaned_tracks_set')\
                    .select("track_id")\
                    .eq("track_search", track_search)\
                    .single()\
                    .execute()
                if r.data and "track_id" in r.data:
                    tid = r.data["track_id"]
            except Exception:
                pass

        # fallback: try (track_name + artists) if needed
        if not tid and track_name and artists:
            try:
                r2 = supabase.table('cleaned_tracks_set')\
                    .select("track_id")\
                    .eq("track_name", track_name)\
                    .ilike("artists", f"{artists}%")\
                    .limit(1)\
                    .execute()
                if r2.data and len(r2.data) > 0 and "track_id" in r2.data[0]:
                    tid = r2.data[0]["track_id"]
            except Exception:
                pass

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
        response = supabase.table('cleaned_tracks_set')\
            .select("track_id, track_name, artists, album_name")\
            .ilike('track_name', f'{search_query}%')\
            .limit(20)\
            .execute()
        
        loaded_ids = set(get_loaded_track_ids())
        for row in response.data:
            tid = str(row.get("track_id", ""))
            row["in_sample"] = (tid in loaded_ids)


        return jsonify({
            "message": f"Found {len(response.data)} results for '{search_query}'", 
            "results": response.data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@songs_bp.route('/details/<track_id>')
def get_song_details(track_id):
    try:
        res = supabase.table('cleaned_tracks_set')\
            .select("*")\
            .eq("track_id", track_id)\
            .single()\
            .execute()
        if not res.data:
            return jsonify({"error": f"No song found for track_id={track_id}"}), 404
        return jsonify(res.data)
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

    # 1) Resolve target row from DB
    try:
        if track_id:
            t_res = supabase.table('cleaned_tracks_set')\
                .select("*").eq("track_id", track_id).single().execute()
            target = t_res.data
        else:
            # prefer exact match on track_search = "Title - Artist"
            t_res = supabase.table('cleaned_tracks_set')\
                .select("*").eq("track_search", target_song).single().execute()
            target = t_res.data
            # fallback: try track_name ilike (first match)
            if not target:
                t_res2 = supabase.table('cleaned_tracks_set')\
                    .select("*").ilike("track_name", target_song).limit(1).execute()
                target = (t_res2.data[0] if t_res2.data else None)
        if not target:
            return jsonify({"error": "Target song not found in database."}), 404
    except Exception as e:
        return jsonify({"error": f"DB lookup failed: {e}"}), 500

    # 2) Fetch candidate rows (entire table or filtered by genre) 
    feature_cols = [
        "danceability","energy","key","loudness","mode","speechiness",
        "acousticness","instrumentalness","liveness","valence","tempo",
        "time_signature","popularity","duration_ms"
    ]
    meta_cols = ["track_id","track_name","artists","track_genre","track_search"]

    try:
        base_query = supabase.table('cleaned_tracks_set').select(",".join(meta_cols + feature_cols))
        if same_genre and target.get("track_genre"):
            base_query = base_query.eq("track_genre", target["track_genre"])
        c_res = base_query.limit(20000).execute()  # safety cap

        rows = c_res.data or []
        # Exclude the target itself from candidates
        rows = [r for r in rows if str(r.get("track_id")) != str(target.get("track_id"))]
        if not rows:
            return jsonify({"input": target.get("track_search") or target.get("track_name"), "recommendations": []})
    except Exception as e:
        return jsonify({"error": f"DB fetch failed: {e}"}), 500

    # 3) vectorize + similarity
    try:
        # build DataFrame for candidates and a single-row DF for target
        df = pd.DataFrame(rows)
        # numeric dtype, replace missing with 0
        for col in feature_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        t_vec = np.array([[pd.to_numeric(target.get(col), errors="coerce") if target.get(col) is not None else 0.0
                           for col in feature_cols]], dtype=float)

        X = df[feature_cols].astype(float).values
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
        ts = scaler.transform(t_vec)

        sims = cosine_similarity(ts, Xs)[0]  # shape: (n_candidates,)
        df["similarity"] = sims

        # top-k similar rows
        top = df.sort_values("similarity", ascending=False).head(k)
        recs = top[["track_id","track_name","artists","track_genre","track_search","similarity"]].to_dict(orient="records")

        return jsonify({
            "input": target.get("track_search") or target.get("track_name"),
            "same_genre": same_genre,
            "k": k,
            "recommendations": recs
        })
    except Exception as e:
        return jsonify({"error": f"Similarity failed: {e}"}), 500
