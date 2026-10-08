# 2. Instaladores

Esta carpeta reúne lo relacionado con las entregas de Lankdea:

- `configuracion-windows/`: receta de Inno Setup para crear el instalador `.exe`.
- `historicos/`: binarios antiguos conservados solo como referencia.
- `windows/` y `android/`: salidas verificadas de una compilación local o de CI.
- `ci-<commit>-<ejecución>/`: paquete descargado desde GitHub Actions.

Para obtener el paquete actual, abre `Descargar paquete Lankdea.cmd`. El script
comprueba que el repositorio esté limpio, que el commit local coincida con GitHub
y que Windows y Android procedan de la misma ejecución. Después descarga el ZIP
completo sin sobrescribir una entrega anterior.

Los directorios y ZIP generados no se guardan en Git: GitHub Actions los publica
como artefactos descargables. Los archivos históricos no representan la versión
3.5 actual.
