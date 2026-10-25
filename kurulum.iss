; Inno Setup (ücretsiz) kurulum tarifi. GitHub Actions bunu her sürümde otomatik derler.
; Elle derlemek için: önce exe_olustur_windows.bat, sonra  iscc /DMyAppVersion=0.3.0 kurulum.iss
#ifndef MyAppVersion
  #define MyAppVersion "0.3.0"
#endif

[Setup]
; AppId değişmemeli: güncellemeler aynı kurulumun üstüne yazılır
AppId={{6E3F2B8A-4C1D-4E7B-9A55-2D8F0C3B7A11}
AppName=PromptVideo Stüdyo
AppVersion={#MyAppVersion}
AppPublisher=emrey5
AppPublisherURL=https://github.com/emrey5/INTOTHEDARKROOM
DefaultDirName={localappdata}\Programs\PromptVideo
PrivilegesRequired=lowest
DefaultGroupName=PromptVideo
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=PromptVideo-{#MyAppVersion}-Kurulum
SetupIconFile=promptvideo\assets\icon.ico
UninstallDisplayIcon={app}\PromptVideo.exe
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Ek simgeler:"

[Files]
Source: "dist\PromptVideo\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[InstallDelete]
; eski sürümden kalan kitaplık dosyaları yenileriyle karışmasın
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\PromptVideo Stüdyo"; Filename: "{app}\PromptVideo.exe"
Name: "{autodesktop}\PromptVideo Stüdyo"; Filename: "{app}\PromptVideo.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PromptVideo.exe"; Description: "PromptVideo Stüdyo'yu başlat"; Flags: nowait postinstall
