from flask import Blueprint, request, jsonify
from database import supabase
from .recommender import get_ml_recommendations, get_loaded_track_ids, get_title_for_id

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

    # Call Person 1's recommender by title (no changes to their logic)
    recommendations = get_ml_recommendations(target_song)

    if isinstance(recommendations, dict) and "error" in recommendations:
        return jsonify(recommendations), 404

    return jsonify({
        "input": target_song,
        "recommendations": recommendations
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
