from flask import Blueprint, render_template, request, redirect, url_for
import requests

ui = Blueprint("ui", __name__)

API_BASE = "http://127.0.0.1:5000"  # same server during local dev

@ui.route("/")
def home():
    return redirect(url_for("ui.search_page"))

@ui.route("/search")
def search_page():
    q = request.args.get("q", "").strip()
    results = []
    message = None
    if q:
        try:
            r = requests.get(f"{API_BASE}/songs/search", params={"q": q})
            data = r.json()
            results = data.get("results", [])
            message = data.get("message")
        except Exception as e:
            message = f"Error: {e}"
    return render_template("search.html", q=q, results=results, message=message)

@ui.route("/songs/<track_id>")
def details_page(track_id):
    data = {}
    try:
        r = requests.get(f"{API_BASE}/songs/details/{track_id}")
        data = r.json()
    except Exception as e:
        data = {"error": str(e)}
    return render_template("details.html", song=data)
# the legacy enpoint we have ("/songs/recommend") which is sample based is still there but the UI will now call the full db
@ui.route("/recommend")
def recommend_page():
    track_id = request.args.get("track_id")
    song = request.args.get("song")
    payload = {}
    try:
        params = {"k": 10}  # tweak if we want a different default
        if request.args.get("k"): params["k"] = int(request.args.get("k"))
        if request.args.get("same_genre") is not None:
            params["same_genre"] = request.args.get("same_genre")

        if track_id:
            params["track_id"] = track_id
        elif song:
            params["song"] = song
        else:
            return redirect(url_for("ui.search_page"))

        # Use the full-dataset recommender
        r = requests.get(f"{API_BASE}/songs/recommend_full", params=params)
        payload = r.json()
    except Exception as e:
        payload = {"error": str(e)}
    return render_template("recommend.html", data=payload)
