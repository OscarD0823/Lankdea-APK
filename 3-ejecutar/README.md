# 3. Ejecutar

En Windows, haz doble clic en `Ejecutar Lankdea.cmd`.

La primera vez, el iniciador:

1. localiza Python 3;
2. crea `1-programa/.venv`;
3. instala Lankdea y su interfaz en ese entorno aislado;
4. abre el cofre.

Las ejecuciones siguientes reutilizan ese entorno. Si cambian las dependencias,
abre PowerShell en esta carpeta y ejecuta:

```powershell
.\ejecutar-lankdea.ps1 -ActualizarDependencias
```

Este acceso es para desarrollo. Para un equipo de uso normal, instala el `.exe`
generado desde GitHub Actions, pues funciona sin preparar Python.
