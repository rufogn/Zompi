[app]
title = Zombi Avi 3D
package.name = zombiavi3d
package.domain = org.zombiavi
source.dir = .
source.include_exts = py,png,jpg,txt
version = 1.0

# pygame, Android'de python-for-android "pygame" tarifi ile derlenir
requirements = python3,pygame

orientation = landscape
fullscreen = 1

# LAN (sunucu/istemci) ve yüksek skor için izinler
android.permissions = INTERNET, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE, CHANGE_WIFI_MULTICAST_STATE

android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
