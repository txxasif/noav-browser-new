; Inno Setup Script for Meta Creator (Windows)
#define MyAppName "Meta Creator"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Nova Meta Engine"
#define MyAppExeName "Run.bat"

[Setup]
AppId={{E5819F37-4D2A-4B6E-9C8E-329A90F845C2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\MetaCreator
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=MetaCreator-Setup-v1.0
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

; NOTE: every Source below must exist in the Windows distribution tree
; (build_windows_dist.py validates this before packaging). Add
; `skipifsourcedoesntexist` only for genuinely optional files.
[Files]
Source: "..\bin\*"; DestDir: "{app}\bin"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\core\*"; DestDir: "{app}\core"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\engine\*"; DestDir: "{app}\engine"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\extensions\*"; DestDir: "{app}\extensions"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\public\*"; DestDir: "{app}\public"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\instagram\*"; DestDir: "{app}\instagram"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\selfies\*"; DestDir: "{app}\selfies"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\img\*"; DestDir: "{app}\img"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\server.js"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\worker.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\runner.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\store.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\db.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\mem_guard.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\mail_providers.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\ai_config.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\ig_flow.py"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\selfie.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\package.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Run.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Run-Console.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Stop.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Update.bat"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\HOW_TO_RUN_ON_WINDOWS.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Stop {#MyAppName}"; Filename: "{app}\Stop.bat"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: shellexec postinstall skipifsilent
