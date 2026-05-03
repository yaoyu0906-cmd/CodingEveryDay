function goBeta() {
    window.location.href = "/beta";
}

function goEvents() {
    window.location.href = "/beta/events";
}

function goProfile() {
    window.location.href = "/profile";
}

function goMain() {
    window.location.href = "/main";
}

function logout() {
    localStorage.removeItem("username");
    window.location.href = "/";
}

function getUsername() {
    return localStorage.getItem("username") || "Guest";
}
