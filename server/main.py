import random
import json
import sys
import uuid
import string
import datetime
import os
import waitress
from flask_cors import CORS
import flask
from flask import request, render_template, session, redirect
import dotenv

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

party_sessions: dict[str, "Party"] = {}


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


class User:
    def __init__(self, user_id: str | None = None, username: str | None = None):
        self._id: str = user_id or str(uuid.uuid4())
        self.username: str = username or self._id[:5]
        self._last_interaction: datetime.datetime = datetime.datetime.now()
        self._score: int = 0
    
    @property
    def score(self):
        self._last_interaction = datetime.datetime.now()
        return self._score
    
    @score.setter
    def score(self, value):
        self._last_interaction = datetime.datetime.now()

        if value < 0:
            return
        
        self._score = value

    @property
    def key(self):
        return self._id
    
    def get_interaction_difference(self) -> datetime.timedelta:
        """
        Get the difference between the user's last interaction and
        the current time.
        """
        return datetime.datetime.now() - self._last_interaction


class Party:
    def __init__(self, passcode: str = "", initial_user: User | None = None):
        self._code: str = self.generate_room_code()
        self._passcode: str = passcode
        self._members: list[User] = []

        # Generate a different room code until one that
        # is not being used is generated
        while party_sessions.get(self._code):
            self._code = self.generate_room_code()

        # Add the initial user to the party, if they exist
        if initial_user:
            self.add_user(initial_user)

        # Add the party to the list of party sessions
        party_sessions[self._code] = self

    @staticmethod
    def generate_room_code() -> str:
        """
        Generate a random room code that is five characters long and only 
        includes alphabetical characters, from A-Z uppercase or lowercase.
        """
        return "".join([string.ascii_letters[random.randint(0, 51)] for _ in range(5)])

    def _get_user_index(self, user: User) -> int | bool:
        """
        Get the index of the user in the parallel arrays
        """
        try:
            return self._members.index(user)
        except ValueError:
            return False

    def delete_party(self) -> None:
        """
        Remove the party from party_sessions.
        """
        party_sessions.pop(self._code, None)

    def check_user(self, user: User) -> bool:
        """
        Check if a user is a member of the party.
        """
        return user in self._members

    def remove_user(self, user: User | str) -> None:
        """
        Checks if a user is in a party and removes them if so.
        """
        if isinstance(user, str):
            user = self.get_user_by_key(user)

        if not user:
            return

        # Remove the user from the list of party members and their score from the list of scores
        if self.check_user(user):
            index = self._get_user_index(user)
            self._members.pop(index)

        # If there are no more members in the party, remove it from the dict
        # of party sessions and delete it.
        if self._members == []:
            self.delete_party()

    def add_user(self, user: User) -> None:
        """
        Add a user to the party 
        """
        self._members.append(user)

    def get_user_score(self, user: User) -> int:
        """
        Get the current score of a user
        """
        index = self._get_user_index(user)

        return self._members[index].score

    def get_party_stats(self) -> dict:
        """
        Return a dictionary with a user's username and score
        """
        info = {user.username: user.score for user in self._members}

        # Sort info by player with the highest score
        info = {user.username: user.score for user in sorted(self._members, key=lambda item: item.score, reverse=True)}

        return info
        
    def add_points(self, user: User | str, points: int) -> None:
        """
        Get the amount of points a user has.
        """
        # In case a user key is passed, get the user object
        if isinstance(user, str):
            user = self.get_user_by_key(user)

        if not user:
            return

        user.score += points

    def get_user_by_key(self, user_key: str) -> User | None:
        """
        Get a user object from the party based on the 
        user's key.
        """
        for user in self._members:
            if user.key == user_key:
                return user
        
        return None

    def prune_inactive_members(self, seconds: int = 300):
        """
        Remove a member from a party if they have not
        interacted within a certain amount of time. The default
        is five minutes (300 seconds)
        """
        for member in self._members:
            if member.get_interaction_difference().seconds > seconds:
                self.remove_user(member)

    @property
    def code(self):
        return self._code

    @property
    def passcode(self):
        return self._passcode

