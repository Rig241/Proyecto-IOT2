#!/usr/bin/env python3
"""Crea dos cuentas MQTT nuevas y la configuración local; no toca el broker anterior."""
import argparse
import base64
import getpass
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def encode(value):
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actualizar", action="store_true", help="Cambiar credenciales después de docker compose down")
    args = parser.parse_args()
    os.chdir(ROOT)
    if not shutil.which("docker"):
        raise SystemExit("No se encontró Docker. Instala Docker Engine y el complemento Compose antes de continuar.")
    for cmd in (["docker", "compose", "version"], ["docker", "info"]):
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode:
            raise SystemExit("Docker/Compose no está disponible para este usuario. Comprueba docker info y docker compose version.")
    env_path = ROOT / ".env"
    if env_path.exists() and not args.actualizar:
        raise SystemExit("Ya existe .env. Para cambiar cuentas: docker compose down y python3 scripts/configurar.py --actualizar")
    running = subprocess.run(
        ["docker", "compose", "ps", "--status", "running", "-q"], capture_output=True, text=True, check=True
    )
    if running.stdout.strip():
        raise SystemExit("Primero detén este proyecto con docker compose down. No uses down -v.")
    print("Se crearán cuentas exclusivas de este proyecto, sin modificar el Mosquitto anterior.")
    print("Usuario de la ESP32: IoTProyecto. Conserva esta contraseña para programar la ESP32.")
    password = getpass.getpass("Contraseña MQTT para IoTProyecto (mínimo 8 caracteres): ")
    if len(password) < 8 or any(c in password for c in "\r\n\x00"):
        raise SystemExit("Utiliza al menos 8 caracteres y no incluyas saltos de línea.")
    if password != getpass.getpass("Repite la contraseña: "):
        raise SystemExit("Las contraseñas no coinciden; no se hicieron cambios.")
    bridge_password = secrets.token_urlsafe(32)
    result = subprocess.run(
        ["docker", "compose", "--profile", "herramientas", "run", "--rm", "--no-deps", "-T", "credenciales"],
        input=encode(password) + "\n" + encode(bridge_password) + "\n", text=True,
    )
    if result.returncode:
        raise SystemExit("No se pudieron preparar las cuentas. Revisa el error de Docker y vuelve a ejecutar el configurador.")
    # Conserva ajustes de puerto/red al cambiar contraseñas.
    settings = (env_path if env_path.exists() else ROOT / ".env.example").read_text(encoding="utf-8")
    lines = [line for line in settings.splitlines() if not line.startswith("MQTT_PASSWORD_B64=")]
    lines.append("MQTT_PASSWORD_B64=" + encode(bridge_password))
    fd, temp_path = tempfile.mkstemp(dir=ROOT, prefix=".env-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write("\n".join(lines) + "\n")
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, env_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    print("Listo. La cuenta dashboard tiene una contraseña aleatoria guardada en .env.")
    print("Siguiente: docker compose config --quiet y docker compose up -d --build")


if __name__ == "__main__":
    main()
