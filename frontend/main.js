const { app, BrowserWindow } = require('electron')

const createWindow = () => {
    const win = new BrowserWindow({
        width: 800,
        height: 600
    })

    win.loadFile('renderer/pages/home.html')
}

app.whenReady().then(() => {
    createWindow()
})

function toggleMenu() {
    document.querySelector(".sideMenu").classList.toggle("active");
    }