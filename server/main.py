import flask
import random
import json
import waitress
from flask_cors import CORS
from flask import request, render_template, session, redirect
import os
import dotenv
import sys

dotenv.load_dotenv()

app = flask.Flask(__name__)
cors = CORS(app)
app.secret_key = os.getenv("SECRET_KEY")
guess_amount_key = {
    "thousand": 1000,
    "million": 1000000,
    "billion": 1000000000,
    "trillion": 1000000000000,
}

class CelebManager:
    def __init__(self):
        with open('celebs.json') as f:
            self.celebinfo = json.load(f)
        
        self.celebs = self.celebinfo["data"]
    
    def get_random_celeb(self):
        """
        Get a random celebrity. This is done by getting a random
        raw celebrity and then returning the processed version.
        """
        return self.get_celeb(random.choice(self.celebs)["name"])

    def _get_raw_celeb(self, name):
        """
        Get celeb data right from the database, unprocessed. This
        may not include the full celeb image URL. This should only 
        be used by other methods in this class.
        """
        for celeb in self.celebs:
            if celeb["name"] == name:
                return celeb
        return None

    def get_celeb(self, name):
        """
        For self-hosted images, the image link in the database is just 
        a filename, as the database does not know where the images are going to be 
        stored. So, we need to prepend the static url path to the image link.
        """
        celeb = self._get_raw_celeb(name)

        if not celeb:
            return None
        
        celeb["image"] = self.get_celeb_image(name)
        return celeb
    
    def get_celeb_image(self, name: str | None = None, celeb: dict | None = None):
        """
        This method will return the full URL of an image for a celebrity. This is
        needed because the database only stores the filename of the image for some
        celebs, and not the full URL. This method will return the full URL every time.
        """
        if not celeb and not name:
            raise ValueError("Either name or celeb must be provided.")
        
        if not celeb:
            celeb = self._get_raw_celeb(name)

            if not celeb:
                return None
        
        if celeb["image"].startswith("http"):
            return celeb["image"]

        else:
            image = request.root_url + (app.static_url_path.strip("/")) + f"/celeb-images/{celeb['image']}"
            return image
    
    def get_celeb_from_session(self):
        """
        This method will get celeb information from the current user's session.
        """
        celeb = self.get_celeb(session.get("celeb"))

        if not celeb:
            return None

        return celeb

celeb_manager = CelebManager()

@app.route('/', methods=["GET"])
def index():
    return redirect("/game/start")

@app.route('/celeb/random', methods=["GET"])
def random_celeb():
    """
    Return a random celeb. 
    This will return either HTML or JSON depending on the format query parameter.
    """
    rceleb = celeb_manager.get_random_celeb()
    data_format = request.args.get("format")
    
    session["celeb"] = rceleb["name"]

    if data_format == "json":
        return rceleb
    
    return f"""<div>
    <h1>{rceleb["name"]}</h1>
    <img src="{rceleb["image"]}">
    <p>{rceleb["networth"]}</p>
</div>"""

@app.route('/celeb/<name>', methods=["GET"])
def celeb(name):
    """
    Return data for a certain celeb.
    Returns a 404 if the celeb does not exist.
    """
    celeb = celeb_manager.get_celeb(name)

    if celeb:
        return celeb
    
    return "No such celeb", 404

@app.route('/game/start', methods=["GET"])
def game_start():
    """
    Start a new game of NetGuessr.
    This method gets a random celebrity and stores it in the current session.
    Afterward, it returns the index file with the celeb's name and image. The net
    worth is hidden from the user until they submit their guess.
    """
    celeb = celeb_manager.get_random_celeb()

    session["celeb"] = celeb["name"]

    if not session.get("score"):
        session["score"] = 0

    return render_template("index.html", celeb_name=celeb["name"], celeb_image_url=celeb["image"], score=session["score"])

@app.route('/game/submit', methods=["POST"])
def game_submit():
    """
    This method is called when a user submits a guess to the game.
    """
    req_data = request.get_json()
    try:
        guess = int(req_data.get("guess"))
    except ValueError:
        guess = float(req_data.get("guess"))
    guess_amt = req_data.get("guess_amt")

    guess *= guess_amount_key[guess_amt]

    celeb = celeb_manager.get_celeb(session.get("celeb"))

    if not celeb:
        return {
            "message": "You are not currently in a game.",
            "statcode": "nogame"
            }, 400
    
    networth = int(celeb["networth"].replace("$", "").replace(",", ""))

    close_high = networth * 1.15
    close_low = networth * 0.85

    mid_high = networth * 1.3
    mid_low = networth * 0.7

    off_high = networth * 1.5
    off_low = networth * 0.5

    response = {}

    points = 0

    if guess == networth:
        response = {
            "message": "You got it exactly right!",
            "statcode": "onthemoney"
            }
        points = 5
    
    elif guess >= close_low and guess <= close_high:
        response = {
            "message": "You were close!",
            "statcode": "closeenough"
            }
        points = 3

    elif guess >= mid_low and guess <= mid_high:
        response = {
            "message": "You were fairly close!",
            "statcode": "middle"
            }
        points = 2

    elif guess >= off_low and guess <= off_high:
        response = {
            "message": "You were off!",
            "statcode": "off"
            }
        points = 1

    else:
        response = {
            "message": "You were way off!",
            "statcode": "wayoff"
            }
        points = 0
    
    response["celeb_data"] = celeb

    session["score"] += points
    response["score"] = session["score"]
    return response, 200

@app.route('/game/restart', methods=["GET"])
def restart():
    """
    Restart the game.
    """
    session["celeb"] = None
    session["score"] = 0
    return "OK", 200

@app.route('/manage/imageError', methods=["POST"])
def image_error():
    data = request.get_json()

    image_url = data.get("image_url")
    celeb_name = data.get("celeb")

    with open("diagnostic.json", "r") as f:
        diagnostic_data = json.load(f)
    
    diagnostic_data["image_errors"].append([
        image_url,
        celeb_name
    ])

    with open("diagnostic.json", "w") as f:
        json.dump(diagnostic_data, f, indent=4)
    
    return "Error recorded", 200

if __name__ == '__main__':
    print("App started!")

    gettrace = getattr(sys, 'gettrace', None)

    if gettrace is None:
        print('No sys.gettrace')
        waitress.serve(app, listen="*:80")
    elif gettrace():
        app.run()
    else:
        waitress.serve(app, listen="*:80")