celeb_manager = CelebManager()

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
    # This is thousand, million, billion, or trillion, represented in zeros
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

    if (
        (party_code := session.get("party_code", False))
          and (party := party_sessions.get(party_code, False))
          and (user_key := session.get("user_key", False))
          and (isinstance(party, Party)) # Should usually be true, however is helpful for type checking
        ):
        party.add_points(user_key, points)
        
        party.prune_inactive_members() # Prune any inactive members of the party
    

    return response, 200

@app.route('/game/restart', methods=["GET"])
def restart():
    """
    Reset the game. This resets the game score and
    celebs to zero.
    """
    session["score"] = 0
    session.pop("user_key", None)
    session.pop("celeb", None)
    session.pop("party_code", None)
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
def create_party():
    """
    Start a party session that other players can join.
    """
    data = request.get_json()

    # Get the user-provided passcode, random party code,
    # and user key.
    user_key = session.get("user_key", str(uuid.uuid4()))
    passcode = data.get("passcode", "")
    username = data.get("username", user_key[:5])

    user = User(user_key, username)
    party = Party(passcode, user)

    # Remove the user from their old party if they 
    # were in one before creating this one
    if (old_code := session.get("party_code", False)) and (old_party := party_sessions.get(old_code)):
        old_party.remove_user(user)

    # Record the user's key and party code in their
    # session
    session["user_key"] = user_key
    session["party_code"] = party.code
    session["score"] = 0

    return {"room_code": party.code, "message": "Room successfully created!"}, 200

@app.route('/game/party/join', methods=["GET"])
def join_party():
    """
    Join a party session.
    """
    user_key = session.get("user_key", str(uuid.uuid4()))

    # Get query arguments
    party_code = request.args.get("code", None)
    passcode = request.args.get("passcode", "")
    username = request.args.get("username", user_key[:5])

    # Reject the user if the code is not provided
    if not party_code:
        return {"message": "No party code provided"}, 400
    
    # Get the party from the dict of active parties
    party = party_sessions.get(party_code, False)

    # Reject the user if the party provided does not exist
    if not party:
        return {"message": "Party not found"}, 404
    
    # Reject the user from joining the party if the code 
    # provided is incorrect
    if (passcode != party.passcode):
        return {"message": "Incorrect passcode"}, 401

    # Remove the user from a party if the user is found
    # to be in another party 
    if ((old_party_code := session.get("party_code", None)) and
        (old_party := party_sessions.get(old_party_code, None))):
        old_party.remove_user(user_key)

    # Create the user object and add it to the party
    user = User(user_id = user_key, username=username)
    party.add_user(user)

    # Save the user's key and party information to the session
    session["user_key"] = user.key
    session["party_code"] = party.code

    return {"message": "Successfully joined party"}, 200

@app.route('/game/party/leave', methods=["GET"])
def leave_party():
    """
    Leave the currently active party.
    """
    party_code = session.get("party_code", None)
    user_key = session.get("user_key", None)

    if party_code:
        try:
            party_sessions[party_code].remove_user(user_key)
        except KeyError:
            pass
    
    session.pop("party_code", None)

    return {"message": "Successfully removed from party"}, 200

@app.route('/game/party/info', methods=["GET"])
def get_party_info():
    """
    Get the users and scores in a user's party
    """
    party_code = session.get("party_code", None)
    user_key = session.get("user_key", None)

    if not (party_code and user_key):
        return {"message": "No available party code or user key "}, 404
    
    party = party_sessions.get(party_code, False)

    if not party:
        return {"message": "No available party code or user key "}, 404
    
    user = party.get_user_by_key(user_key)
    
    return {"stats": party.get_party_stats(), "code": party_code, "current_user": user.score}, 200

if __name__ == '__main__':
    print("App starting!")

    gettrace = getattr(sys, 'gettrace', None)

    if gettrace is None:
        print('No sys.gettrace')
        waitress.serve(app, listen="*:80")
    elif gettrace():
        app.run()
    else:
        waitress.serve(app, listen="*:80")
