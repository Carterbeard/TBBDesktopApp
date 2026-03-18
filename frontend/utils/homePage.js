const inputFile = document.getElementById("inputFile");
const dropZone = document.querySelector(".dragAndDrop");

function toggleMenu() {
    document.querySelector(".sideMenu").classList.toggle("active");
    }

//run when process Data button is clicked
async function processData() {
    document.getElementById('errorMsgHome').innerText = "";
    const {jobId,uploadError}  =  await uploadFileApi();
    if(uploadError!=null){
        document.getElementById('errorMsgHome').innerText = "Error with uploading: " + uploadError;
        return;
    }
    const processError = await processFileApi(jobId)
    if(processError!=null){
        document.getElementById('errorMsgHome').innerText = "Error with processing: " + processError;
        return;
    }
    localStorage.removeItem("progress");
    localStorage.removeItem("progressComplete");
    window.location.href = `analysis.html?runProgress=true&jobId=${jobId}`;
}
async function uploadFileApi() {
    const response = await uploadFile(
        document.getElementById('inputFile').files[0],
        document.getElementById('datasetName').value,
        document.getElementById('catchmentThreshold').value
    )
    const data = await response.json();
    if(response.ok){
        return { jobId: data.job_id, uploadError: null };
    } 
    if (response.status === 422) {
        const field = data.detail?.[0]?.loc?.slice(-1)[0];
        const msg = field === 'file' ? "Please upload file" :   field === 'catchment_threshold_area' ? "Enter a valid number" : 
        "Please enter parameters";
        return { jobId: null, uploadError: msg };
    }
    return { jobId: null, uploadError: data.detail || "Server error" };
}
async function processFileApi(jobId){
    const response = await processFile(jobId)
    const data = await response.json();
    if(response.ok){
        return null;
    }
    return data.detail
}




function toggleParameters() {
    document.querySelector(".parameterInput").classList.toggle("active", inputFile.files.length>0);
}

function toggleProcessButton(){
    document.querySelector(".processButton").classList.toggle("active", inputFile.files.length>0);
}

function toggleWhenActiveFile(){
    const fileName = inputFile.files[0].name;
    document.getElementById("uploadImg").classList.toggle("active");
    document.getElementById("dragP").innerHTML= "File added: " + fileName;
    document.getElementById("inputBtnSection").hidden = true;
    document.getElementById("removeFileBtn").hidden = false;
}

function removeFile(){
    document.getElementById('errorMsgHome').innerText = "";
    inputFile.value="";
    document.getElementById("uploadImg").classList.toggle("active");
    document.getElementById("dragP").innerHTML= "Drag and Drop to Upload File";
    document.getElementById("inputBtnSection").hidden = false;
    document.getElementById("removeFileBtn").hidden = true;
    toggleParameters();
    toggleProcessButton();
}

inputFile.addEventListener("change",()=>{
    toggleProcessButton();
    toggleParameters();
    toggleWhenActiveFile();
});
dropZone.addEventListener("dragover", e => e.preventDefault());
dropZone.addEventListener("drop", e => {
    e.preventDefault();
    inputFile.files = e.dataTransfer.files;
    toggleProcessButton();
    toggleParameters();
    toggleWhenActiveFile();
});

