#!/usr/bin/env python3
"""Envía cinco lecturas fijas de prueba, únicamente cuando se ejecuta este script."""
import base64
import getpass
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SHELL = '''
set -eu
IFS= read -r encoded
IFS= read -r payload
password=$(printf '%s' "$encoded" | base64 -d)
mosquitto_pub -h 127.0.0.1 -p 1883 -u IoTProyecto -P "$password" \
  -t iot/monitoreo/mediciones -q 1 -m "$payload"
'''


def main():
    password = getpass.getpass("Contraseña MQTT de IoTProyecto: ")
    encoded = base64.b64encode(password.encode()).decode()
    data = {"voltaje": 220.5, "corriente": 1.23, "resistencia": 179.3, "fase": 45.2}
    print("Publicando 5 lecturas de PRUEBA, separadas por un segundo. No son mediciones reales.")
    for _ in range(5):
        subprocess.run(
            ["docker", "compose", "exec", "-T", "mosquitto", "sh", "-c", SHELL],
            cwd=ROOT, input=encoded + "\n" + json.dumps(data) + "\n", text=True, check=True,
        )
        time.sleep(1)
    print("Prueba terminada. Tras unos 10 segundos sin nuevas lecturas, el panel indicará datos no recientes.")


if __name__ == "__main__":
    main()
