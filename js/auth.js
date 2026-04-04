function signup() {
    const inputs = document.querySelectorAll(".input");

    fetch("https://codingeveryday-api.onrender.com/signup", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            username: inputs[0].value,
            password: inputs[1].value
        })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
    });
}

function login() {
    const inputs = document.querySelectorAll(".input");

    fetch("https://codingeveryday-api.onrender.com/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            username: inputs[0].value,
            password: inputs[1].value
        })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);

        if (data.status === "ok") {
            window.location.href = "/main";
        }
    });
}
