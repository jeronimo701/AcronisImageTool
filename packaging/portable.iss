#ifndef Payload
#error Payload is required
#endif
#ifndef SetupOut
#error SetupOut is required
#endif
[Setup]
AppId=Jeronimo701-{#Product}
AppName={#Product}
AppVersion=2026.10.28
AppPublisher=Jeronimo701
DefaultDirName={localappdata}\Programs\{#Product}
DisableProgramGroupPage=yes
DisableDirPage=no
PrivilegesRequired=lowest
Uninstallable=no
CreateUninstallRegKey=no
OutputDir={#SetupOut}
OutputBaseFilename={#Product}-Setup-snapshot-2026-10-28
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no
[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
