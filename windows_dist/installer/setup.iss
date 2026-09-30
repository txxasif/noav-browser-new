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
Source: "..\server\*"; DestDir: "{app}\server"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\pipelines\*"; DestDir: "{app}\pipelines"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\tg\*"; DestDir: "{app}\tg"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
; .py* wildcard: matches worker.py (dev build) or worker.pyc (protected build).
Source: "..\worker.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\runner.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\store.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\db.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\ai_config.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\ig_flow.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tg_bot.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tg_accounts.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tg_fingerprint.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tg_login.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tg_login_mtproto.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\mtproto_bot.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tg_balance.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tg_toggle.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\warm_pool.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tg_tasks.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tg_flows.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tg_steps.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\run_cookie_cycle.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\run_native_cycle.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tg_fastpay.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tg_join_bot.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tg_manager_cli.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tg_stats.py*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\selfie.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\package.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Run.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Run-Console.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Stop.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Update.bat"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\Update.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\HOW_TO_RUN_ON_WINDOWS.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Stop {#MyAppName}"; Filename: "{app}\Stop.bat"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: shellexec postinstall skipifsilent
