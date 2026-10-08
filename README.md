# Lankdea Local 3.6

Cofre cifrado para contraseñas, notas, imágenes, videos y documentos en Windows y Android. Esta edición funciona
sin Firebase ni Firestore: los datos permanecen en cada dispositivo y la
sincronización se realiza directamente por Wi-Fi privada o USB/ADB.

Autor: **OscarD0823**

![Cofre de Lankdea](1-programa/assets/cofre_atlas_gothic.png)

## Estructura del repositorio

```text
Lankdea-APK/
├── 1-programa/       Código, recursos, pruebas y documentación técnica
├── 2-instaladores/   Configuración, descarga de paquetes y binarios históricos
├── 3-ejecutar/       Inicio sencillo del programa desde el código fuente
├── .github/          Pruebas y compilación automática de GitHub Actions
├── LICENSE           Licencia MIT del código original
└── README.md         Esta guía
```

- [1-programa](1-programa/README.md) es la carpeta de desarrollo. Contiene la app,
  el cifrado, la interfaz, la sincronización, las imágenes, los sonidos y las pruebas.
- [2-instaladores](2-instaladores/README.md) recibe el instalador `.exe`, la APK y
  el ZIP completo generados para un mismo commit.
- [3-ejecutar](3-ejecutar/README.md) contiene un acceso para ejecutar la app en un
  PC de desarrollo. La primera ejecución crea su entorno de Python e instala las
  dependencias necesarias.

## Instalar la aplicación terminada

