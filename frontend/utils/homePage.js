const inputFile = document.getElementById("inputFile");
const dropZone = document.querySelector(".dragAndDrop");

function toggleMenu() {
    document.querySelector(".sideMenu").classList.toggle("active");
    }

function processData() {
    localStorage.removeItem("progress");
    localStorage.removeItem("progressComplete");
    window.location.href = "analysis.html?runProgress=true";
}

function toggleParameters() {
    document.querySelector(".parameterInput").classList.toggle("active", inputFile.files.length>0);
}

function toggleWhenActiveFile(){
    const fileName = inputFile.files[0].name;

    document.getElementById("uploadImg").classList.toggle("active");
    document.getElementById("dragP").innerHTML= "File added: " + fileName;
    document.getElementById("inputBtnSection").hidden = true;
    document.getElementById("removeFileBtn").hidden = false;
}

function removeFile(){
    inputFile.value=""
    document.getElementById("uploadImg").classList.toggle("active");
    document.getElementById("dragP").innerHTML= "Drag and Drop to Upload File";
    document.getElementById("inputBtnSection").hidden = false;
    document.getElementById("removeFileBtn").hidden = true;
}

inputFile.addEventListener("change",()=>{
    toggleParameters()
    toggleWhenActiveFile()
});
dropZone.addEventListener("dragover", e => e.preventDefault());
dropZone.addEventListener("drop", e => {
    e.preventDefault();
    inputFile.files = e.dataTransfer.files;
    toggleParameters();
    toggleWhenActiveFile();
});