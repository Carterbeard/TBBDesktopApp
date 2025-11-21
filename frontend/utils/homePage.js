function toggleMenu() {
    document.querySelector(".sideMenu").classList.toggle("active");
    }

function processData() {
    localStorage.removeItem("progress");
    localStorage.removeItem("progressComplete");
    window.location.href = "analysis.html?runProgress=true";
}