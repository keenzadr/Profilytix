; Compile through scripts/build_windows.ps1 -Installer.
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef SourceRoot
  #define SourceRoot ".."
#endif

[Setup]
AppId={{43450D5B-E2F2-4C25-A211-89D3ACFD95CC}
AppName=Profilytix
AppVersion={#AppVersion}
AppPublisher=Profilytix
DefaultDirName={localappdata}\Programs\Profilytix
DefaultGroupName=Profilytix
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#SourceRoot}\dist\installer
OutputBaseFilename=Profilytix-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\Profilytix.exe
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Dirs]
Name: "{localappdata}\Profilytix\logs"

[Files]
Source: "{#SourceRoot}\dist\Profilytix\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Profilytix"; Filename: "{app}\Profilytix.exe"
Name: "{group}\Offline demo"; Filename: "{app}\demo\demo_finances.csv"
Name: "{group}\Diagnostic logs"; Filename: "{localappdata}\Profilytix\logs"
Name: "{autodesktop}\Profilytix"; Filename: "{app}\Profilytix.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Profilytix.exe"; Description: "Launch Profilytix"; Flags: nowait postinstall skipifsilent
