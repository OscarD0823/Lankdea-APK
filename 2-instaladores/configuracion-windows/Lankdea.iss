; El AppId y la ruta de datos permanecen estables entre versiones.
#ifndef AppVersion
  #error AppVersion es obligatorio
#endif
#ifndef SourceExe
  #error SourceExe es obligatorio
#endif
#ifndef OutputPath
  #error OutputPath es obligatorio
#endif

[Setup]
AppId={{B1ACDE32-A2AA-4E20-A7F2-D44B387A1392}
AppName=Lankdea Local
AppVersion={#AppVersion}
AppPublisher=OscarD0823
AppPublisherURL=https://github.com/OscarD0823
AppSupportURL=https://github.com/OscarD0823/Lankdea-APK
AppUpdatesURL=https://github.com/OscarD0823/Lankdea-APK/releases
LicenseFile={#LicensePath}
DefaultDirName={localappdata}\Programs\Lankdea
DefaultGroupName=Lankdea
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputPath}
OutputBaseFilename=Lankdea-{#AppVersion}-Instalador-Windows-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\Lankdea-PC.exe
SetupLogging=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#LicensePath}"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "{#NoticesPath}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Lankdea"; Filename: "{app}\Lankdea-PC.exe"
Name: "{userdesktop}\Lankdea"; Filename: "{app}\Lankdea-PC.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Lankdea-PC.exe"; Description: "Abrir Lankdea"; Flags: nowait postinstall skipifsilent

; No hay UninstallDelete: jamás borrar %APPDATA%\lankdea ni el cofre.
