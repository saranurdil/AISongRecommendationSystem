# Song Recommendation System

After you clone the repo, follow these setup steps:

## 1. Create a virtual environment:
`python3 -m venv venv`

## 2. Activate the virtual environment
On macOS/Linux:
`source venv/bin/activate`

On Windows:
`.\venv\Scripts\activate`

## 3. Install Dependencies
pip install -r requirements.txt

## 4. Run the application
- Go to `backend/app` directory
- Run `flask run`

## 5. Navigate through the app
The website should be shown on the local host (127.0.0.1:5000). The landing page is the search page that shows a simple search bar where a user can enter the song name or a part of the song name. Click enter to see all songs found in the dataset under that name (you can use 'Hello' as a test input). 
From the returned list of songs, you can choose to either view the song details (album, genre, tempo, valence, energy) or get recommendations. 

## More questions or lacking details?
Please check the report. This README is short because all the extensive explanation is in the written report, which is easier to type in. It goes more in detail on how our model works, its performance, and so much more!

The demo output screenshots can also be found in the report.

Thank you!
