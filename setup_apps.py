#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cross-platform CLI app installer (Windows: winget, Linux: apt)
- Interactive selection menu
- Presets
- Logging
- Preflight checks
- Continues on errors

Usage examples:
  python setup_apps.py
  python setup_apps.py --preset daily
  python setup_apps.py --list
  python setup_apps.py --install chrome 7zip vlc
  python setup_apps.py --dry-run --preset daily
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import platform
import shutil
import subprocess
import sys
from typing import Dict, List, Tuple


# -------------------------
# Package catalogs
# -------------------------

# Each entry: key -> (Human name, installer_id_or_pkgname)
WINDOWS_CATALOG: Dict[str, Tuple[str, str]] = {
    "7zip": ("7-Zip", "7zip.7zip"),
    "chrome": ("Google Chrome", "Google.Chrome"),
    "brave": ("Brave", "Brave.Brave"),
    "firefox": ("Mozilla Firefox", "Mozilla.Firefox"),
    "vlc": ("VLC Media Player", "VideoLAN.VLC"),
    "potplayer": ("PotPlayer", "Daum.PotPlayer"),
    "telegram": ("Telegram Desktop", "Telegram.TelegramDesktop"),
    "notepadpp": ("Notepad++", "Notepad++.Notepad++"),
    "sumatra": ("SumatraPDF", "SumatraPDF.SumatraPDF"),
    "foxit": ("Foxit PDF Reader", "Foxit.FoxitReader"),
    "anydesk": ("AnyDesk", "AnyDeskSoftwareGmbH.AnyDesk"),
}

LINUX_CATALOG: Dict[str, Tuple[str, str]] = {
    "p7zip": ("p7zip-full (7z support)", "p7zip-full"),
    "rar": ("p7zip-rar (RAR support)", "p7zip-rar"),
    "chromium": ("Chromium Browser", "chromium-browser"),
    "firefox": ("Firefox", "firefox"),
    "vlc": ("VLC Media Player", "vlc"),
    "telegram": ("Telegram Desktop", "telegram-desktop"),
    "geany": ("Geany (Editor)", "geany"),
    "evince": ("Evince (PDF)", "evince"),
    "codecs": ("Restricted Codecs", "ubuntu-restricted-extras"),
}

PRESETS = {
    "daily": ["7zip", "chrome", "vlc", "telegram", "notepadpp", "sumatra"],
    # Linux daily preset will be auto-mapped to equivalents
}


# -------------------------
# Utilities
# -------------------------

LOG_FILE = "install.log"


