"""Folder Sync - synchronize folders between PC and flash drive."""

from drive_monitor import DriveMonitor
from tray import TrayIcon
from ui import FolderSyncApp


def main() -> None:
    app = FolderSyncApp()
    monitor = DriveMonitor(poll_interval=2.0)
    monitor.on_drive_connected(app.handle_drive_connected)
    monitor.on_drive_disconnected(app.handle_drive_disconnected)
    monitor.start()
    app.attach_monitor(monitor)

    tray = TrayIcon(on_show=app.show_window, on_quit=app.quit_app)
    tray.start()
    app.attach_tray(tray)

    app.mainloop()


if __name__ == "__main__":
    main()
