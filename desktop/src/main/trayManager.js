'use strict';

const { Tray, Menu, nativeImage, app } = require('electron');
const path = require('path');
const log = require('electron-log');

/**
 * Manages the system tray icon and context menu.
 *
 * Status colours:
 *   online  – green indicator
 *   stale   – amber indicator (data cached but TTL exceeded)
 *   offline – red indicator
 */
class TrayManager {
  constructor(config, win, onForceSync) {
    this.config = config;
    this.win = win;
    this.onForceSync = onForceSync;
    this.tray = null;
    this._status = 'online';
  }

  create() {
    const iconPath = this._iconPath();
    try {
      const icon = nativeImage.createFromPath(iconPath);
      this.tray = new Tray(icon.isEmpty() ? nativeImage.createEmpty() : icon);
    } catch (err) {
      log.warn('TrayManager: could not load icon:', err.message);
      this.tray = new Tray(nativeImage.createEmpty());
    }

    this.tray.setToolTip('Dublin City Dashboard');
    this._updateMenu();
  }

  /**
   * Update the tray indicator and tooltip.
   * @param {'online'|'stale'|'offline'} status
   */
  setStatus(status) {
    this._status = status;
    const labels = { online: 'Online', stale: 'Stale data', offline: 'Offline' };
    if (this.tray) {
      this.tray.setToolTip(`Dublin City Dashboard — ${labels[status] || status}`);
      this._updateMenu();
    }
  }

  destroy() {
    if (this.tray) {
      this.tray.destroy();
      this.tray = null;
    }
  }

  // --------------------------------------------------------------------------
  // Internal
  // --------------------------------------------------------------------------

  _iconPath() {
    // Prefer a status-specific icon; fall back to the generic tray icon
    return path.join(__dirname, '..', '..', 'assets', 'tray-icon.png');
  }

  _updateMenu() {
    const statusLabel = {
      online:  '● Online',
      stale:   '◐ Stale data',
      offline: '○ Offline',
    }[this._status] || this._status;

    const menu = Menu.buildFromTemplate([
      { label: 'Dublin City Dashboard', enabled: false },
      { label: statusLabel, enabled: false },
      { type: 'separator' },
      {
        label: 'Show Dashboard',
        click: () => {
          if (this.win) {
            this.win.show();
            this.win.focus();
          }
        },
      },
      {
        label: 'Force Sync',
        click: () => {
          log.info('Manual force sync triggered from tray');
          if (this.onForceSync) this.onForceSync();
        },
      },
      { type: 'separator' },
      {
        label: 'Quit',
        click: () => app.quit(),
      },
    ]);

    if (this.tray) {
      this.tray.setContextMenu(menu);
    }
  }
}

module.exports = TrayManager;