def log(msg: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # If logging fails, continue silently.
        pass


def run(cmd: List[str] | str, *, shell: bool = False, timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        shell=shell,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def require_admin_or_root() -> None:
    os_name = platform.system()
    if os_name == "Windows":
        try:
            import ctypes
            if ctypes.windll.shell32.IsUserAnAdmin() == 0:
                raise PermissionError
        except Exception:
            log("ERROR: Please run Terminal/PowerShell as Administrator.")
            sys.exit(1)
    else:
        if os.geteuid() != 0:
            log("ERROR: Please run with sudo: sudo python3 setup_apps.py")
            sys.exit(1)


def have_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def check_internet() -> bool:
    # Lightweight connectivity check (DNS + HTTPS)
    try:
        import socket
        socket.setdefaulttimeout(3)
        socket.gethostbyname("github.com")
        return True
    except Exception:
        return False


def detect_platform() -> str:
    os_name = platform.system()
    if os_name == "Windows":
        return "windows"
    if os_name == "Linux":
        return "linux"
    return "other"


# -------------------------
# Catalog selection / mapping
# -------------------------

def get_catalog(os_key: str) -> Dict[str, Tuple[str, str]]:
    return WINDOWS_CATALOG if os_key == "windows" else LINUX_CATALOG


def map_windows_preset_to_linux(keys: List[str]) -> List[str]:
    """Map common Windows keys to Linux equivalents when possible."""
    mapping = {
        "7zip": "p7zip",
        "chrome": "chromium",     # closest common default
        "brave": "chromium",
        "notepadpp": "geany",
        "sumatra": "evince",
        "foxit": "evince",
        "potplayer": "vlc",
    }
    out = []
    for k in keys:
        out.append(mapping.get(k, k))
    # de-dup while keeping order
    seen = set()
    dedup = []
    for k in out:
        if k not in seen:
            seen.add(k)
            dedup.append(k)
    return dedup


# -------------------------
# Interactive menu
# -------------------------

def interactive_select(os_key: str) -> List[str]:
    catalog = get_catalog(os_key)
    keys = list(catalog.keys())

    selected = set()

    def render() -> None:
        print("\n" + "=" * 70)
        print("Interactive installer - select packages")
        print("Type numbers separated by space to toggle, or commands:")
        print("  a=all, n=none, i=install, q=quit")
        print("=" * 70)
        for idx, k in enumerate(keys, start=1):
            name, pkg = catalog[k]
            mark = "✓" if k in selected else " "
            print(f"{idx:>2}. [{mark}] {k:<10} - {name} ({pkg})")
        print("=" * 70)

    while True:
        render()
        s = input("Selection> ").strip().lower()
        if s in ("q", "quit", "exit"):
            log("User quit.")
            sys.exit(0)
        if s in ("a", "all"):
            selected = set(keys)
            continue
        if s in ("n", "none", "clear"):
            selected = set()
            continue
        if s in ("i", "install", "go"):
            if not selected:
                print("Nothing selected.")
                continue
            return list(selected)

        # Toggle numeric selections
        parts = s.split()
        any_toggle = False
        for p in parts:
            if not p.isdigit():
                continue
            idx = int(p)
            if 1 <= idx <= len(keys):
                k = keys[idx - 1]
                if k in selected:
                    selected.remove(k)
                else:
                    selected.add(k)
                any_toggle = True
        if not any_toggle:
            print("Invalid input. Example: '1 3 5' or 'a' or 'i'.")


# -------------------------
# Installers
# -------------------------

def winget_install(pkg_id: str, name: str, *, dry_run: bool) -> bool:
    cmd = [
        "winget", "install",
        "--id", pkg_id,
        "-e",
        "--silent",
        "--accept-package-agreements",
        "--accept-source-agreements",
    ]
    if dry_run:
        log(f"DRY-RUN winget: {' '.join(cmd)}")
        return True

    log(f"Installing (winget): {name}")
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.returncode == 0:
        log(f"OK: {name}")
        return True

    log(f"FAIL: {name} (code={p.returncode})")
    if p.stdout:
        log("STDOUT:\n" + p.stdout.strip())
    if p.stderr:
        log("STDERR:\n" + p.stderr.strip())
    return False


def apt_install(pkg_name: str, name: str, *, dry_run: bool) -> bool:
    cmd = ["bash", "-lc", f"DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg_name}"]
    if dry_run:
        log(f"DRY-RUN apt: {cmd[-1]}")
        return True

    log(f"Installing (apt): {name}")
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.returncode == 0:
        log(f"OK: {name}")
        return True

    log(f"FAIL: {name} (code={p.returncode})")
    if p.stdout:
        log("STDOUT:\n" + p.stdout.strip())
    if p.stderr:
        log("STDERR:\n" + p.stderr.strip())
    return False


def preflight(os_key: str) -> None:
    log(f"Detected OS: {os_key}")

    if not check_internet():
        log("WARNING: Internet seems unavailable. Installs may fail.")

    if os_key == "windows":
        if not have_command("winget"):
            log("ERROR: winget not found. Install/Update 'App Installer' from Microsoft Store.")
            sys.exit(1)
    elif os_key == "linux":
        if not have_command("apt-get"):
            log("ERROR: apt-get not found. This script supports Debian/Ubuntu-based distros.")
            sys.exit(1)
    else:
        log("ERROR: Unsupported OS.")
        sys.exit(1)


def install_selected(os_key: str, keys: List[str], *, dry_run: bool) -> None:
    catalog = get_catalog(os_key)

    ok = 0
    fail = 0

    if os_key == "linux" and not dry_run:
        log("Running apt-get update...")
        u = subprocess.run(["bash", "-lc", "apt-get update -y"], text=True, capture_output=True)
        if u.returncode != 0:
            log("WARNING: apt-get update failed; continuing anyway.")

    for k in keys:
        if k not in catalog:
            log(f"SKIP: unknown package key '{k}'")
            fail += 1
            continue

        name, pkg = catalog[k]
        if os_key == "windows":
            if winget_install(pkg, name, dry_run=dry_run):
                ok += 1
            else:
                fail += 1
        else:
            if apt_install(pkg, name, dry_run=dry_run):
                ok += 1
            else:
                fail += 1

    log(f"Done. Success={ok}, Failed={fail}. Log saved to: {os.path.abspath(LOG_FILE)}")


# -------------------------
# CLI
# -------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--list", action="store_true", help="List available package keys for this OS and exit.")
    ap.add_argument("--preset", choices=sorted(PRESETS.keys()), help="Install a predefined set.")
    ap.add_argument("--install", nargs="*", help="Install by keys, e.g. --install chrome 7zip vlc")
    ap.add_argument("--interactive", action="store_true", help="Interactive menu selection (default if no args).")
    ap.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    return ap.parse_args()


def main() -> None:
    os_key = detect_platform()
    require_admin_or_root()
    preflight(os_key)

    args = parse_args()

    if args.list:
        cat = get_catalog(os_key)
        print("\nAvailable packages:")
        for k, (name, pkg) in cat.items():
            print(f"  {k:<10} -> {name} ({pkg})")
        sys.exit(0)

    # Decide selection
    selected_keys: List[str] = []

    if args.preset:
        keys = PRESETS[args.preset]
        if os_key == "linux":
            keys = map_windows_preset_to_linux(keys)
        selected_keys = keys

    elif args.install is not None and len(args.install) > 0:
        selected_keys = args.install

    else:
        # default interactive
        selected_keys = interactive_select(os_key)

    install_selected(os_key, selected_keys, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
