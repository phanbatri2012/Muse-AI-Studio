#define MyAppName "Muse AI Studio"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "Muse AI Studio"
#define MyAppExeName "Muse AI Studio.exe"
#define VCRedistExeName "VC_redist.x64.exe"
#define DistRoot AddBackslash(SourcePath) + "..\\..\\dist\\Muse AI Studio"
#define PrereqRoot AddBackslash(SourcePath) + "..\\..\\build-assets\\windows\\prereqs"
#define AppIconFile AddBackslash(SourcePath) + "..\\..\\app_icon.ico"

[Setup]
AppId={{EDB31FBC-CC82-4DEB-BF18-6349F465AF0E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile={#AppIconFile}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableDirPage=no
DisableProgramGroupPage=yes
OutputDir=..\..\dist-installer
OutputBaseFilename=Muse_AI_Studio_Setup
SetupLogging=yes
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng ngoài màn hình Desktop (Create Desktop Shortcut)"; GroupDescription: "Tùy chọn bổ sung:"

[Dirs]
Name: "{localappdata}\{#MyAppName}"; Flags: uninsneveruninstall

[Files]
Source: "{#DistRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PrereqRoot}\{#VCRedistExeName}"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; AppUserModelID: "Muse.AI.Studio.App"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; AppUserModelID: "Muse.AI.Studio.App"; Tasks: desktopicon

[Run]
Filename: "{tmp}\{#VCRedistExeName}"; Parameters: "/install /quiet /norestart"; StatusMsg: "Đang cài đặt thư viện Microsoft Visual C++ Runtime..."; Flags: waituntilterminated runhidden; Check: NeedsVCRedist
Filename: "{app}\{#MyAppExeName}"; Description: "Khởi chạy {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function IsVCRedistInstalled(const RootKey: Integer; const SubKey: string): Boolean;
var
  Installed: Cardinal;
begin
  Result :=
    RegQueryDWordValue(RootKey, SubKey, 'Installed', Installed) and
    (Installed = 1);
end;

function NeedsVCRedist(): Boolean;
begin
  Result := not (
    IsVCRedistInstalled(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64') or
    IsVCRedistInstalled(HKLM64, 'SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64') or
    IsVCRedistInstalled(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64') or
    IsVCRedistInstalled(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64')
  );
end;

procedure SHChangeNotify(wEventId: Integer; uFlags: Cardinal; dwItem1, dwItem2: Integer);
  external 'SHChangeNotify@shell32.dll stdcall';

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    try
      SHChangeNotify($08000000, $0000, 0, 0);
    except
    end;
  end;
end;
