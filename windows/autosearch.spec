# PyInstaller build of AutoSearch.exe. Run from the repo root:
#     .venv\Scripts\pyinstaller windows\autosearch.spec --noconfirm
#
# onedir (not onefile): starts faster and trips fewer antivirus heuristics;
# the Inno Setup script ships the whole folder anyway.
from PyInstaller.utils.hooks import collect_data_files

datas = [
    # web.py resolves these with Path(__file__).with_name(...), so they must
    # keep sitting next to the frozen autosearch package
    ("../autosearch/index.html", "autosearch"),
    ("../autosearch/favicon.svg", "autosearch"),
    ("../autosearch/icon-180.png", "autosearch"),
    # seeds config.yaml in %LOCALAPPDATA%\AutoSearch on first run
    ("../config.example.yaml", "."),
]
datas += collect_data_files("tzdata")  # zoneinfo needs it for Europe/Rome

a = Analysis(
    ["launcher.py"],
    pathex=[".."],
    datas=datas,
    hiddenimports=["autosearch.sources.linkedin", "autosearch.sources.inpa"],
    excludes=["tkinter", "unittest", "pydoc", "doctest"],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="AutoSearch",
    console=False,          # no console window: the launcher logs to data/web.log
    icon="autosearch.ico",
    version="version.txt",
)
COLLECT(exe, a.binaries, a.datas, name="AutoSearch")
