"""Main application window and dialogs."""

import subprocess
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import autostart
from app_paths import resource_path
from config_manager import read_config, scan_and_update_config_timestamp, write_config, generate_key
from drive_monitor import find_config_folders_on_removable_drives
from folder_watcher import FolderWatcher
from pairs_store import add_pair, load_pairs, remove_pair
from sync_engine import sync_folder

class ConflictDialog(tk.Toplevel):
    def __init__(
        self,
        master,
        *,
        source_folder: str,
        source_device: str,
        dest_folder: str,
        dest_device: str,
        source_timestamp: datetime,
    ):
        super().__init__(master)
        self.result: bool | None = None
        self.source_folder = source_folder
        self.source_device = source_device
        self.dest_folder = dest_folder
        self.dest_device = dest_device
        self.source_timestamp = source_timestamp

        self.title("Synchronization Required")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_decline)

        self._build_ui()
        self.update_idletasks()
        self._center_over(master)

    def _center_over(self, master) -> None:
        master.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_y() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="A connected device contains a matching sync configuration.",
            wraplength=520,
        ).pack(anchor=tk.W, pady=(0, 10))

        message = (
            f"The folder on {self.dest_device} contains older files:\n"
            f"  {self.dest_folder}\n\n"
            f"Accept will overwrite it with files from {self.source_device}:\n"
            f"  {self.source_folder}\n\n"
            f"Newer timestamp: {self.source_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        ttk.Label(frame, text=message, wraplength=520, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 16))

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X)

        ttk.Button(buttons, text="Decline", command=self._on_decline).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(buttons, text="Accept", command=self._on_accept).pack(side=tk.RIGHT)

    def _on_decline(self) -> None:
        self.result = False
        self.grab_release()
        self.destroy()

    def _on_accept(self) -> None:
        self.result = True
        self.grab_release()
        self.destroy()


class FolderSyncApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SYNC")
        self.minsize(640, 420)
        self.geometry("760x480")

        self.watcher = FolderWatcher()
        self._prompted_devices: set[str] = set()
        self._active_dialogs: set[str] = set()
        self._tray = None
        self._monitor = None
        self._is_quitting = False

        self._set_window_icon()
        self._build_ui()
        self._refresh_pairs_list()
        self._start_watching_registered_folders()
        self._update_autostart_button()

        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

    def _set_window_icon(self) -> None:
        icon_path = resource_path("app.ico")
        if icon_path.is_file():
            try:
                self.iconbitmap(str(icon_path))
            except tk.TclError:
                pass

    def attach_tray(self, tray) -> None:
        self._tray = tray

    def attach_monitor(self, monitor) -> None:
        self._monitor = monitor
    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Label(
            outer,
            text="Synchronize folders between your PC and a flash drive using matching configuration files.",
            wraplength=700,
        )
        header.pack(anchor=tk.W, pady=(0, 12))

        actions = ttk.Frame(outer)
        actions.pack(fill=tk.X, pady=(0, 12))

        ttk.Button(
            actions,
            text="Create Configuration File",
            command=self._create_configuration,
        ).pack(side=tk.LEFT)

        ttk.Button(
            actions,
            text="Refresh",
            command=self._refresh_pairs_list,
        ).pack(side=tk.LEFT, padx=(8, 0))

        self.autostart_button = ttk.Button(
            actions,
            text="Enable Autostart",
            command=self._toggle_autostart,
        )
        self.autostart_button.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(outer, text="Registered sync folders on this PC:").pack(anchor=tk.W)
        list_frame = ttk.Frame(outer)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 12))

        self.pairs_tree = ttk.Treeview(
            list_frame,
            columns=("key", "path"),
            show="headings",
            height=8,
        )
        self.pairs_tree.heading("key", text="Key")
        self.pairs_tree.heading("path", text="PC Folder")
        self.pairs_tree.column("key", width=160, anchor=tk.W)
        self.pairs_tree.column("path", width=520, anchor=tk.W)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.pairs_tree.yview)
        self.pairs_tree.configure(yscrollcommand=scrollbar.set)
        self.pairs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        footer = ttk.Frame(outer)
        footer.pack(fill=tk.X)

        ttk.Button(
            footer,
            text="Open Selected Folder in Explorer",
            command=self._open_selected_folder,
        ).pack(side=tk.LEFT)

        ttk.Button(
            footer,
            text="Remove Selected Pair",
            command=self._remove_selected_pair,
        ).pack(side=tk.LEFT, padx=(8, 0))

        self.status_var = tk.StringVar(value="Running in the background. Waiting for removable drive connection...")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor=tk.W, pady=(12, 0))

    def _update_autostart_button(self) -> None:
        if autostart.is_enabled():
            self.autostart_button.configure(text="Disable Autostart")
        else:
            self.autostart_button.configure(text="Enable Autostart")

    def _toggle_autostart(self) -> None:
        enabled = autostart.toggle()
        self._update_autostart_button()
        if enabled:
            self.status_var.set("SYNC will start automatically with Windows.")
            messagebox.showinfo("Autostart Enabled", "SYNC will launch automatically when you sign in to Windows.")
        else:
            self.status_var.set("Automatic startup disabled.")
            messagebox.showinfo("Autostart Disabled", "SYNC will no longer start automatically with Windows.")

    def show_window(self) -> None:
        self.after(0, self._show_window)

    def _show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def minimize_to_tray(self) -> None:
        self.withdraw()
        if self._tray is not None:
            self._tray.notify("SYNC", "SYNC is still running in the system tray.")

    def _on_window_close(self) -> None:
        self.minimize_to_tray()

    def quit_app(self) -> None:
        self.after(0, self._quit_app)

    def _quit_app(self) -> None:
        if self._is_quitting:
            return
        self._is_quitting = True

        if self._monitor is not None:
            self._monitor.stop()
        self.watcher.stop()
        if self._tray is not None:
            self._tray.stop()
        self.destroy()
    def _refresh_pairs_list(self) -> None:
        for item in self.pairs_tree.get_children():
            self.pairs_tree.delete(item)

        for pair in load_pairs():
            self.pairs_tree.insert("", tk.END, values=(pair["key"], pair["pc_path"]))

        self._start_watching_registered_folders()

    def _start_watching_registered_folders(self) -> None:
        folders = [pair["pc_path"] for pair in load_pairs()]
        self.watcher.refresh(folders)

    def _create_configuration(self) -> None:
        pc_folder = filedialog.askdirectory(
            title="Step 1: Select the PC synchronization folder",
            mustexist=True,
        )
        if not pc_folder:
            return

        pc_path = Path(pc_folder)
        existing = read_config(pc_path)
        if existing:
            if not messagebox.askyesno(
                "Configuration Exists",
                "This folder already contains a sync configuration.\n"
                "Do you want to replace it and create a new pair?",
            ):
                return

        key = generate_key()
        write_config(pc_path, key)
        add_pair(key, str(pc_path))

        messagebox.showinfo(
            "PC Configuration Created",
            f"Configuration file created in:\n{pc_path}\n\n"
            f"Key: {key}\n\n"
            "Next, select the folder on the flash drive.",
        )

        flash_folder = filedialog.askdirectory(
            title="Step 2: Select the flash drive synchronization folder",
            mustexist=False,
        )
        if not flash_folder:
            messagebox.showwarning(
                "Flash Folder Skipped",
                "PC configuration was saved, but no flash drive folder was selected.\n"
                "Run Create Configuration again to finish the pair when the drive is connected.",
            )
            self._refresh_pairs_list()
            return

        flash_path = Path(flash_folder)
        flash_path.mkdir(parents=True, exist_ok=True)
        write_config(flash_path, key)

        messagebox.showinfo(
            "Configuration Complete",
            f"Matching configuration files were created.\n\n"
            f"PC folder:\n{pc_path}\n\n"
            f"Flash folder:\n{flash_path}\n\n"
            f"Shared key:\n{key}",
        )

        self._refresh_pairs_list()
        self.status_var.set(f"Sync pair registered. Key: {key}")

    def _open_selected_folder(self) -> None:
        selected = self.pairs_tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Select a registered folder first.")
            return

        values = self.pairs_tree.item(selected[0], "values")
        folder = values[1]
        subprocess.Popen(["explorer", folder])

    def _remove_selected_pair(self) -> None:
        selected = self.pairs_tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Select a registered folder first.")
            return

        values = self.pairs_tree.item(selected[0], "values")
        key, path = values[0], values[1]
        if messagebox.askyesno(
            "Remove Pair",
            f"Remove this sync pair from the program?\n\nKey: {key}\nFolder: {path}",
        ):
            remove_pair(key)
            self._refresh_pairs_list()

    def handle_drive_connected(self, drive: str) -> None:
        self.after(0, lambda: self._process_drive_connection(drive))

    def handle_drive_disconnected(self, drive: str) -> None:
        prompt_key = drive.rstrip("\\").upper()
        self._prompted_devices.discard(prompt_key)
        self._active_dialogs.discard(prompt_key)

    def _process_drive_connection(self, drive: str) -> None:
        drive = drive.rstrip("\\")
        prompt_key = drive.upper()

        if prompt_key in self._prompted_devices or prompt_key in self._active_dialogs:
            return

        pairs = {pair["key"]: pair for pair in load_pairs()}
        if not pairs:
            return

        matches = find_config_folders_on_removable_drives()
        for match in matches:
            if not match["drive"].upper().startswith(prompt_key):
                continue

            remote_folder = match["folder"]
            remote_config = read_config(remote_folder)
            if remote_config is None:
                continue

            key = remote_config["key"]
            pair = pairs.get(key)
            if pair is None:
                continue

            pc_folder = pair["pc_path"]
            pc_config = read_config(pc_folder)
            if pc_config is None:
                continue

            remote_timestamp = scan_and_update_config_timestamp(remote_folder)
            pc_timestamp = pc_config["timestamp"]

            if remote_timestamp is None:
                continue

            if remote_timestamp == pc_timestamp:
                self._prompted_devices.add(prompt_key)
                self.status_var.set(f"Drive {drive}: folders already synchronized.")
                continue

            if remote_timestamp > pc_timestamp:
                source_folder = remote_folder
                source_device = f"flash drive ({drive})"
                dest_folder = pc_folder
                dest_device = "this PC"
                source_timestamp = remote_timestamp
            else:
                source_folder = pc_folder
                source_device = "this PC"
                dest_folder = remote_folder
                dest_device = f"flash drive ({drive})"
                source_timestamp = pc_timestamp

            self._prompted_devices.add(prompt_key)
            self._active_dialogs.add(prompt_key)
            self._show_window()
            self._show_conflict_dialog(                prompt_key,
                source_folder,
                source_device,
                dest_folder,
                dest_device,
                source_timestamp,
            )
            return

        self.status_var.set(f"Drive {drive} connected. No matching sync configuration found.")

    def _show_conflict_dialog(
        self,
        prompt_key: str,
        source_folder: str,
        source_device: str,
        dest_folder: str,
        dest_device: str,
        source_timestamp: datetime,
    ) -> None:
        dialog = ConflictDialog(
            self,
            source_folder=source_folder,
            source_device=source_device,
            dest_folder=dest_folder,
            dest_device=dest_device,
            source_timestamp=source_timestamp,
        )
        self.wait_window(dialog)
        self._active_dialogs.discard(prompt_key)

        if dialog.result:
            try:
                sync_folder(source_folder, dest_folder, source_timestamp)
                self.status_var.set(
                    f"Synchronized {dest_device}: {dest_folder}"
                )
                messagebox.showinfo(
                    "Synchronization Complete",
                    f"Files were copied to:\n{dest_folder}",
                )
            except Exception as exc:
                messagebox.showerror("Synchronization Failed", str(exc))
                self.status_var.set("Synchronization failed.")
        else:
            self.status_var.set("Synchronization declined by user.")


def run_app() -> None:
    app = FolderSyncApp()
    app.mainloop()