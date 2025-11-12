from flask import Flask, jsonify
from database import supabase
from scripts.songs import songs_bp
from scripts.recommender import initialize_recommender
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# initialize the recommender once
with app.app_context():
    initialize_recommender()

app.register_blueprint(songs_bp)

# API Endpoints

@app.route('/')
def health():
    return jsonify({
        "status": "ok",
        "service": "song-recommender-api",
        "version": "0.1.0",
        "endpoints": ["/songs/search", "/songs/recommend", "/songs/details/<track_id>", "/test_connection"]
    })

# this is a test route
@app.route('/test_connection')
def test_connection():
    try:
        # fetch the first 5 rows
        response = supabase.table('cleaned_tracks_set').select("*").limit(5).execute()
        
        #  data is in the data attribute of the response
        data = response.data
        
        # return the data as a JSON response
        return jsonify({
            "message": "Successfully connected to Supabase and fetched data!",
            "data": data
        })
        
    except Exception as e:
        # return an error message
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    app.run(debug=True)