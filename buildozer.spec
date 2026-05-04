[app]
title = NateWake
package.name = natewake
package.domain = org.perso
source.dir = .
source.include_exts = py,kv,json,md,joblib
version = 0.1
requirements = python3,kivy==2.3.0,kivymd==1.2.0,pandas,numpy,scikit-learn,scipy,joblib

# Entry point
source.main = main.py

# Orientation
orientation = portrait

# Android permissions
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE

# API levels
android.api = 33
android.minapi = 26

# Architectures
android.archs = arm64-v8a, armeabi-v7a

# Build options
android.release_artifact = aab
android.debug_artifact = apk

# Fullscreen
fullscreen = 0

# Log level (set to 2 for production, 1 for debug)
log_level = 1

# Gradle extras (required for newer Android API)
android.gradle_dependencies = com.google.android.material:material:1.9.0

# p4a branch
p4a.branch = master

[buildozer]
# Build directory
build_dir = .buildozer

# Warn if buildozer is used on an unsupported system
warn_on_root = 1
