# Seguridad

Lankdea cifra el cofre antes de escribirlo en disco o sincronizarlo directamente
con otro dispositivo. No utiliza Firebase ni Firestore.

- Cifrado autenticado AES-256-GCM y scrypt con sal aleatoria.
- La contraseña maestra no se escribe en disco.
- Los parámetros scrypt, Base64 y tamaños se validan antes de reservar memoria o descifrar.
- Contraseñas ocultas al listar y editar; Android marca clips sensibles y la limpieza
  del portapapeles ocurre a los 15 segundos por defecto.
- Bloqueo automático después de cinco minutos sin actividad.
- Android usa almacenamiento privado, desactiva el respaldo automático del sistema
  y bloquea capturas y vistas recientes mientras la app está abierta.
- El servidor local existe solo mientras el cofre del PC está abierto y el enlace habilitado.
- El QR de Authenticator se renderiza en memoria y su secreto no se guarda como imagen.

## Sincronización directa

HTTP local transporta un sobre AES-256-GCM. Las solicitudes y respuestas usan
HMAC-SHA256 enlazado al método, ruta, estado, cuerpo, marcas de tiempo y nonces
contra repetición. El código de enlace es aleatorio de 80 bits. Las entradas tienen
límites estrictos, el servidor limita handlers simultáneos y el descubrimiento no
anuncia el nombre del equipo. Puerto 8765.
Esto no oculta tamaños, horarios ni el nombre técnico del servicio; un atacante
todavía puede interrumpir la red. Usa Wi-Fi privada, no expongas ese puerto en el
router y regenera el código si deja de ser secreto. USB requiere ADB autorizado.
PC y Android deben ejecutar la versión 3.5 o posterior para usar este protocolo.

## Actualizaciones

La consulta a GitHub es voluntaria, no incluye información del cofre ni tokens.
No se descargan o ejecutan instaladores automáticamente. Un 404 de un repositorio
privado no se presenta como falta de Internet. Las APK debug están marcadas como
pruebas y no se publican como versiones oficiales. La clave Android debe mantenerse
estable para actualizar instalaciones existentes. Ver
[ACTUALIZACIONES.md](../1-programa/docs/ACTUALIZACIONES.md).

Los ZIP contienen una lista explícita de archivos, no una copia del directorio de
trabajo. Nunca se incluyen cofres, credenciales ni claves privadas. Los builds de
rama generan APK debug sin acceso a secretos; una APK release solo se compila desde
una etiqueta y el entorno protegido `android-release`. Las acciones externas están
fijadas por hash de commit. SHA-256 detecta corrupción pero no autentica al autor.
Windows no lleva certificado Authenticode.

El código original es público bajo MIT. Los paquetes de descarga no incluyen
cofres, credenciales ni la firma privada Android. La protección de datos depende
de la contraseña personal, scrypt y AES-GCM, no de ocultar el código.

Al cambiar la contraseña maestra, el archivo principal y su copia automática se
recifran y verifican con la nueva contraseña antes de informar éxito. Los respaldos
exportados manualmente conservan la contraseña con la que fueron creados.

La verificación de ZIP inspecciona metadatos y limita entradas, tamaño expandido y
relación de compresión antes de descomprimir contenido no confiable.

## Límites

Si olvidas la contraseña maestra no existe recuperación. Los dos dispositivos
deben usar la misma contraseña para fusionar registros. La contraseña se deriva con
scrypt y hace que el texto cifrado solo cobre sentido al descifrarlo correctamente;
AES-GCM rechaza claves o contenidos incorrectos en lugar de mostrar datos falsos.
TOTP es un segundo paso dentro de la aplicación: un código de seis dígitos tiene
solo un millón de posibilidades y no puede sustituir una contraseña fuerte como
clave de cifrado local. Tampoco protege contra un dispositivo infectado. Conserva
respaldos cifrados y verifica que puedas abrirlos.

Al migrar desde Lankdea 2 se verifica primero el cofre moderno, se crea un respaldo
AES-256-GCM y se retiran el original y las copias antiguas que incluían su propia
clave de descifrado. Consulta [MIGRATION.md](../1-programa/docs/MIGRATION.md).

“Retirar” significa que esas rutas visibles se sustituyen por marcadores. No es una
promesa de borrado forense: SSD, sistemas copy-on-write, snapshots, sincronización y
backups pueden conservar versiones antiguas. Después de migrar, limpia esas copias
según tu plataforma y rota las credenciales importantes.

La retirada de la nube no elimina datos remotos ni convierte la antigua aplicación
Android Firebase en la local: eran paquetes diferentes. Recupera los datos primero
con la versión anterior si solo están en la nube.
