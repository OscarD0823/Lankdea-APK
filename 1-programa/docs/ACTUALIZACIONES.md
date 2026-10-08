# Actualizaciones y entrega de Lankdea Local

## Decisión respecto a Fortuna Real

Se conserva el enfoque de una entrega numerada, verificable y fácil de copiar.
Fortuna Real usa Tauri; Lankdea usa Python/Kivy, por lo que no puede utilizar su
plugin actualizador ni su clave privada. Lankdea no reutiliza claves de otros proyectos.

Ahora cada push genera las apps y un ZIP; una etiqueta de versión publica una
entrega oficial si la APK está firmada para distribución. El instalador Windows
reemplaza solo el programa y conserva su AppId, la ruta de instalación y la carpeta
de datos de Lankdea. La app permite comprobar versiones y abrir Releases, pero
**no descarga ni ejecuta código automáticamente**. SHA-256 detecta corrupción,
no sustituye una firma de editor. No se afirma tener la firma de actualización de Tauri.

## Identidad y datos que deben conservarse

- Android: paquete `app.lankdea.lankdealocal`, misma clave privada de firma y
  `versionCode` creciente. Buildozer/python-for-android lo deriva de la versión.
- Windows: AppId `B1ACDE32-A2AA-4E20-A7F2-D44B387A1392`, programa en
  `%LOCALAPPDATA%/Programs/Lankdea`, mismo usuario.
- Cofre: `lankdea_vault_v2.json` en la carpeta de datos habitual de Kivy.
  El formato cifrado no cambia; se conserva contraseña, registros y TOTP.
- Archivos 3.5: conserva también `lankdea_vault_v2.json.files/`. Sus bloques
  están cifrados y sus llaves solo viven dentro del cofre. Un JSON solo no es
  un respaldo completo si se han guardado fotos, videos o documentos.
- Los cofres viejos pueden contener preferencias nube; se ignoran al normalizar.
  No se borran archivos ni bases remotas. Lo que solo exista en Firestore debe
  recuperarse primero usando la versión anterior.

Android exige la misma firma para actualizar una aplicación y rechaza versiones
inferiores: [firma Android](https://developer.android.com/studio/publish/app-signing),
[versionado](https://developer.android.com/studio/publish/versioning).
El AppId de Inno Setup identifica la instalación:
[documentación de Inno Setup](https://jrsoftware.org/ishelp/topic_setup_appid.htm).

## Firma Android y publicación protegida

Las APK históricas 3.1.1 se compilaron en modo debug. No se presupone que exista
la clave privada de aquella compilación, y no se rota ni se sube una clave sin
decisión del propietario. Una clave distinta impide actualizar esa instalación
directamente. Nunca aconsejar desinstalar sin haber respaldado y verificado el cofre.

Para una línea de distribución mantenible, conserva una clave Android de publicación
y su copia de seguridad privada. El workflow admite estos secretos únicamente en
una compilación iniciada por una etiqueta `v*` y dentro del entorno protegido de
GitHub `android-release`:

- `ANDROID_KEYSTORE_BASE64`: contenido del keystore codificado en base64.
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

La variable del entorno `ANDROID_CERTIFICATE_SHA256` contiene la huella pública
del certificado autorizado. No es un secreto. El verificador rechaza una APK
firmada con otro certificado, aunque declare el canal release.

Configurarlos requiere autorización del propietario. Deben guardarse como secretos
del entorno, no como secretos disponibles a trabajos de rama. Protege ese entorno
con revisores autorizados y restringe las ramas/etiquetas de despliegue a las etiquetas
de publicación. No están incluidos en código, ZIP, caché ni artefactos. El build
release no restaura ni guarda caché. El keystore temporal existe solo durante la
compilación firmada en el runner y se elimina al terminar ese paso. Buildozer usa
las variables `P4A_RELEASE_*`. El certificado se verifica con `apksigner verify`.

Cada push de rama genera siempre una APK debug identificada como PRUEBAS y ese
trabajo no referencia `secrets.*`. Las acciones de terceros están fijadas por un
hash de commit para evitar que una etiqueta mutable cambie el código ejecutado.

Sin esos secrets se genera un ZIP **PRUEBAS**, con aviso explícito; no se publica
como Release. Una etiqueta oficial falla si falta la firma, antes de compilar.
El EXE no tiene certificado Authenticode; Windows puede avisar de editor desconocido.

Para mantener toda clave en tu PC: compila Android release en un entorno Linux
local configurado con la misma clave y genera `android-build.json` mediante
`python -m scripts.record_android`; compila Windows en el mismo commit y luego
ejecuta `python -m scripts.create_package --require-release`. No mezcles binarios
sin sus recibos de compilación. La publicación del ZIP puede hacerse con `gh release`.

## Flujo de publicación

1. Actualiza las tres versiones y ejecuta `python -m pytest -q`.
2. Haz commit y push. Se compilan las apps desde ese commit.
3. Descarga `Lankdea-Paquete-Completo` o abre
   `2-instaladores/Descargar paquete Lankdea.cmd` desde la raíz del repositorio.
4. Revisa instalación limpia, actualización con datos y sincronización con un
   Android físico. Un build exitoso no sustituye esas pruebas.
5. Con firma estable y pruebas aprobadas, sube `v<versión>`. El workflow verifica
   que la etiqueta coincida; un revisor debe aprobar manualmente `android-release`.
   Crea un Release con ZIP, EXE y APK sin reemplazar otro existente.

Cada commit es una compilación, no necesariamente una nueva versión publicada.
Para que la app detecte una actualización hay que aumentar la versión y publicar
su ZIP oficial. No se incrementa silenciosamente la versión del código.

## Contenido y verificación

El empaquetador acepta solo instalador, APK, manual, LEEME, licencias y metadatos. Verifica
tamaño, SHA-256, plataforma, versión y commit de ambos recibos. Un archivo faltante,
antiguo, mezclado o alterado impide crear el ZIP. Después relee el ZIP completo,
valida CRC y huellas y rechaza contenido extra o rutas externas.

```powershell
python -m scripts.create_package --verify ruta/al/paquete.zip
```

Se distribuye el ZIP, no el ZIP de código fuente que GitHub genera por defecto.
Los artefactos de Actions caducan a los 30 días; Releases son la vía de distribución
duradera. Este proyecto se distribuye mediante un repositorio público; cualquiera
puede descargar las entregas publicadas sin iniciar sesión. El código original usa
MIT y los recursos externos conservan sus licencias.
