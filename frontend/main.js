const { app, BrowserWindow } = require('electron')

let win;

const createWindow = () => {
    const win = new BrowserWindow({
        width: 800,
        height: 600
    })

    win.loadFile('renderer/pages/home.html')

    setInterval(()=>{
        win.reload();
    },3000);
}


app.whenReady().then(() => {
    createWindow()
})
