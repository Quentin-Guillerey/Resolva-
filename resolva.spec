# resolva.spec
# Build with:  pyinstaller resolva.spec
#
# Produces a single-file executable that starts the Flask server locally and
# opens Resolva in the default browser. No Python install needed on the host.
# Same codebase as the web version — this just wraps it in a launcher.
#
# Must be built on the OS you want to ship to (PyInstaller does not
# cross-compile): build the Windows .exe on Windows.

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    # Bundle the templates, CSS, and demo CSV next to the code so the
    # packaged app can find them via the resource_path() helper in app.py.
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('data', 'data'),
    ],
    hiddenimports=[
        'resolva.config', 'resolva.store', 'resolva.audit',
        'resolva.classifier', 'resolva.ai', 'resolva.ingestion',
        'resolva.accounts', 'resolva.notify',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='Resolva',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # no console window; it's a browser app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,            # add icon='resolva.ico' once you have one
)
