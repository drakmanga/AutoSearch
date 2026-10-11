; Installer for AutoSearch. Build the exe first, then compile this:
;     .venv\Scripts\python.exe -m PyInstaller windows\autosearch.spec --noconfirm
;     & "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" windows\installer.iss
; Result: dist\AutoSearch-Setup-<version>.exe

#define AppName "AutoSearch"
#define AppVersion "1.0.0"
#define AppExe "AutoSearch.exe"

[Setup]
AppId={{7C4E1A82-5F3D-4B96-9E27-3A8D6B1C0F54}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
OutputDir=..\dist
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
SetupIconFile=autosearch.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; per-user install: no UAC prompt on top of the SmartScreen warning
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; stop a running copy before replacing its files
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Dirs]
; so the Start Menu shortcut below is not dangling before the first run
Name: "{localappdata}\{#AppName}"

[Files]
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Cartella dati e configurazione"; Filename: "{localappdata}\{#AppName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; the install folder only: config.yaml and data\jobs.db live in
; %LOCALAPPDATA%\AutoSearch and are deliberately left in place
Type: filesandordirs; Name: "{app}"
