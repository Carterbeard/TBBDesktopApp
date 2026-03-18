function toggleMenu() {
    document.querySelector(".sideMenu").classList.toggle("active");
    }

const delay = ms => new Promise(res => setTimeout(res, ms));

window.onload = async () => {
    document.getElementById('errorMsgAnalysis').innerText = "";
    const params = new URLSearchParams(window.location.search);
    const progressComplete = localStorage.getItem("progressComplete") === "true";
    const curJobId = params.get('jobId')

    const progressContainer = document.getElementsByClassName("progressContainer")[0];
    const progressBar = document.getElementsByClassName("progressBar")[0];

    if (params.get("runProgress") === "true" && !progressComplete) {
        let {status, percent, error} =  await getStatusApi(curJobId);
        while((status === "processing" || status === "queued") && error === null){
            setProgressInterval(progressBar, progressContainer,percent);
            await delay(300);
            const result = await getStatusApi(curJobId);
            status = result.status;
            percent = result.percent;
            error = result.error;
        }
        if(status==="failed"){
            const response = await getStatus(curJobId);
            const data = await response.json();
            document.getElementById('errorMsgAnalysis').innerText = "Error with backend: " + data.error_message;
            return;
        }
        if(error!=null){
            document.getElementById('errorMsgAnalysis').innerText = "Error occurred" + error;
            return;
        }
        if(status==="completed"){
            setProgressInterval(progressBar, progressContainer, 100);
        }
    }
    if (progressComplete) {
        progressContainer.style.display = "none";
        return;
    }
};
function setProgressInterval(progressBar, progressContainer,currProgress) {
    progressBar.style.width = currProgress + "%";
    localStorage.setItem("progress", currProgress);
    if (currProgress == 100) {
        const figures = document.querySelector(".imageProduced");
        progressContainer.style.display = "none";
        figures.style.visibility = "visible";
        localStorage.setItem("progressComplete", "true");
    }
}
async function getStatusApi(curJobId){
    const response = await getStatus(curJobId);
    const data = await response.json();
    if(response.ok){
        //processing or completed or failed
        return {status: data.status, percent: data.progress_percent, error: null}
    }
    return {status:null,percent:null,error: data.detail}
}