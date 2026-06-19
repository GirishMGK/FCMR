/**
 * Auto-updater for SanGir Automations desktop app.
 *
 * Update flow:
 *   1. Check for updates on startup and every 4 hours.
 *   2. If found, download silently in the background.
 *   3. When downloaded, show a dialog: "Restart now" or "Later".
 *   4. On "Later", install automatically on the next quit.
 *
 * All events are logged to update.log so users can verify it's working.
 */

const { autoUpdater } = require("electron-updater");
const { app, dialog, Notification } = require("electron");
const path = require("path");
const fs = require("fs");

const LOG_DIR = path.join(app.getPath("userData"), "logs");
const UPDATE_LOG = path.join(LOG_DIR, "update.log");

function ensureLogDir() {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
  } catch (_) {}
}

function writeLog(line) {
  ensureLogDir();
  try {
    fs.appendFileSync(UPDATE_LOG, `[${new Date().toISOString()}] ${line}\n`);
  } catch (_) {}
}

function showNotification(title, body) {
  if (Notification.isSupported()) {
    new Notification({ title, body, silent: true }).show();
  }
}

function initUpdater(mainWindow) {
  writeLog(`=== Auto-updater starting (current: v${app.getVersion()}) ===`);

  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.autoDownload = true;

  autoUpdater.on("checking-for-update", () => {
    writeLog("Checking for updates...");
  });

  autoUpdater.on("update-available", (info) => {
    writeLog(`Update available: v${info.version} (released ${info.releaseDate})`);
    showNotification(
      "Update available — SanGir Automations",
      `v${info.version} is downloading in the background.`
    );
  });

  autoUpdater.on("update-not-available", (info) => {
    writeLog(`Up to date (v${info.version})`);
  });

  autoUpdater.on("error", (err) => {
    writeLog(`Update error: ${err.message}`);
    writeLog(`  Stack: ${err.stack || "(no stack)"}`);
  });

  autoUpdater.on("download-progress", (progress) => {
    const pct = Math.round(progress.percent);
    const mbps = (progress.bytesPerSecond / 1024 / 1024).toFixed(1);
    writeLog(`Downloading: ${pct}% at ${mbps} MB/s`);
  });

  autoUpdater.on("update-downloaded", (info) => {
    writeLog(`v${info.version} downloaded — showing restart dialog`);
    showNotification(
      "Update ready — SanGir Automations",
      `v${info.version} is ready. Restart to apply.`
    );

    // Show restart dialog attached to the main window
    const win = mainWindow && !mainWindow.isDestroyed() ? mainWindow : null;
    const opts = {
      type: "info",
      title: "Update Ready",
      message: `SanGir Automations v${info.version} is ready to install.`,
      detail:
        "Click 'Restart Now' to apply the update immediately, or 'Later' to install it the next time you close the app.",
      buttons: ["Restart Now", "Later"],
      defaultId: 0,
      cancelId: 1,
    };

    const promise = win
      ? dialog.showMessageBox(win, opts)
      : dialog.showMessageBox(opts);

    promise.then(({ response }) => {
      if (response === 0) {
        writeLog("User chose Restart Now — installing...");
        autoUpdater.quitAndInstall(false, true);
      } else {
        writeLog("User chose Later — will install on next quit");
      }
    });
  });

  // Check on startup
  autoUpdater.checkForUpdates().catch((err) => {
    writeLog(`Startup update check failed: ${err.message}`);
  });

  // Re-check every 4 hours
  setInterval(
    () => {
      autoUpdater.checkForUpdates().catch((err) => {
        writeLog(`Periodic update check failed: ${err.message}`);
      });
    },
    4 * 60 * 60 * 1000
  );
}

module.exports = { initUpdater };
