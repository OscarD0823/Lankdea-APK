# Historial de cambios

## 3.6.0

- Cofre gótico de alto detalle coherente con el icono: metal oscuro, cadenas,
  cristales violetas y herrajes dorados. Atlas transparente cargado una sola vez.
- Transición ilustrada abierto/cerrado, aura y profundidad visual sin bucle permanente;
  sustituye el cofre geométrico simple. No es un modelo 3D articulado.
- Cofre más grande al entrar, paneles ornamentales y controles violetas con oro;
  navegación adaptable y formularios desplazables.
- Código y descargas públicos bajo MIT. Licencia y atribuciones incluidas en EXE,
  APK y ZIP; no se distribuyen cofres ni credenciales ni llaves privadas.
- Descargas individuales de Windows y Android además del ZIP conjunto.

## 3.5.0

- Cofre geométrico en perspectiva con tapa articulada a 103° e iluminación interior,
  sin motor 3D adicional ni bucle permanente cuando está quieto.
- Archivos cifrados por bloques: imágenes, videos y documentos; límites de tamaño,
  autenticación por bloque, exportación explícita y sin temporales legibles.
- Respaldos completos `.lankdea` y restauración con listas de rutas exactas, tamaños
  acotados y comprobación AES-GCM; selector de documentos nativo en Android.
- Sincronización local v3 de metadatos y bloques, bidireccional y reanudable. Exige
  3.5 en ambos dispositivos para no perder metadatos con clientes anteriores.
- Apertura de cofre en un hilo de trabajo para mantener fluida la animación.
- Nueva entrada cinematográfica de cofre con HUD, escaneo, progreso, sonido y
  adaptación a pantallas pequeñas; puede omitirse tocando la pantalla.
- Paleta interna renovada en cian, azul profundo y oro, inspirada en la claridad
  visual de Caja Fantasma sin reutilizar arte ni marcas del juego.
- Selector con 12 idiomas y preferencia guardada dentro del cofre cifrado.
- La rotación recifra y verifica `.bak` y copias automáticas de migración,
  conservando sus instantáneas; registra su propiedad dentro del cofre cifrado.
  Pruebas de errores de escritura y rollback; bloqueo ante fallos de recuperación.
- El servidor PC limita conexiones simultáneas y rechaza cabeceras inválidas antes
  de leer un cuerpo.
- Android marca el portapapeles como sensible y la limpieza baja a 15 segundos.
- El verificador de paquetes impone límites de entradas, expansión y compresión.
- Se documenta que reemplazar archivos heredados no garantiza borrado forense en
  SSD, snapshots o copias externas.

## 3.4.0

- Bienvenida original de asistente futurista después de una autenticación correcta,
  con confirmación visual de identidad y audio completamente local.
- Control independiente en Configuración para activar o apagar el asistente al entrar;
  el interruptor general de sonidos sigue teniendo prioridad.
- Fondo adaptable basado en el arte oficial del cofre épico, tanto al iniciar sesión
  como durante el cierre, sin perder legibilidad en celular o escritorio.
- Acceso más claro y fluido con estados de relicario bloqueado, verificación de
  identidad, animación de apertura y transición al contenido.
- Autor `OscarD0823` visible en la aplicación, metadatos del paquete y el instalador.
- Atribución de la voz incluida junto al recurso; el audio no usa la red ni reproduce
  contraseñas, notas u otros datos del cofre.

## 3.3.0

- Repositorio reorganizado en `1-programa`, `2-instaladores` y `3-ejecutar`, con
  rutas de compilación verificadas y un iniciador sencillo para desarrollo en Windows.
- Contraseñas maestras nuevas de 12 o más caracteres y validación de claves débiles.
- Límites estrictos de scrypt, Base64 y tamaño para rechazar cofres manipulados sin
  agotar memoria, CPU o disco.
- Migración del formato antiguo sin conservar archivos que incluyan su propia clave:
  crea un respaldo AES-256-GCM verificable y retira las copias expuestas.
- QR de Authenticator generado únicamente en memoria; no queda una imagen con el
  secreto TOTP en el disco.
- Authenticator se mantiene como segundo factor y nunca como clave de cifrado de seis dígitos.
- Bloqueo automático tras cinco minutos de inactividad, campos de contraseña ocultos
  por defecto y protección de capturas de pantalla en Android.
- Sincronización local v2 con autenticación HMAC de solicitudes y respuestas, nonces
  contra repetición, límites de tamaño y respuestas de error sin información interna.
- Builds de rama siempre debug y sin secretos. La firma Android oficial queda aislada
  en etiquetas y en el entorno protegido `android-release`, con acciones fijadas por commit.
- Cofre 3D a pantalla completa al entrar y bloquear, con transición de escala,
  fundido y sonidos coordinados.
- Formularios centrados con ancho máximo, menús que cambian automáticamente entre
  una y seis columnas y cabecera compacta para vistas horizontales o de poca altura.
- Ejecutable Windows con bytecode optimizado; los paquetes siguen excluyendo fuentes,
  pruebas y depuración sin recurrir a código señuelo inseguro.

## 3.2.0

- Una sola edición local: retirados cliente, pantallas, reglas y compilación Firebase/Firestore.
- Conservación del formato cifrado y compatibilidad con cofres locales existentes.
- Actualizaciones consultadas voluntariamente sin enviar el cofre ni incrustar tokens.
- Instalador Windows por usuario con identidad estable y datos separados del programa.
- Cada push genera Windows, Android y un ZIP completo con manual offline y SHA-256.
- Validación de versión, commit, firma Android y huellas antes de mezclar artefactos.
- Publicaciones oficiales por etiqueta, bloqueadas cuando falta una firma Android estable.
- APK debug claramente identificada como PRUEBAS, sin prometer actualización in situ.

## 3.1.1

- Inicio de sesión guiado en dos pasos cuando Authenticator está activo.
- Entrada automática al completar un código TOTP válido de seis dígitos.
- Reintentos de código sin volver a escribir la contraseña, con límite de seguridad.
- Activación de Authenticator solo después de comprobar el primer código generado.
- Mejor navegación con foco automático y tecla Entrar en PC y celular.
- Caché Android completo en GitHub Actions para conservar SDK, NDK y Buildozer juntos.
- La compilación Firebase se omite limpiamente mientras no estén configuradas sus claves.
- PyInstaller usa un backend gráfico simulado durante el análisis en runners sin GPU.
- Cada artefacto Android publica una sola APK con un nombre estable y reconocible.

## 3.1.0

- Nuevo cofre 3D con estados abierto/cerrado y transición animada.
- Sonidos de apertura y cierre generados para la aplicación.
- Diseño adaptable validado en ventanas de PC y formato celular.
- Sincronización cifrada PC ↔ Android por Wi-Fi local.
- Reconexión automática por USB mediante ADB autorizado.
- Menú de enlace, detección del PC y sincronización automática cada 8 segundos.
- GitHub Actions para las dos APK y la aplicación de Windows.

## 3.0.0

- Dos ediciones desde el mismo código: Local y Firebase.
- Nuevo cifrado AES-256-GCM con scrypt.
- Sincronización por registro con marcas de eliminación y control de conflictos.
- Renovación automática del token de Firebase.
- Interfaz móvil primero y recursos visuales renovados.
- Contraseñas ocultas y limpieza automática del portapapeles.
- Migración segura desde el formato anterior sin borrar el original.
- GitHub Actions para pruebas y generación de dos APK.
