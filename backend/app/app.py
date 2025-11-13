from flask import Flask, jsonify, request
from scripts.songs import songs_bp
from scripts.recommender import initialize_recommender, run_batch_evals
from flask_cors import CORS
from ui import ui
from database import load_tracks_data

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# initialize the recommender once
with app.app_context():
    initialize_recommender()

app.register_blueprint(songs_bp)
app.register_blueprint(ui)

# API Endpoints

@app.route('/')
def health():
    return jsonify({
        "status": "ok",
        "service": "song-recommender-api",
        "version": "0.1.0",
        "endpoints": ["/songs/search", "/songs/recommend", "/songs/details/<track_id>", "/evaluate_model"]
    })

# this is a test route
@app.route('/test_connection')
def test_connection():
    try:
        df = load_tracks_data()

        # fetch the first 5 rows
        if df is not None:
            sample_data = df.head(5).to_dict('records')
            
            # return the data as a JSON response 
            return jsonify({
                "message": "Successfully loaded data from CSV!",
                "data": sample_data
            })
        else:
            return jsonify({"error": "Failed to load CSV data"}), 500
    except Exception as e:
        # return an error message
        return jsonify({"error": str(e)}), 500

@app.route('/evaluate_model')
def evaluate_model():

    # pick a number of songs to test
    # default to 100 for practicality and speed
    n = request.args.get('n', default=100, type=int)
    
    avg_metrics = run_batch_evals(n_songs=n)
    return jsonify(avg_metrics)

if __name__ == '__main__':
    app.run(debug=True)