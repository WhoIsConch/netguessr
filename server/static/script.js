const BASE_URL = "http://127.0.0.1:5000";

async function getRandom() {
    let response = await fetch("/celeb/random?format=json");

    if (response.ok) {
        let json = await response.json();
        currentRandom = json;

        return json;
    } else {
        alert("HTTP-Error: " + response.status);
        return null;
    }
}

async function submit() {
    let response = await fetch("/game/submit", {
        method: "POST",
        body: JSON.stringify({
            guess: $("#guess").val(),
            guess_amt: $("#amount").val()
        }),
        headers: {
            "Content-Type": "application/json"
        }
    });

    let json = await response.json();

    return json;
}

async function reset() {
    $("#submit").prop("disabled", false);
    $("#guess").prop("disabled", false);
    $("#skip").prop("disabled", false);
    $(".result").hide();
    $("#guess").val("");

    let celeb = await getRandom();

    $("#celeb-name").text(celeb.name);
    $("#celeb-img").attr("src", celeb.image);
    $("#result-text").text("");

}

async function getPartyInfo() {
    let resp = await fetch("/game/party/info");

    if (resp.status !== 200) {
        return false;
    }

    let json = await resp.json();

    $("#partyList").html("");
    for (let user in json.stats) {
        $("#partyList").append(`<li>${user} | ${json.stats[user]}</li>`);
    }

    $("#score").text(`Score: ${json.current_user}`)

    $("#partyCode").text("Party Code: " + json.code)
    return true;
}

async function siteLoad() {
    $("#guess").val("");
    $("input").val("M");

    let isInParty = await getPartyInfo();

    if (isInParty) {
        $("#joinParty").hide();
        $("#leaveParty").show();
    }
}

$(function(){
    siteLoad();

    $("#celeb-img").on("error", () => {
        fetch("/manage/imageError", {
            method: "POST",
            body: JSON.stringify({
                image_url: $("#celeb-img").attr("src"),
                celeb: $("#celeb-name").text()
            }),
            headers: {
                "Content-Type": "application/json"
            }
        });
    });

    $("#guess").keyup(function(event){
        if(event.keyCode == 13 && $("#submit").prop("disabled") == false){
            $("#submit").click();
        }
    });

    $("#next").click(async function(){
        // Refresh the page
        getPartyInfo();
        await reset();
    });

    $("#skip").click(async function(){
        await reset();
    });

    $("#restart").click(async function(){
        fetch("/game/restart")
            .then(() => {
                location.reload();
            });
    });

    $("#submit").click(async function(){
        let result = await submit();

        switch (result.statcode) {
            case "onthemoney":
                $(".result").css("background-color", "#0d7306");
                break;
            case "closeenough":
                $(".result").css("background-color", "#31478f");
                break;
            case "middle":
                $(".result").css("background-color", "#b09a2e");
                break;
            case "off":
                $(".result").css("background-color", "#b09a2e");
                break;
            case "wayoff":
                $(".result").css("background-color", "#942319");
                break;
            default:
                $(".result").css("background-color", "white");
                break;
        }

        $("#result-text").text(result.message);
        
        $("#result-net-worth").text(
            "The net worth of " + result.celeb_data.name + " is " +
            result.celeb_data.networth
            );

        $("#score").text("Score: " + result.score);

        $("#submit").prop("disabled", true);
        $("#guess").prop("disabled", true);
        $("#skip").prop("disabled", true);
        $(".result").show();

        $('html, body') .animate ({
            scrollTop: $ (".result") .offset().top + $(".result")[0].scrollHeight
            }, 700);
    });

    $("#joinParty").click(async function(){
        let code = prompt("Input a room code:");

        if (code === null) {
            return;
        }
        else if (code === "") {
            alert("Room code is required!");
            return;
        }

        let username = prompt("Input a username:");

        if (username === null || username === "") {
            alert("Username is required!");
            return;
        }

        res = await fetch(`/game/party/join?code=${code}&username=${username}`);
        resp = await res.json();

        if (res.status === 401) {
            let passcode = prompt("Input the room's passcode:");

            res = await fetch(`/game/party/join?code=${code}&username=${username}&passcode=${passcode}`);
            resp = await res.json();
        }

        if (res.status === 404) {
            alert("Room does not exist.");
        }
        else if (res.status !== 200) {
            alert(`Something went wrong when joining the party. Error: ${res.status}`);
            return;
        } else {
            $("#joinParty").hide();
            $("#leaveParty").show();
            getPartyInfo();
        }

    });

    $("#leaveParty").click(async function(){
        resp = await fetch("/game/party/leave");

        if (resp.status === 200) {
            $("#partyList").html("");
            $("#leaveParty").hide();
            $("#joinParty").show();
            $("#partyCode").text("");
        } 
    });

    $("#createParty").click(async function(){
        let passcode = prompt("Enter passcode, if any.");
        let payload = {};

        if (passcode !== "" && passcode !== null) {
            payload = {"passcode": passcode};
        } else if (passcode === null) {
            return;
        } 

        let username = prompt("Enter a username:");
        if (username === null || username === "") {
            alert("You must have a username!");
            return;
        } else {
            payload.username = username;
        }

        let resp = await fetch("/game/party/create", {
            method: "POST",
            body: JSON.stringify(payload),
            headers: {
                "Content-Type": "application/json"
            }
        });
        let data = await resp.json();

        if (data.room_code) {
            $("#joinParty").hide();
            $("#leaveParty").show();
            alert("Party created! Room code: " + data.room_code);
        }

        await reset();
        await getPartyInfo();

        console.log(data);
    });

});