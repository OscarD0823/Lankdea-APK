[app]
title = Lankdea Local Direct
package.name = lankdealocal
package.domain = app.lankdea
source.dir = .
source.include_exts = py,png,json,kv,ttf,otf,wav,txt
source.exclude_dirs = tests,.venv,build,dist,__pycache__,assets/splash_frames,scripts,docs
source.exclude_patterns = *.keystore,*.jks,*.p12,*.pfx,*.pem,*.key,*.lksource,*dpapi*,*firebase*.json
version = 3.6.0
requirements = python3,kivy,cryptography,pyotp,qrcode,pillow,requests,urllib3
orientation = portrait,landscape,portrait-reverse,landscape-reverse
fullscreen = 0
icon.filename = assets/cofre_icono.png
presplash.filename = assets/cofre_icono.png
android.permissions = INTERNET,ACCESS_NETWORK_STATE,CHANGE_WIFI_MULTICAST_STATE

android.api = 36
android.minapi = 26
android.ndk = 27c
android.archs = arm64-v8a
android.private_storage = True
android.allow_backup = False
android.allow_cleartext = True
android.accept_sdk_license = True
android.release_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 1
