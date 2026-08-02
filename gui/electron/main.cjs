const { app, BrowserWindow } = require("electron");
const path = require("path");
const isDev = !app.isPackaged;
function createWindow() {
  const win = new BrowserWindow({ width: 1200, height: 800, minWidth: 900, minHeight: 600,
    frame: false,
    webPreferences: { preload: path.join(__dirname, "preload.cjs") },
  });
  if (isDev) win.loadURL("http://localhost:1420");
  else win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
}
app.whenReady().then(createWindow);
app.on("window-all-closed", () => app.quit());
