# Cross-platform packaging

`Imervue.spec` builds the Windows executable. The same PyInstaller analysis
works on macOS and Linux; only the bundling step and the path separators in the
`datas` list differ. The runtime file association is already cross-platform —
see `Imervue/system/file_association.py` (Windows registry, Linux XDG desktop
entry, macOS handled by the `.app` `Info.plist` below).

## macOS — `.app` bundle

Run PyInstaller on a Mac. Use forward-slash `datas` paths and append a `BUNDLE`
step so Finder treats the output as an app:

```python
app = BUNDLE(
    exe,
    name='Imervue.app',
    icon='Imervue.icns',           # convert Imervue.ico → .icns
    bundle_identifier='com.imervue.viewer',
    info_plist={
        # Declare the formats Imervue opens so Finder offers "Open With".
        'CFBundleDocumentTypes': [{
            'CFBundleTypeName': 'Image',
            'LSItemContentTypes': [
                'public.png', 'public.jpeg', 'com.compuserve.gif',
                'org.webmproject.webp', 'public.tiff', 'public.heic',
            ],
            'CFBundleTypeRole': 'Viewer',
        }],
    },
)
```

Distribute the `.app` inside a `.dmg` (`hdiutil create`). Wrap in `codesign`
+ `xcrun notarytool` for Gatekeeper-clean distribution.

## Linux — AppImage

Build a one-folder PyInstaller bundle, drop in the desktop entry and icon, then
run `appimagetool`:

```sh
pyinstaller Imervue.spec                       # produces dist/Imervue/
cp packaging/imervue.desktop dist/Imervue/      # (or generate via file_association)
cp Imervue.png dist/Imervue/
appimagetool dist/Imervue Imervue-x86_64.AppImage
```

The `.desktop` body is exactly what
`file_association.desktop_entry_content(...)` produces, so the same MIME
associations apply whether the user installs the AppImage or runs from source
(`register_file_association()` writes `~/.local/share/applications/imervue.desktop`).

## Notes

* The `datas` list in `Imervue.spec` uses Windows `\\` separators. On
  macOS/Linux use `/` (or `os.path.join`) — PyInstaller does not translate them.
* Heavy model blobs stay out of every bundle (see `_is_model_asset` in the
  spec); plugins download them on first use to `<app_dir>/plugins/<name>/models/`.
* `Imervue/system/app_paths.py` already resolves frozen paths for all three
  platforms, so no code changes are needed for the bundle to find its data.
