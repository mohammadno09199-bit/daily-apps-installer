#!/usr/bin/env python3
"""
Cross-Platform Essential Apps Installer (Windows & Linux)
Creator: Mohammad
Designed for quick, clean post-install provisioning.
"""

import os
import platform
import subprocess
import sys

# لیست پکیج‌ها در ویندوز (از طریق شناسه رسمی winget)
WINDOWS_PACKAGES = [
    ("7-Zip (Compression)", "7zip.7zip"),
    ("Google Chrome (Browser)", "Google.Chrome"),
    ("PotPlayer (Video Player)", "Daum.PotPlayer"),
    ("VLC Media Player", "VideoLAN.VLC"),
    ("Telegram Desktop", "Telegram.TelegramDesktop"),
    ("Notepad++ (Text Editor)", "Notepad++.Notepad++"),
    ("Foxit PDF Reader", "Foxit.FoxitReader"),
    ("AnyDesk (Remote Support)", "AnyDeskSoftwareGmbH.AnyDesk"),
]

# لیست پکیج‌ها در لینوکس (محیط‌های مبتنی بر Debian/Ubuntu/Parrot/Mint)
LINUX_PACKAGES = [
    ("p7zip-full (Compression)", "p7zip-full"),
    ("p7zip-rar (RAR Support)", "p7zip-rar"),
    ("Chromium Browser", "chromium-browser"),
    ("VLC Media Player", "vlc"),
    ("Telegram Desktop", "telegram-desktop"),
    ("Geany / Editor (Lightweight)", "geany"),
    ("Evince (PDF Reader)", "evince"),
    ("Restricted Codecs", "ubuntu-restricted-extras"),
]


def check_admin():
    """بررسی دسترسی Administrator / Root"""
    os_name = platform.system()
    if os_name == "Windows":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    else:
        return os.geteuid() == 0


def run_command(cmd, desc):
    """اجرای ایمن دستور با نمایش خروجی لحظه‌ای"""
    print(f"\n[+] در حال نصب: {desc} ...")
    try:
        res = subprocess.run(cmd, shell=True, check=True)
        if res.returncode == 0:
            print(f"[✔] {desc} با موفقیت نصب شد.")
    except subprocess.CalledProcessError:
        print(f"[✘] خطا در نصب {desc}. از این پکیج صرف‌نظر می‌شود.")
    except Exception as e:
        print(f"[✘] خطای غیرمنتظره: {e}")


def install_windows():
    print("=" * 60)
    print("سیستم‌عامل: Windows شناسایی شد.")
    print("استفاده از پکیج منیجر رسمی Windows Package Manager (winget)...")
    print("=" * 60)

    # بررسی وجود winget
    try:
        subprocess.run(["winget", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except:
        print("[!] خطای مهم: دستور 'winget' روی این ویندوز پیدا نشد.")
        print("لطفاً App Installer را از مایکروسافت استور آپدیت کنید یا پکیج‌ها را دستی نصب کنید.")
        return

    for name, pkg_id in WINDOWS_PACKAGES:
        # نصب خاموش، پذیرش خودکار لایسنس و عدم ایجاد پنجره مزاحم
        cmd = f'winget install --id {pkg_id} -e --silent --accept-package-agreements --accept-source-agreements'
        run_command(cmd, name)


def install_linux():
    print("=" * 60)
    print("سیستم‌عامل: Linux شناسایی شد.")
    print("به‌روزرسانی مخازن apt...")
    print("=" * 60)

    # آپدیت مخازن
    subprocess.run("apt-get update -y", shell=True)

    for name, pkg_name in LINUX_PACKAGES:
        cmd = f"DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg_name}"
        run_command(cmd, name)


def main():
    current_os = platform.system()
    print("\n" + "#" * 60)
    print("  اسکریپت خودکار نصب ابزارهای ضروری روزمره (محمد نوری)")
    print("#" * 60)

    # اخطار دسترسی در صورت نیاز
    if not check_admin():
        if current_os == "Windows":
            print("\n[!] هشدار: لطفاً ترمینال یا PowerShell را به صورت 'Run as Administrator' اجرا کنید تا نصب‌ها به خطای دسترسی نخورند.")
        else:
            print("\n[!] خطا: در لینوکس حتماً اسکریپت را با دستور sudo اجرا کنید:")
            print("    sudo python3 setup_apps.py")
            sys.exit(1)

    if current_os == "Windows":
        install_windows()
    elif current_os == "Linux":
        install_linux()
    else:
        print(f"[!] سیستم‌عامل {current_os} در حال حاضر پشتیبانی نمی‌شود.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("[🎉] تمام مراحل با موفقیت به پایان رسید! سیستم شما آماده استفاده است.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()