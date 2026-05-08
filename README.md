# DevHost — Local Domain Manager

A Windows desktop application for managing Apache virtual hosts and the Windows hosts file on local PHP / web development environments.
Built with **Python 3.12+** and **PySide6**. Supports XAMPP, WAMP, Laragon, and custom Apache installations.

---

## Features

### Domain Management
- **Add, edit, and delete** virtual host entries with a clean form dialog
- **Enable / disable** individual domains without deleting them — toggling comments out the vhost block and hosts entry so Apache ignores them
- **Alphabetically sorted** domain table for quick navigation
- **Duplicate domain and port conflict detection** — warns before saving clashing names or ports
- **Document root browser** — pick folders directly from the dialog
- **Notes field** per domain for personal reminders

### Apache Control
- **Start, Stop, Restart** Apache directly from the toolbar using background threads (UI never freezes)
- **Live status badge** in the header showing whether Apache is running or stopped
- **Automatic status polling** at a configurable interval (default 5 s, or disabled)
- **Manual "Check Status"** button for an immediate on-demand check
- **Apache config validation** (`httpd -t`) runs before any change is committed — bad configs are caught before they break Apache
- Supports XAMPP, WAMP, Laragon, and custom Apache installs

### Configuration File Management
- **Virtual hosts config** (`httpd-vhosts.conf`) — DevHost writes only inside its own `# BEGIN DevHost` / `# END DevHost` marker block, leaving the rest of the file untouched
- **Windows hosts file** (`C:\Windows\System32\drivers\etc\hosts`) — same marker-based approach, never touches unrelated entries
- **httpd.conf Listen directives** — automatically adds or removes `Listen <port>` lines when domains with non-80 ports are added, enabled, or disabled

### Backup & Restore
- **Automatic backup** before every modification (configurable)
- **Manual "Backup Now"** toolbar button
- Backs up all three files: hosts, vhosts config, and httpd.conf
- **Restore dialog** lets you browse and restore any previous backup for each file individually
- Configurable maximum number of backups to retain

### Settings
All settings are saved to `config/settings.json` and configurable through the tabbed Settings dialog:

| Tab | Settings |
|-----|----------|
| **Apache** | Server type, path to `httpd.exe`, optional Windows service name |
| **Paths** | VHosts config, `httpd.conf`, Windows hosts file, default port & document root |
| **Behaviour** | Auto-restart toggle, validate before save, backup before modify, max backups, status poll interval |
| **Timeouts** | Start bat timeout, stop bat timeout, start poll timeout, Windows service timeout |

### Other
- **Open in Browser** — per-row 🔗 button opens the domain in Chrome (or the system default browser)
- **Open Config Dir** — opens the `config/` folder in Windows Explorer
- **UAC elevation** — automatically requests administrator privileges on launch (required to write the hosts file and Apache config)
- No background console window — launched via `pythonw.exe`

---

## Screenshots

> _Add screenshots here once available._

---

## Requirements

- Windows 10 / 11
- Python 3.12 or newer
- One of: XAMPP, WAMP, Laragon, or a custom Apache installation

---

## Installation (Run from Source)

### 1. Clone the repository

```bat
git clone https://github.com/your-username/LoclaDomainManagerTool.git
cd LoclaDomainManagerTool
```

### 2. Create and activate a virtual environment

```bat
python -m venv DevHost\.venv
DevHost\.venv\Scripts\activate
```

### 3. Install dependencies

```bat
pip install -r DevHost\requirements.txt
```

### 4. Configure settings

Copy the example settings file and edit it to match your environment:

```bat
copy DevHost\config\settings.example.json DevHost\config\settings.json
```

Open `settings.json` and update the paths:

```json
{
  "apache_bin":  "C:\\xampp\\apache\\bin\\httpd.exe",
  "vhosts_conf": "C:\\xampp\\apache\\conf\\extra\\httpd-vhosts.conf",
  "httpd_conf":  "C:\\xampp\\apache\\conf\\httpd.conf",
  "hosts_file":  "C:\\Windows\\System32\\drivers\\etc\\hosts",
  "server_type": "xampp"
}
```

You can also configure everything through the **Settings** dialog after the app starts.

### 5. Launch the app

```bat
startapp.bat
```

Or directly:

```bat
DevHost\.venv\Scripts\pythonw.exe DevHost\main.py
```

The app will prompt for UAC elevation automatically — this is required to write to the Windows hosts file and Apache config files.

---

## Build a Standalone EXE (Optional)

Run the included build script from inside the `DevHost\` directory:

```bat
cd DevHost
build.bat
```

This uses PyInstaller to produce `DevHost\dist\DevHost.exe` — a single self-contained executable with the UAC manifest embedded. No Python installation required to run it.

---

## Project Structure

```
LoclaDomainManagerTool/
├── startapp.bat                  # Launcher (no console window)
├── README.md
├── LICENSE
│
└── DevHost/
    ├── main.py                   # Entry point (python main.py)
    ├── app.py                    # Bootstrap: logging, UAC, Qt setup
    ├── build.bat                 # PyInstaller build script
    ├── requirements.txt
    │
    ├── config/
    │   ├── settings.example.json # Copy to settings.json and edit
    │   ├── settings.json         # Your local config (git-ignored)
    │   └── domains.json          # Domain store (git-ignored)
    │
    ├── services/
    │   ├── admin_service.py      # UAC elevation check and relaunch
    │   ├── apache_service.py     # Apache start / stop / restart / status
    │   ├── backup_service.py     # File backup and restore
    │   ├── hosts_service.py      # Windows hosts file management
    │   ├── httpd_conf_service.py # httpd.conf Listen port management
    │   ├── settings_service.py   # JSON config loader with typed accessors
    │   ├── validation_service.py # Domain name and path validation
    │   └── vhost_service.py      # Apache vhosts config management
    │
    ├── ui/
    │   ├── main_window.py        # Main application window
    │   ├── add_domain_dialog.py  # Add domain form
    │   ├── edit_domain_dialog.py # Edit domain form
    │   ├── settings_dialog.py    # Settings dialog (tabbed)
    │   ├── restore_dialog.py     # Backup restore dialog
    │   └── styles.py             # Global Qt stylesheet (Catppuccin Mocha)
    │
    ├── templates/
    │   └── apache_vhost.template # VirtualHost block template
    │
    ├── backups/                  # Auto-created backup files (git-ignored)
    ├── logs/                     # Application logs (git-ignored)
    └── assets/                   # Icons and images
```

---

## How It Works

### Marker-based file editing
DevHost never rewrites entire config files. It manages a delimited section:

```apache
# BEGIN DevHost
<VirtualHost *:80>
    ServerName myproject.test
    DocumentRoot "F:/php_workspace/myproject"
    ...
</VirtualHost>
# END DevHost
```

Everything outside the markers is left completely untouched.

### Enable / Disable
Disabling a domain comments out every line of its vhost block and its hosts entry. The entries remain in the file and can be re-enabled at any time — no data is lost.

### Domain store
`config/domains.json` is the source of truth for domain metadata (doc root, port, notes, enabled state). The config files are always re-rendered from this store, so manual edits to the vhost file outside the markers are preserved.

---

## Supported Server Types

| Type | Start / Stop method |
|------|---------------------|
| `xampp` | Direct `httpd.exe` launch (detached) + `taskkill` |
| `wamp` | `taskkill` + direct `httpd.exe` relaunch |
| `laragon` | `net start/stop laragon-apache` Windows service |
| `custom` | Direct `httpd.exe` launch + `taskkill` |

A named Windows service can be set in Settings for any type and takes priority over the default method.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
