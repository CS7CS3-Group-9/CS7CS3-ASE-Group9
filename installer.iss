; installer.iss — Inno Setup script for Dublin City Dashboard
; Requires Inno Setup 6+: https://jrsoftware.org/isinfo.php
; Build after PyInstaller: right-click → Compile, or iscc installer.iss

#define AppName      "Dublin City Dashboard"
#define AppVersion   "1.0.0"
#define AppPublisher "CS7CS3 Group 9"
#define AppExeName   "DublinCityDashboard.exe"
#define DistDir      "dist\DublinCityDashboard"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL=http://ase-citydash-board.duckdns.org
AppSupportURL=http://ase-citydash-board.duckdns.org
AppUpdatesURL=http://ase-citydash-board.duckdns.org
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; No admin required — installs to per-user AppData if admin not available
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer_output
OutputBaseFilename=DublinCityDashboard-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; WebView2 is pre-installed on Windows 10 20H2+ and all Windows 11.
; If you need to support older Windows 10, add a WebView2 bootstrapper here.
MinVersion=10.0.19042

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";   Description: "{cm:CreateDesktopIcon}";   GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupentry";  Description: "Start automatically at login"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; All PyInstaller output
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";          Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\desktop\assets\tray-icon.ico"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";    Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\desktop\assets\tray-icon.ico"; Tasks: desktopicon

[Registry]
; Optional: launch at startup
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#AppName}"; \
  ValueData: """{app}\{#AppExeName}"""; \
  Flags: uninsdeletevalue; Tasks: startupentry

[Run]
Filename: "{app}\{#AppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(AppName,'&','&&')}}"; \
  Flags: nowait postinstall skipifsilent