1. Abre [Descargas públicas / Releases](https://github.com/OscarD0823/Lankdea-APK/releases).
2. Descarga el ZIP completo de la versión publicada, o el EXE y la APK por separado.
   No necesitas una cuenta GitHub. Si todavía no hay Release, la publicación está pendiente;
   los artefactos de **Actions** son compilaciones de pruebas y requieren acceso a GitHub.
3. Extrae el ZIP. Allí encontrarás el instalador de Windows x64, la APK Android
   ARM64, el manual, el manifiesto y las huellas SHA-256.
4. En Windows, ejecuta `Lankdea-3.6.0-Instalador-Windows-x64.exe`.
5. En Android 8 o posterior, permite la instalación desde la fuente utilizada y
   abre `Lankdea-3.6.0-Android-arm64.apk`.

También puedes abrir [Descargar paquete Lankdea.cmd](2-instaladores/Descargar%20paquete%20Lankdea.cmd).
Necesita GitHub CLI autenticado y descarga únicamente el paquete construido desde
el mismo commit, dentro de `2-instaladores/ci-<commit>-<ejecución>/`.

Los archivos de `2-instaladores/historicos/` son versiones antiguas y no se deben
distribuir como si fueran la versión actual.

## Usar el cofre

La versión 3.6 presenta un cofre gótico detallado como el icono: metal oscuro,
cristales violetas, cadenas y bordes dorados. Su arte ilustrado en perspectiva usa
transiciones entre estados abierto/cerrado, luz y profundidad visual (no un modelo
3D articulado), marcos ornamentales, animación adaptable y
sonidos de apertura/cierre. La interfaz se reorganiza automáticamente para
escritorio, tablet o celular. Incluye los mismos 12 idiomas base usados por Caja
Fantasma: español, inglés, portugués, francés, alemán, italiano, polaco, turco,
ruso, japonés, coreano y chino simplificado, con fuente Noto CJK incluida.
La navegación principal está traducida; los formularios registrados sin traducción
secundaria usan inglés. Algunos avisos avanzados siguen en español.

Al abrir Lankdea por primera vez, crea una contraseña maestra larga y única. Esa
contraseña deriva la clave que cifra el cofre con AES-GCM; no se guarda y no puede
recuperarse si se olvida. Después puedes guardar contraseñas, notas y archivos, bloquear el
cofre y activar Authenticator como segundo paso.

Después de una autenticación correcta, Lankdea muestra y reproduce una bienvenida
breve de su asistente local. La voz incluida está en español y se silencia al elegir
otro idioma; la bienvenida visual usa español o inglés. Se puede apagar desde **Configuración**; la frase es un
recurso incluido en la aplicación y no utiliza la red ni lee el contenido del cofre.

El código temporal de seis dígitos permite completar el inicio cuando Authenticator
está activado, pero no reemplaza la contraseña maestra. Para enlazar PC y celular,
usa la misma contraseña maestra en ambos, abre los dos cofres, pulsa **PC + celular**
y escribe en Android el código mostrado por el PC. La sincronización funciona con
ambas aplicaciones abiertas en la misma red privada; por USB requiere Android
Platform-Tools, depuración USB y autorización explícita del computador.
Para transferir archivos, PC y celular deben usar **3.5 o posterior**: el protocolo
local v3 no se mezcla con versiones antiguas.

**Guardar archivo** importa una imagen, video o documento de hasta 256 MiB. Se
admiten 128 archivos activos y hasta 2 GiB de bloques cifrados por dispositivo.
La importación no elimina ni cifra el archivo original elegido: elimina esa copia
externa por tu cuenta solo después de comprobar el cofre y el respaldo.
**Exportar archivo** crea una copia legible explícita y advierte que esa copia ya
no está protegida por Lankdea. No se crean temporales en claro ni se abren archivos
automáticamente en apps externas.

**Respaldo** genera un archivo `.lankdea` que contiene el cofre y todos los bloques
cifrados; **Configuración → Restaurar respaldo** permite recuperar y combinar
registros usando la contraseña del respaldo. En Android se usa el selector del
sistema; por seguridad se debe desbloquear otra vez al volver del selector.

## Qué está cifrado

Contraseñas, notas, nombres de archivo, llaves de archivos, TOTP, preferencias y datos de enlace se guardan juntos dentro
de un sobre **AES-256-GCM**. La clave se deriva con **scrypt** de la contraseña que
elige cada persona; cada guardado usa sal y nonce aleatorios. La contraseña maestra
no se escribe en disco. El archivo principal, su copia automática, los respaldos
manuales y los sobres enviados entre PC y celular permanecen cifrados.
Cambiar la contraseña recifra las copias automáticas administradas dentro de la
carpeta del cofre. Los respaldos manuales y copias externas ya entregadas conservan
su contraseña original: vuelve a exportarlos si deseas retirar la clave anterior.
No se garantiza una transacción entre varios archivos ante un apagón o fallos
persistentes de disco; conserva un respaldo verificado antes de rotar la frase.
Las imágenes, videos y documentos se cifran por bloques de 2 MiB con AES-256-GCM
y una llave aleatoria por archivo; esa llave solo existe dentro de los metadatos
protegidos por la frase maestra. Cada bloque autentica identidad, posición y tamaño.
Los nombres originales y formatos tampoco se guardan en claro, aunque el tamaño
aproximado y la cantidad de bloques siguen siendo observables.

El código fuente se publica bajo [licencia MIT](LICENSE). Los recursos de terceros
mantienen sus propias licencias, incluidas en [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).
El programa no contiene una contraseña maestra universal: cada persona crea su propia
contraseña para proteger los datos. El código abierto no revela esa contraseña.

Al copiar un secreto se marca como sensible en Android cuando la plataforma lo
permite y se limpia a los 15 segundos. En Windows ningún programa puede impedir de
forma universal que otra aplicación de la misma sesión lea el portapapeles; úsalo
solo en equipos confiables.

El manual completo está en
[1-programa/docs/Manual-Lankdea.html](1-programa/docs/Manual-Lankdea.html).

## Ejecutar y desarrollar

La forma sencilla en Windows es abrir
[Ejecutar Lankdea.cmd](3-ejecutar/Ejecutar%20Lankdea.cmd). Para trabajar manualmente:

```powershell
cd 1-programa
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[desktop,dev]"
python main.py
python -m pytest -q
```

Para compilar el instalador de Windows se necesita Python 3.10+ e Inno Setup 6:

```powershell
cd 1-programa
python -m pip install -e ".[desktop,dev]" "pyinstaller>=6,<7"
python -m scripts.build_windows
```

Android se compila con Buildozer en Linux. Cada push ejecuta pruebas y genera los
artefactos de prueba de ambas plataformas. Una publicación oficial exige una
etiqueta `vX.Y.Z` y la firma Android estable dentro del entorno protegido
`android-release`; una APK debug no se presenta como actualización oficial.

Consulta [actualizaciones](1-programa/docs/ACTUALIZACIONES.md),
[migración](1-programa/docs/MIGRATION.md) y la
[política de seguridad](.github/SECURITY.md).
