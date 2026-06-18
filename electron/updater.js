/**
 * Auto-updater for SanGir Automations desktop app.
 *
 * Silent update strategy (Claude-style):
 *   1. Check for updates on startup and every 4 hours.
 *   2. Download silently in the background — no dialogs, no prompts.
 *   3. Install automatically the next time the user quits the app.
 *
 * The user never sees a dialog. They just open the app after closing it
 * and it is already on the new version.
 */

const { autoUpdater } = require("electron-updater");

const log = {
  info: (...args) => console.log("[updater]", ...args),
  error: (...args) => console.error("[updater]", ...args),
};

function initUpdater() {
  // Install silently on next quit — no explicit quitAndInstall call needed.
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.autoDownload = true;

  autoUpdater.on("checking-for-update", () => {
    log.info("Checking for updates...");
  });

  autoUpdater.on("update-available", (info) => {
    log.info(`Update available: ${info.version} — downloading silently`);
  });

  autoUpdater.on("update-not-available", () => {
    log.info("App is up to date");
  });

  autoUpdater.on("error", (err) => {
    // Non-fatal — log and continue. Offline users should not see a crash.
    log.error(`Update check failed: ${err.message}`);
  });

  autoUpdater.on("download-progress", (progress) => {
    log.info(`Downloading: ${Math.round(progress.percent)}%`);
  });

  autoUpdater.on("update-downloaded", (info) => {
    log.info(`v${info.version} downloaded — will install on next quit`);
  });

  // Check on startup, then every 4 hours.
  autoUpdater.checkForUpdates().catch((err) => {
    log.error(`Initial update check failed: ${err.message}`);
  });

  setInterval(() => {
    autoUpdater.checkForUpdates().catch((err) => {
      log.error(`Periodic update check failed: ${err.message}`);
    });
  }, 4 * 60 * 60 * 1000);
}

module.exports = { initUpdater };
