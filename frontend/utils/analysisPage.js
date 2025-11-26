function toggleMenu() {
    document.querySelector(".sideMenu").classList.toggle("active");
    }

window.onload = () => {
    const params = new URLSearchParams(window.location.search);
    const progressComplete = localStorage.getItem("progressComplete") === "true";

    const progressContainer = document.getElementsByClassName("progressContainer")[0];
    const progressBar = document.getElementsByClassName("progressBar")[0];
    
    if (params.get("runProgress") === "true" && !progressComplete) {
        setProgressInterval(progressBar, progressContainer);
    }
    if (progressComplete) {
        progressContainer.style.display = "none";
        return;
    }
};
function setProgressInterval(progressBar, progressContainer) {
    let currentProgress = parseInt(localStorage.getItem("progress")) || 0;


    //this will be changed but currently just adds to currentProgress each loop, however after backend is implemented with each function adding a new amount of progress this bar function below will change to reflect currentProgress changin differently
    const interval = setInterval(() => {
        progressBar.style.width = currentProgress + "%";

        currentProgress++;
        localStorage.setItem("progress", currentProgress);
        if (currentProgress > 100) {
            clearInterval(interval);
            const progressContainer = document.getElementsByClassName("progressContainer")[0];
            const figures = document.querySelector(".imageProduced");
            progressContainer.style.display = "none";
            figures.style.visibility = "visible";
            localStorage.setItem("progressComplete", "true");
        }
        
    },30);
}