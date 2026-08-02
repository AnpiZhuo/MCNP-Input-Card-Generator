const electron = require('electron');
console.log('electron type:', typeof electron);
console.log('keys:', Object.keys(electron).slice(0,15).join(','));
console.log('has app:', typeof electron.app);
console.log('has BrowserWindow:', typeof electron.BrowserWindow);
