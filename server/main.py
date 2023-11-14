import flask
import random
import json
import waitress
from flask_cors import CORS
from flask import request, render_template, session, redirect
import os
import dotenv
import sys
import uuid
import string

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

# This dict holds information about "parties", or a group of users
# playing the game together.
party_sessions = {}

class CelebManager:
    """
    Manage the available celebrities. This class opens and contains the 
    list of celebs, while also holding the only methods the program should
    use when attempting to get info about or perform actions on a celebrity.
    The main reason this exists is to convert relative image URLs to absolute
    URLs.
    """
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

def generate_room_code():
    """
    Generate a random room code that is five characters long and only 
    includes alphabetical characters, from A-Z uppercase or lowercase.
    """
    return "".join([string.ascii_letters[random.randint(0, 51)] for _ in range(5)])

def remove_from_party(party_code: str, user: str):
    """
    Checks if a user is in a party and removes them if so.
    """
    # Check if the provided code is a valid party and if the user specified
    # is a member of the party. If so, remove the members from the party. We
    # added the second condition to not raise an error if the user does not 
    # exist in the party.
    if (party := party_sessions.get(party_code)) and (user in party["members"]):
        index = party["members"].index(user)
        party["members"].pop(index)
        party["scores"].pop(index)
        
        party_sessions[party_code] = party

    # Check if the party has any remaining members. If not, remove the party
    # from the dict of party sessions. 
    # First, we check if the party exists. If it doesn't, we return the default
    # value {} to not raise an error when attempting to use the .get() method.
    # We then check if the next dict contains members and if the members
    # list has any members. 
    if party_sessions.get(party_code, {}).get("members", False) == []:
        party_sessions.pop(party_code, None)

@app.route('/', methods=["GET"])
def index():
    """
    Navigating to the index of the site will simply redirect 
    a user to the game. This may be changed in the future to
    a welcome page.
    """
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

    # Get the symbolic amount a user guesses.
    # This is thousand, million, billion, or trillion
    guess_amt = req_data.get("guess_amt")

    # Multiply the user's guess by the symbolic guess amount
    guess *= guess_amount_key[guess_amt]

    celeb = celeb_manager.get_celeb(session.get("celeb"))

    if not celeb:
        return {
            "message": "You are not currently in a game.",
            "statcode": "nogame"
            }, 400

    # Convert the net worth of the celeb to an integer
    # and format the string into an integer-convertible format    
    networth = int(celeb["networth"].replace("$", "").replace(",", ""))

    # Calculate the barriers in which the user will get points
    # if they are in or touch.
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

    # Add points to the customer's score and return their score
    session["score"] += points
    response["score"] = session["score"]

    if party := session.get("party_code", False):
        user_index = party_sessions[party]["members"].index(session.get("user_key", None))

        party_sessions[party]["scores"][user_index] += points
    

    return response, 200

@app.route('/game/restart', methods=["GET"])
def restart():
    """
    Reset the game. This resets the game score and
    celebs to zero.
    """
    session["celeb"] = None
    session["score"] = 0
    return "OK", 200

@app.route('/manage/imageError', methods=["POST"])
def image_error():
    """
    Send diagnostic data to the server in the event
    that an image fails to load. This will be so we
    can replace the image if too many clients report 
    it as unnaccessable.
    """

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

@app.route('/game/party/create', methods=["POST"])
def game_party():
    """
    Start a party session that other players can join.
    """
    data = request.get_json()

    # Get the user-provided passcode, random party code,
    # and user key.
    passcode = data.get("passcode", None)
    party_code = generate_room_code()
    user_key = session.get("user_key", str(uuid.uuid4()))

    # Generate a different room code until one that
    # is not being used is generated.
    while party_sessions.get(party_code, False):
        party_code = generate_room_code()

    # Remove the user from their old party if they 
    # were in one before creating this one
    if old_code := session.get("party_code", False):
        remove_from_party(old_code, user_key)

    # Record the user's key and party code in their
    # session
    session["user_key"] = user_key
    session["party_code"] = party_code

    # Record the new party in the party_sessions dict
    party_sessions[party_code] = {"members": [user_key], "scores": [0]}

    # Add the passcode to the party_sessions dict, if 
    # applicable
    if passcode:
        party_sessions[party_code]["passcode"] = passcode

    return {"room_code": party_code, "message": "Room successfully created!"}, 200

@app.route('/game/party/join', methods=["GET"])
def game_party_join():
    """
    Join a party session.
    """
    code = request.args.get("code", None)
    passcode = request.args.get("passcode", None)

    if not code:
        return {"message": "No party code provided"}, 400
    
    party_info = party_sessions.get(code, None)

    if not party_info:
        return {"message": "Party not found"}, 404
    
    party_passcode = party_info.get("passcode", None)
    
    if (party_passcode and party_passcode != passcode):
        return {"message": "Incorrect passcode"}, 403

    user_key = session.get("user_key", str(uuid.uuid4()))

    # Remove the user from a party if the user is found
    # to be in another party 
    if old_party := session.get("party_code", False):
        remove_from_party(old_party, user_key)

    party_info["members"].append(user_key)
    party_info["scores"].append(0)

    session["user_key"] = user_key
    session["party_code"] = code

    party_sessions[code] = party_info

    return {"message": "Successfully joined party"}, 200

@app.route('/game/party/leave', methods=["GET"])
def party_leave():
    """
    Leave the currently active party.
    """
    code = session.get("party_code", None)
    user = session.get("user_key", None)

    remove_from_party(code, user)

    return {"message": "Successfully removed from party"}, 200

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
