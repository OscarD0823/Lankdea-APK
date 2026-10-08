# 1. Programa

Esta es la carpeta de desarrollo de Lankdea Local.

Versión actual: **3.6.0** · Autor: **OscarD0823**

```text
1-programa/
├── assets/                 Imágenes 3D y sonidos del cofre
├── docs/                   Manual, cambios, migración y actualizaciones
├── lankdea/                Código principal de la aplicación
├── scripts/                Compilación y verificación de entregas
├── tests/                  Pruebas automáticas
├── buildozer.local.spec    Configuración Android local
├── main.py                 Punto de entrada
└── pyproject.toml          Dependencias y versión
```

Para iniciar desde esta carpeta:

```powershell
python -m pip install -e ".[desktop,dev]"
python main.py
```

Para verificar los cambios:

```powershell
python -m compileall -q main.py lankdea scripts
python -m pytest -q
```

Los procesos de compilación escriben sus entregas en `../2-instaladores`; nunca
incluyen el cofre, las contraseñas, notas ni claves privadas del usuario.

La bienvenida hablada se distribuye como un audio local opcional. Su procedencia y
licencia están documentadas en `assets/sounds/ASSISTANT_VOICE_NOTICE.txt`.

La interfaz 3.6 añade un cofre gótico detallado, marcos dorados, una entrada
cinematográfica original, diseño adaptable y
12 idiomas definidos en `lankdea/i18n.py`. La preferencia de idioma, igual que las
demás opciones, forma parte del documento cifrado.

`chest_3d.py` carga una vez el atlas transparente y anima los dos estados ilustrados
con luz y profundidad visual; no utiliza un modelo 3D articulado; `attachments.py` cifra archivos
por bloques AES-GCM, y `file_access.py` utiliza acceso explícito a archivos y
Storage Access Framework en Android. El protocolo local v3 transfiere bloques
autenticados y puede continuar tras una desconexión. Los respaldos `.lankdea`
incluyen los bloques cifrados, no solo el documento JSON.

El límite es 256 MiB por archivo, 128 archivos activos y 2 GiB almacenados. Los
originales y las copias exportadas están fuera del cifrado del cofre. El borrado de
un registro es lógico para sincronizarlo; no promete borrado forense del disco.

Código original bajo [MIT](../LICENSE), con recursos de terceros documentados en
[THIRD-PARTY-NOTICES.txt](../THIRD-PARTY-NOTICES.txt). El repositorio público no
contiene cofres ni credenciales de usuarios ni la firma privada Android.
