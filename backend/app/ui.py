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

@ui.route("/recommend")
def recommend_page():
    track_id = request.args.get("track_id")
    song = request.args.get("song")
    payload = {}
    try:
        if track_id:
            r = requests.get(f"{API_BASE}/songs/recommend", params={"track_id": track_id})
        elif song:
            r = requests.get(f"{API_BASE}/songs/recommend", params={"song": song})
        else:
            return redirect(url_for("ui.search_page"))
        payload = r.json()
    except Exception as e:
        payload = {"error": str(e)}
    return render_template("recommend.html", data=payload)
