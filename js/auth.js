function signup() {
    const inputs = document.querySelectorAll(".input");
    const username = inputs[0].value.trim();
    const password = inputs[1].value;
    const confirm = inputs[2].value;

    if (!username) {
        alert("Please enter a username.");
        return;
    }

    if (!password) {
        alert("Please enter a password.");
        return;
    }

    if (password !== confirm) {
        alert("Passwords do not match!");
        return;
    }

    fetch("https://codingeveryday-api.onrender.com/signup", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ username, password })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        if (data.status === "ok") {
            localStorage.setItem("username", username);
            window.location.href = "/main";
        }
    });
}

function login() {
    const inputs = document.querySelectorAll(".input");
    const username = inputs[0].value.trim();
    const password = inputs[1].value;

    if (!username) {
        alert("Please enter a username.");
        return;
    }

    fetch("https://codingeveryday-api.onrender.com/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ username, password })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        if (data.status === "ok") {
            localStorage.setItem("username", username);
            window.location.href = "/main";
        }
    });
}
