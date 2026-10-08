# Migración desde Lankdea 2

La versión anterior guardaba `lankdea_cofre.json`. Lankdea 3 detecta ese archivo en la carpeta de datos y muestra **Migrar cofre anterior**.

1. Escribe una nueva contraseña maestra de al menos 12 caracteres.
2. Confírmala.
3. Pulsa **Migrar cofre anterior**.

La migración crea y vuelve a abrir `lankdea_vault_v2.json` antes de retirar el formato
anterior. Ese formato incluía en el mismo archivo la clave que permitía descifrarlo,
por lo que no es seguro conservarlo como respaldo. Lankdea 3.3:

- crea `lankdea_cofre.json.legacy.encrypted.bak`, protegido con la nueva contraseña
  y el formato moderno AES-256-GCM;
- reemplaza `lankdea_cofre.json` y cualquier copia `.legacy.bak` expuesta con un
  marcador que no contiene registros ni claves.

Desde 3.5 la copia automática moderna se guarda dentro de la carpeta del cofre,
incluso si el archivo antiguo se importó desde otra ubicación. Su nombre queda
registrado dentro de las preferencias cifradas para recifrarla al cambiar la
contraseña, conservando su instantánea histórica. Las copias externas previas a
esta versión y los respaldos manuales conservan la contraseña con que se crearon.
Si una copia automática antigua ya usa otra contraseña, la rotación se detiene
antes de modificar archivos; hay que recuperar/verificar esa copia primero.

Conserva el respaldo cifrado y verifica que puedas abrir el cofre nuevo. Si tenías
una copia manual del archivo antiguo fuera de la carpeta de Lankdea, trátala como
datos en texto recuperable y elimínala de forma segura después de validar la migración.

La sustitución atómica elimina el contenido de las rutas visibles, pero no puede
prometer borrado forense de bloques antiguos, snapshots, historial de nube o copias
en otros dispositivos. Si el cofre anterior contenía secretos reales, haz la
migración en un disco cifrado, elimina versiones históricas según tu plataforma y
rota después las contraseñas más sensibles.
