; Inno Setup script for the Bilimoria Mehta & Co. MIS Generator.
; Build the app first (python build.py), then compile this with Inno Setup
; (https://jrsoftware.org/isinfo.php) to produce Setup-BMC-MIS.exe.

#define AppName "Bilimoria Mehta & Co. MIS Generator"
#define AppShort "BMC MIS"
#define AppVersion "0.1.0"
#define AppPublisher "Bilimoria Mehta & Co."

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppShort}
DefaultGroupName={#AppShort}
UninstallDisplayName={#AppName}
OutputBaseFilename=Setup-BMC-MIS
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
WizardStyle=modern

[Files]
; Copies the entire PyInstaller one-folder build.
Source: "dist\BMC MIS\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\BMC MIS.exe"
Name: "{commondesktop}\{#AppShort}"; Filename: "{app}\BMC MIS.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Run]
Filename: "{app}\BMC MIS.exe"; Description: "Launch {#AppShort}"; Flags: nowait postinstall skipifsilent

; Note: all data (the SQLite database and exported reports) is stored under
; %LOCALAPPDATA%\BMC MIS and is left untouched on uninstall.
