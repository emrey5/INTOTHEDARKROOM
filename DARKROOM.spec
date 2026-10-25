# PyInstaller tarifi: python -m PyInstaller DARKROOM.spec
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

datas = [("promptvideo/fonts", "promptvideo/fonts"), ("promptvideo/assets", "promptvideo/assets"),
         ("ornekler", "ornekler")]
datas += collect_data_files("imageio_ffmpeg")
datas += collect_data_files("edge_tts")
binaries = collect_dynamic_libs("cairo") + collect_dynamic_libs("imageio_ffmpeg")
hidden = (collect_submodules("edge_tts") + collect_submodules("ddgs") + collect_submodules("openpyxl")
          + collect_submodules("pypdf") + ["lxml.etree", "gtts"])

a = Analysis(["baslat.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=["tkinter", "matplotlib", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="DARKROOM", console=False,
          icon="promptvideo/assets/icon.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="DARKROOM")
