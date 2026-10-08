"""Copia fuente AES-256-GCM. Es independiente de las claves de los cofres.

No oculta un EXE/APK en ejecución. La contraseña se pide al usar la herramienta
y no se incluye en el archivo, en el programa ni en el repositorio.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"LANKDEA-SOURCE-AESGCM-1\n"
MAX_ARCHIVE = 256 * 1024 * 1024


def derive_key(password: str, salt: bytes) -> bytes:
    if len(password) < 8:
        raise ValueError("Usa una contraseña de al menos 8 caracteres.")
    return Scrypt(salt=salt, length=32, n=32768, r=8, p=1).derive(password.encode("utf-8"))


def encrypt_source(repository: Path, destination: Path, password: str) -> None:
    repository = Path(repository).resolve()
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=repository).decode("utf-8").split("\0")
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            if not name:
                continue
            path = repository / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("El código contiene un archivo especial o ausente.")
            archive.write(path, name)
    content = buffer.getvalue()
    if len(content) > MAX_ARCHIVE:
        raise ValueError("La copia fuente supera el límite de 256 MiB.")
    salt, nonce = os.urandom(16), os.urandom(12)
    header = MAGIC + json.dumps({"salt": base64.b64encode(salt).decode("ascii"),
                                "nonce": base64.b64encode(nonce).decode("ascii")}, separators=(",", ":")).encode("ascii") + b"\n"
    encrypted = AESGCM(derive_key(password, salt)).encrypt(nonce, content, header)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(header + encrypted)


def decrypt_source(source: Path, destination: Path, password: str) -> None:
    if destination.exists():
        raise ValueError("Elige una carpeta nueva; nunca se sobrescribe el código existente.")
    with source.open("rb") as stream:
        magic = stream.readline(len(MAGIC) + 1)
        line = stream.readline(1025)
        encrypted = stream.read(MAX_ARCHIVE + 17)
    if magic != MAGIC or len(line) > 1024 or not line.endswith(b"\n") or len(encrypted) > MAX_ARCHIVE + 16:
        raise ValueError("Formato de copia fuente inválido.")
    metadata = json.loads(line)
    salt = base64.b64decode(metadata["salt"], validate=True)
    nonce = base64.b64decode(metadata["nonce"], validate=True)
    if len(salt) != 16 or len(nonce) != 12:
        raise ValueError("Formato de copia fuente inválido.")
    content = AESGCM(derive_key(password, salt)).decrypt(nonce, encrypted, magic + line)
    with zipfile.ZipFile(BytesIO(content)) as archive:
        infos = archive.infolist()
        if len(infos) > 2000 or sum(i.file_size for i in infos) > MAX_ARCHIVE:
            raise ValueError("La copia fuente expandida es demasiado grande.")
        if len({i.filename.casefold() for i in infos}) != len(infos):
            raise ValueError("Hay nombres duplicados en la copia fuente.")
        for info in infos:
            relative = PurePosixPath(info.filename)
            if relative.is_absolute() or any(p in ("", ".", "..") or ":" in p or "\\" in p or p.endswith((".", " ")) for p in relative.parts):
                raise ValueError("Hay una ruta insegura en la copia fuente.")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("La copia fuente contiene un enlace simbólico.")
        # Autenticidad y lista de rutas se comprobaron antes de crear la carpeta.
        destination.mkdir(parents=True, exist_ok=False)
        for info in infos:
            target = destination.joinpath(*PurePosixPath(info.filename).parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as incoming, target.open("xb") as outgoing:
                total = 0
                while block := incoming.read(1024 * 1024):
                    total += len(block)
                    if total > info.file_size:
                        raise ValueError("Entrada expandida inválida.")
                    outgoing.write(block)


def main():
    if len(sys.argv) == 1:
        print("Lankdea: descifrar copia de desarrollo (no abre cofres personales).")
        source = Path(input("Archivo .lksource: ").strip().strip('"'))
        destination = Path(input("Carpeta NUEVA de destino: ").strip().strip('"'))
        password = getpass.getpass("Contraseña de la copia: ")
        try:
            decrypt_source(source, destination, password)
            print("Código descifrado en", destination)
        except Exception:
            print("No se pudo descifrar. Revisa la contraseña, el archivo y el destino.")
        input("Enter para cerrar.")
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("encrypt", "decrypt"))
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--key-stdin", action="store_true", help="Recibir contraseña por entrada estándar; no por argumentos")
    args = parser.parse_args()
    password = sys.stdin.readline().rstrip("\r\n") if args.key_stdin else getpass.getpass("Contraseña de la copia: ")
    if args.mode == "encrypt":
        encrypt_source(args.source, args.destination, password)
    else:
        decrypt_source(args.source, args.destination, password)
    print("Operación completada:", args.destination)


if __name__ == "__main__":
    main()
