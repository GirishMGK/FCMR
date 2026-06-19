/**
 * Preload script for Electron (sandboxed context).
 * Exposes minimal API to the renderer process.
 */

// In the preload context, only ipcRenderer (not app) is available from electron.
// Version info is passed from the main process via IPC or read from package.json.
const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("sangir", {
  platform: process.platform,
});
