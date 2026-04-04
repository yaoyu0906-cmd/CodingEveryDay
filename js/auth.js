function signup() {
    const inputs = document.querySelectorAll(".input");

    fetch("http://localhost:5000/signup", {
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

    fetch("http://localhost:5000/login", {
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
