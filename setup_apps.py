#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Post-install app setup
Windows 10/11: winget
Debian-based Linux: apt

Python 3.8+

Examples:
  python setup_apps.py
  python setup_apps.py --list
  python setup_apps.py --preset daily --dry-run
  python setup_apps.py --install chrome vlc git --yes
  python setup_apps.py --settings restore-point fast-startup-off show-extensions
"""

import argparse
import ctypes
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# (Display name, winget ID or None, apt package candidates)
# None means the application is not offered on that platform by this script.
APPS = {
    "7zip":         ("7-Zip",                  "7zip.7zip",                       ("7zip", "p7zip-full")),
    "chrome":       ("Google Chrome",          "Google.Chrome",                   None),
    "brave":        ("Brave",                  "Brave.Brave",                    None),
    "firefox":      ("Firefox",                "Mozilla.Firefox",                 ("firefox-esr", "firefox")),
    "chromium":     ("Chromium",               None,                              ("chromium", "chromium-browser")),
    "vlc":          ("VLC",                    "VideoLAN.VLC",                    ("vlc",)),
    "potplayer":    ("PotPlayer",              "Daum.PotPlayer",                  None),
    "telegram":     ("Telegram Desktop",       "Telegram.TelegramDesktop",        ("telegram-desktop",)),
    "notepadpp":    ("Notepad++",              "Notepad++.Notepad++",             None),
    "geany":        ("Geany",                  None,                              ("geany",)),
    "sumatra":      ("SumatraPDF",             "SumatraPDF.SumatraPDF",           None),
    "evince":       ("Evince PDF Reader",      None,                              ("evince",)),
    "libreoffice":  ("LibreOffice",            "TheDocumentFoundation.LibreOffice", ("libreoffice",)),
    "thunderbird":  ("Thunderbird",            "Mozilla.Thunderbird",             ("thunderbird",)),
    "filezilla":    ("FileZilla",              "FileZilla.FileZilla",             ("filezilla",)),
    "winscp":       ("WinSCP",                 "WinSCP.WinSCP",                   None),
    "anydesk":      ("AnyDesk",                "AnyDeskSoftwareGmbH.AnyDesk",     None),
    "git":          ("Git",                    "Git.Git",                         ("git",)),
    "vscode":       ("Visual Studio Code",     "Microsoft.VisualStudioCode",      None),
    "python":       ("Python 3.14",            "Python.Python.3.14",              ("python3",)),
    "python-venv":  ("Python virtualenv tools", None,                             ("python3-venv",)),
    "github-cli":   ("GitHub CLI",             "GitHub.cli",                      None),
    "node":         ("Node.js LTS",            "OpenJS.NodeJS.LTS",               ("nodejs",)),
    "powertoys":    ("Microsoft PowerToys",    "Microsoft.PowerToys",             None),
    "terminal":     ("Windows Terminal",       "Microsoft.WindowsTerminal",       None),
    "obs":          ("OBS Studio",             "OBSProject.OBSStudio",            ("obs-studio",)),
    "gimp":         ("GIMP",                   "GIMP.GIMP.3",                    ("gimp",)),
    "audacity":     ("Audacity",               "Audacity.Audacity",               ("audacity",)),
    "qbittorrent":  ("qBittorrent",            "qBittorrent.qBittorrent",         ("qbittorrent",)),
    "keepassxc":    ("KeePassXC",              "KeePassXCTeam.KeePassXC",         ("keepassxc",)),
    "flameshot":    ("Flameshot",              None,                              ("flameshot",)),
    "curl":         ("curl",                   None,                              ("curl",)),
    "htop":         ("htop",                   None,                              ("htop",)),
}

WINDOWS_SETTINGS = {
    "restore-point":     "تلاش برای ساخت Restore Point پیش از تغییرات",
    "fast-startup-off":  "غیرفعال کردن Fast Startup؛ بدون غیرفعال کردن Hibernate",
    "show-extensions":   "نمایش پسوند فایل‌ها در File Explorer",
    "persian-standard":  "افزودن کیبورد Persian (Standard) برای کاربر فعلی",
    "windows-update":    "باز کردن صفحه Windows Update برای بررسی دستی",
    "activation":        "باز کردن صفحه وضعیت فعال‌سازی ویندوز",
}

DAILY = {
    "windows": ["7zip", "chrome", "vlc", "telegram", "sumatra", "libreoffice"],
    "linux":   ["7zip", "firefox", "vlc", "telegram", "evince", "libreoffice"],
}

DEVELOPER_EXTRA = {
    "windows": ["git", "vscode", "python", "github-cli", "terminal"],
    "linux":   ["git", "python", "python-venv", "geany", "curl", "htop"],
}


def get_log_path():
    for directory in (Path.home(), Path(tempfile.gettempdir())):
        path = directory / "setup_apps.log"
        try:
            path.touch(exist_ok=True)
            return path
        except OSError:
            continue
    return None


LOG_FILE = get_log_path()


def log(message):
    print(message, flush=True)
    if LOG_FILE:
        try:
            with LOG_FILE.open("a", encoding="utf-8") as file:
                file.write(message + "\n")
        except OSError:
            pass


def show_log_tail(lines=7):
    if not LOG_FILE:
        return
    try:
        from collections import deque
        with LOG_FILE.open("r", encoding="utf-8", errors="replace") as file:
            tail = deque(file, maxlen=lines)
        for line in tail:
            print("    " + line.rstrip())
    except OSError:
        pass


def run_command(command, timeout=1800, env=None):
    """Run a fixed argument list; never invoke a shell."""
    log("COMMAND: " + subprocess.list2cmdline(command))
    try:
        if LOG_FILE:
            with LOG_FILE.open("a", encoding="utf-8", errors="replace") as file:
                result = subprocess.run(
                    command, stdout=file, stderr=subprocess.STDOUT,
                    timeout=timeout, env=env, check=False
                )
        else:
            result = subprocess.run(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                timeout=timeout, env=env, check=False
            )
        if result.returncode != 0:
            log("FAILED: exit code " + str(result.returncode))
            show_log_tail()
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        log("FAILED: " + str(exc))
        return False


def detect_os():
    name = platform.system()
    if name == "Windows":
        return "windows"
    if name == "Linux":
        return "linux"
    return None


def supported_apps(os_name):
    column = 1 if os_name == "windows" else 2
    return {key: app for key, app in APPS.items() if app[column] is not None}


def is_debian_based():
    try:
        text = Path("/etc/os-release").read_text(encoding="utf-8").lower()
        return bool(re.search(r"(?m)^id=(debian|ubuntu|linuxmint|parrot)$", text)
                    or re.search(r"(?m)^id_like=.*\b(debian|ubuntu)\b", text))
    except OSError:
        return False


def is_windows_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def preset_keys(os_name, preset):
    if preset == "full":
        return list(supported_apps(os_name))
    keys = list(DAILY[os_name])
    if preset == "developer":
        keys += DEVELOPER_EXTRA[os_name]
    return list(dict.fromkeys(keys))


def select_menu(title, entries, defaults=()):
    keys = list(entries)
    selected = set(defaults) & set(keys)

    while True:
        print("\n" + title)
        print("-" * 65)
        for number, key in enumerate(keys, 1):
            mark = "x" if key in selected else " "
            print(f"{number:>2}. [{mark}] {key:<20} {entries[key]}")
        print("شماره‌ها را با فاصله یا ویرگول وارد کن.")
        print("a=همه | n=هیچ‌کدام | d=پیش‌فرض | i=ادامه | q=خروج")

        try:
            answer = input("> ").strip().lower()
        except EOFError:
            raise SystemExit("ورودی تعاملی در دسترس نیست؛ از --preset استفاده کن.")

        if answer == "q":
            raise SystemExit(0)
        if answer == "a":
            selected = set(keys)
        elif answer == "n":
            selected.clear()
        elif answer == "d":
            selected = set(defaults) & set(keys)
        elif answer == "i":
            return [key for key in keys if key in selected]
        else:
            parts = answer.replace(",", " ").split()
            if not parts or any(not p.isdigit() or
                                not 1 <= int(p) <= len(keys) for p in parts):
                print("ورودی نامعتبر است؛ مثلاً: 1 3 5")
                continue
            for part in parts:
                key = keys[int(part) - 1]
                if key in selected:
                    selected.remove(key)
                else:
                    selected.add(key)


def apt_installed(package):
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Status}", package],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, check=False
    )
    return result.returncode == 0 and result.stdout.strip() == "install ok installed"


def apt_available(package):
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    result = subprocess.run(
        ["apt-cache", "policy", package],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, env=env, check=False
    )
    return result.returncode == 0 and bool(
        re.search(r"(?m)^\s*Candidate:\s*(?!\(none\))\S+", result.stdout)
    )


def winget_installed(package_id):
    """Best-effort detection; winget --no-upgrade also protects reruns."""
    try:
        result = subprocess.run(
            ["winget", "list", "--id", package_id, "--exact"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, errors="replace", timeout=90, check=False
        )
        pattern = r"\s+" + re.escape(package_id) + r"\s+\S+"
        return result.returncode == 0 and any(
            re.search(pattern, line) for line in result.stdout.splitlines()
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


def install_windows(key, dry_run):
    name, package_id, _ = APPS[key]
    command = [
        "winget", "install", "--id", package_id, "--exact",
        "--source", "winget", "--silent", "--no-upgrade",
        "--accept-package-agreements", "--accept-source-agreements",
    ]

    if dry_run:
        log("DRY RUN: " + name + " -> " + subprocess.list2cmdline(command))
        return "preview"

    if winget_installed(package_id):
        log("SKIP: " + name + " is already installed.")
        return "skip"

    log("INSTALL: " + name)
    if run_command(command):
        log("OK: " + name)
        return "ok"

    # An existing application may have caused a nonzero winget exit code.
    if winget_installed(package_id):
        log("SKIP: " + name + " is already present.")
        return "skip"

    return "fail"


def install_linux(key, dry_run):
    name, _, candidates = APPS[key]

    if dry_run:
        log("DRY RUN: " + name + " -> apt candidates: " +
            ", ".join(candidates))
        return "preview"

    for package in candidates:
        if apt_installed(package):
            log("SKIP: " + name + " is already installed (" + package + ").")
            return "skip"

    package = next((p for p in candidates if apt_available(p)), None)
    if package is None:
        log("FAILED: no apt candidate for " + name +
            " (" + ", ".join(candidates) + ").")
        return "fail"

    log("INSTALL: " + name + " (" + package + ")")
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    command = ["apt-get", "install", "-y", package]
    if run_command(command, env=env):
        log("OK: " + name)
        return "ok"
    return "fail"


def registry_dword(root, subkey, name, value):
    import winreg

    with winreg.CreateKeyEx(root, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            previous, _ = winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            previous = None

        if previous == value:
            log("SKIP: setting already has the requested value.")
            return "skip"

        log(f"REGISTRY: {subkey}\\{name}: {previous!r} -> {value!r}")
        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
        return "ok"


def apply_windows_setting(key, dry_run):
    if dry_run:
        log("DRY RUN: Windows setting -> " + key)
        return "preview"

    if key in ("windows-update", "activation"):
        uri = ("ms-settings:windowsupdate" if key == "windows-update"
               else "ms-settings:activation")
        try:
            os.startfile(uri)
            log("OPENED: " + uri + " (no update or activation performed)")
            return "ok"
        except OSError as exc:
            log("FAILED: " + str(exc))
            return "fail"

    if key == "show-extensions":
        try:
            import winreg
            return registry_dword(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                "HideFileExt", 0
            )
        except OSError as exc:
            log("FAILED: " + str(exc))
            return "fail"

    if key == "persian-standard":
        # Preserve existing display languages and keyboard layouts.
        script = (
            "$ErrorActionPreference='Stop'; "
            "$list=Get-WinUserLanguageList; "
            "$fa=$list | Where-Object LanguageTag -EQ 'fa-IR' | "
            "Select-Object -First 1; "
            "$changed=$false; "
            "if($null -eq $fa) { "
            "$list.Add('fa-IR'); "
            "$fa=$list | Where-Object LanguageTag -EQ 'fa-IR' | "
            "Select-Object -First 1; "
            "$fa.InputMethodTips.Clear(); $changed=$true }; "
            "if(-not $fa.InputMethodTips.Contains('0429:00050429')) { "
            "$fa.InputMethodTips.Add('0429:00050429'); $changed=$true }; "
            "if($changed) { Set-WinUserLanguageList -LanguageList $list -Force }"
        )
        return ("ok" if run_command(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-Command", script], timeout=180
        ) else "fail")

    if not is_windows_admin():
        log("FAILED: " + key + " requires an Administrator terminal.")
        return "fail"

    if key == "fast-startup-off":
        try:
            import winreg
            return registry_dword(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Power",
                "HiberbootEnabled", 0
            )
        except OSError as exc:
            log("FAILED: " + str(exc))
            return "fail"

    if key == "restore-point":
        script = (
            "$ErrorActionPreference='Stop'; "
            "Checkpoint-Computer -Description 'Before setup_apps changes' "
            "-RestorePointType 'MODIFY_SETTINGS'"
        )
        return ("ok" if run_command(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-Command", script], timeout=900
        ) else "fail")

    return "fail"


def parse_arguments():
    parser = argparse.ArgumentParser(description="Choose apps and post-install settings.")
    parser.add_argument("--list", action="store_true", help="List apps for this OS.")
    parser.add_argument("--list-settings", action="store_true",
                        help="List optional Windows settings.")
    parser.add_argument("--preset", choices=["daily", "developer", "full"])
    parser.add_argument("--install", nargs="+", metavar="APP")
    parser.add_argument("--settings", nargs="+", metavar="SETTING")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without installing or changing settings.")
    parser.add_argument("--yes", action="store_true",
                        help="Skip final confirmation.")
    return parser, parser.parse_args()


def main():
    os_name = detect_os()
    if os_name is None:
        print("Only Windows and Debian-based Linux are supported.")
        return 2

    parser, args = parse_arguments()
    available = supported_apps(os_name)

    if args.list or args.list_settings:
        if args.list:
            print("\nAvailable applications:")
            for key, app in available.items():
                print(f"  {key:<20} {app[0]}")
        if args.list_settings:
            if os_name != "windows":
                print("\nWindows settings do not apply to Linux.")
            else:
                print("\nOptional Windows settings:")
                for key, description in WINDOWS_SETTINGS.items():
                    print(f"  {key:<20} {description}")
        return 0

    if args.preset and args.install:
        parser.error("Use either --preset or --install, not both.")

    if args.install:
        unknown = [key for key in args.install if key not in available]
        if unknown:
            parser.error("Unavailable app key(s): " + ", ".join(unknown))

    if args.settings:
        if os_name != "windows":
            parser.error("--settings is available on Windows only.")
        unknown = [key for key in args.settings if key not in WINDOWS_SETTINGS]
        if unknown:
            parser.error("Unknown setting(s): " + ", ".join(unknown))

    interactive = not (args.preset or args.install or args.settings)

    if interactive:
        app_labels = {key: app[0] for key, app in available.items()}
        apps = select_menu(
            "برنامه‌ها را انتخاب کن:",
            app_labels,
            defaults=preset_keys(os_name, "daily")
        )
        settings = (
            select_menu("تنظیمات اختیاری ویندوز را انتخاب کن:",
                        WINDOWS_SETTINGS)
            if os_name == "windows" else []
        )
    else:
        apps = (preset_keys(os_name, args.preset) if args.preset
                else list(dict.fromkeys(args.install or [])))
        settings = list(dict.fromkeys(args.settings or []))

    if not apps and not settings:
        print("هیچ کاری انتخاب نشده است.")
        return 0

    print("\nSelected apps:", ", ".join(apps) or "none")
    print("Selected settings:", ", ".join(settings) or "none")
    print("Mode:", "PREVIEW" if args.dry_run else "APPLY")
    print("Log:", LOG_FILE or "unavailable")

    if not args.dry_run and not args.yes:
        if input("ادامه بدهم؟ [y/N] ").strip().lower() not in ("y", "yes"):
            print("انصراف داده شد.")
            return 0

    if not args.dry_run:
        if apps and os_name == "windows" and not shutil.which("winget"):
            log("ERROR: winget not found; update/install Windows App Installer.")
            return 2

        if apps and os_name == "linux":
            if not is_debian_based():
                log("ERROR: this Linux distribution is not Debian-based.")
                return 2
            if not all(shutil.which(p) for p in
                       ("apt-get", "apt-cache", "dpkg-query")):
                log("ERROR: apt tools are missing.")
                return 2
            if os.geteuid() != 0:
                log("ERROR: run with sudo for apt installations.")
                return 2

    results = []

    # A selected restore point must run before installations and other settings.
    if os_name == "windows" and "restore-point" in settings:
        log("\nSETTING: restore-point")
        results.append(apply_windows_setting("restore-point", args.dry_run))
        settings.remove("restore-point")

    if apps and os_name == "linux" and not args.dry_run:
        log("\nUpdating apt package indexes...")
        if not run_command(["apt-get", "update"], timeout=900):
            log("WARNING: apt update failed; using cached indexes if available.")

    for key in apps:
        if os_name == "windows":
            results.append(install_windows(key, args.dry_run))
        else:
            results.append(install_linux(key, args.dry_run))

    for key in settings:
        log("\nSETTING: " + key)
        results.append(apply_windows_setting(key, args.dry_run))

    log(
        "\nFinished. "
        + " | ".join(f"{status}={results.count(status)}"
                   for status in ("ok", "skip", "preview", "fail"))
    )
    log("Log file: " + str(LOG_FILE))
    return 1 if "fail" in results else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(130)
