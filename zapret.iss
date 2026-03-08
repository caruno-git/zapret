;---------------------------------------------------
;  Zapret installer / updater (ProgramData by default)
;---------------------------------------------------
[Setup]
AppName=Zapret
AppVersion=16.1.0
AppId={{5C71C1DC-7627-4E57-9B1A-6B5D1F3A57F0}}
; ───────────────────────────────────────────────────────────────
DefaultDirName={code:GetInstallDir}
DisableDirPage=no
UsePreviousAppDir=yes
; ───────────────────────────────────────────────────────────────
PrivilegesRequired=admin
DefaultGroupName=Zapret
AllowNoIcons=yes
OutputDir=.
OutputBaseFilename=ZapretSetup
Compression=lzma2
SolidCompression=yes
SetupIconFile=zapret.ico
UninstallDisplayIcon={app}\Zapret.exe
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
;---------------------------------------------------

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "..\zapret\Zapret.exe";           DestDir: "{app}";      Flags: ignoreversion
Source: "..\zapret\bat\*";              DestDir: "{app}\bat"; Flags: recursesubdirs ignoreversion
Source: "..\zapret\bin\*";                DestDir: "{app}\bin";  Flags: recursesubdirs ignoreversion
Source: "..\zapret\exe\*";              DestDir: "{app}\exe"; Flags: recursesubdirs ignoreversion
Source: "..\zapret\json\*";              DestDir: "{app}\json"; Flags: recursesubdirs ignoreversion
Source: "..\zapret\ico\*";              DestDir: "{app}\ico"; Flags: recursesubdirs ignoreversion
Source: "..\zapret\lists\*";              DestDir: "{app}\lists"; Flags: recursesubdirs ignoreversion
Source: "..\zapret\sos\*";              DestDir: "{app}\sos"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Zapret";              Filename: "{app}\Zapret.exe"; WorkingDir: "{app}"
Name: "{group}\Удалить Zapret";      Filename: "{uninstallexe}";   IconFilename: "{app}\Zapret.exe"
Name: "{commondesktop}\Zapret";      Filename: "{app}\Zapret.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Создать ярлык на рабочем столе"; Flags: unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{commonappdata}\Zapret"

;──────────────────────────────────────────────
[Code]
{ 1.  КИЛЛИМ процессы ──────────────────────── }
procedure KillProcess(const ExeName: string);
var R: Integer;
begin
  Exec('taskkill.exe', '/IM ' + ExeName + ' /F', '',
       SW_HIDE, ewWaitUntilTerminated, R);
end;

{ 1a.  ОСТАНОВКА/УДАЛЕНИЕ СЛУЖБЫ WinDivert ─── }
procedure StopAndDeleteService(const ServiceName: string);
var R: Integer;
begin
  { Остановить службу }
  Exec('sc.exe', 'stop "' + ServiceName + '"', '',
       SW_HIDE, ewWaitUntilTerminated, R);

  { Удалить службу (если она уже удалена – игнорируем ошибку) }
  Exec('sc.exe', 'delete "' + ServiceName + '"', '',
       SW_HIDE, ewWaitUntilTerminated, R);
end;

function PrepareToInstall(var NeedsRestart: Boolean): string;
begin
  { 1) выгружаем ВСЕ драйверы WinDivert }
  StopAndDeleteService('WinDivert');
  StopAndDeleteService('WinDivert14'); 
  StopAndDeleteService('WinDivert1.4');
  StopAndDeleteService('WinDivert64');
  
  { 2) гасим процессы }
  KillProcess('winws.exe');
  KillProcess('Zapret.exe');

  Result := '';
end;

{ 2.  ДЕФОЛТНЫЙ ПУТЬ ────────────────────────── }
function GetInstallDir(Param: string): string;
begin
  { если есть предыдущая установка – Inno сам подставит её,
    иначе кладём в ProgramData }
  Result := ExpandConstant('{commonappdata}\Zapret');
end;

{ 3.  ПРОВЕРКА ПУТИ ──────────────────────────── }
function IsAsciiLetter(C: Char): Boolean;
begin
  Result := (C >= 'A') and (C <= 'Z') or (C >= 'a') and (C <= 'z');
end;

function IsAllowedChar(C: Char): Boolean;
begin
  Result := IsAsciiLetter(C) or (C = '\') or (C = ':');
end;

function CheckDirName(const Dir: string): Boolean;
var I: Integer;
begin
  for I := 1 to Length(Dir) do
    if not IsAllowedChar(Dir[I]) then
    begin
      Result := False;
      Exit;
    end;
  Result := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;                                { по умолчанию идём дальше }

  if CurPageID = wpSelectDir then                { страница выбора папки }
  begin
    if not CheckDirName(WizardDirValue) then
    begin
      MsgBox('Путь к папке установки может содержать только латинские буквы ' +
             'и символы "\" и ":". ' + #13#10 +
             'Без пробелов, цифр и специальных символов.',
             mbError, MB_OK);
      Result := False;                           { остаёмся на странице }
    end;
  end;
end;

{───────────────────────────────────────────────────────────
  4.  УДАЛЕНИЕ: гасим службы / процессы перед RemoveFiles
───────────────────────────────────────────────────────────}
procedure CurUninstallStepChanged(CurStep: TUninstallStep);
begin
  if CurStep = usUninstall then   { начинается собственно удаление }
  begin
    { а) останавливаем / удаляем WinDivert, если вдруг запущена }
    StopAndDeleteService('WinDivert');
    StopAndDeleteService('WinDivert14');
    StopAndDeleteService('WinDivert1.4');
    StopAndDeleteService('WinDivert64');

    { б) завершаем работающие процессы }
    KillProcess('winws.exe');
    KillProcess('Zapret.exe');
  end;
end;
