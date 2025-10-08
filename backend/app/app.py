from flask import Flask, jsonify
from database import supabase

app = Flask(__name__)


# API Endpoints

@app.route('/')
def hello_world():
    return 'Hello World'

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