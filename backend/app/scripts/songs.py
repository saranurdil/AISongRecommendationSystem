from flask import Blueprint, request, jsonify
from database import supabase

songs_bp = Blueprint('songs_bp', __name__, url_prefix='/songs')

@songs_bp.route('/search')
def search_songs():

    search_query = request.args.get('q')

    if not search_query:
        return jsonify({"error": "A search query 'q' is required."}), 400

    try:
        response = supabase.table('cleaned_tracks_set').select("track_name, artists, album_name").ilike('track_name', f'{search_query}%').limit(20).execute()

        return jsonify({
            "message": f"Found {len(response.data)} results for '{search_query}'", 
            "results": response.data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
