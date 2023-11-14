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

$(function(){
    $(".result").hide();
    $("#leaveParty").hide();
    $("#guess").val("");
    $("input").val("M");

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

        res = await fetch(`/game/party/join?code=${code}`);
        resp = await res.json();

        if (res.status === 401) {
            let passcode = prompt("Input the room's passcode:");

            res = await fetch(`/game/party/join?code=${code}&passcode=${passcode}`);
            resp = await res.json();
        }

        if (res.status !== 200) {
            alert(`Something went wrong when joining the party. Error: ${res.status}`);
            return;
        } else {
            $("#joinParty").hide();
            $("#leaveParty").show();
        }

    });

    $("#leaveParty").click(async function(){
        fetch("/game/party/leave");

        $("#leaveParty").hide();
        $("#joinParty").show();
    });

    $("#createParty").click(async function(){
        let passcode = prompt("Enter passcode, if any.");
        let payload = {};

        if (passcode !== "" && passcode !== null) {
            payload = {"passcode": passcode};
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
        }

        console.log(data);
    });

});