# Validación de la versión local

Fecha: 20 de octubre de 2026.

## Verificaciones realizadas

- Compose aceptó `compose.yaml` sin errores de configuración. Se verificaron los puertos 1883
  y 8080 y que el puente no publica su puerto 8765 al anfitrión.
- Los manifiestos oficiales de las tres imágenes seleccionadas incluyen `linux/amd64` y `linux/arm64`.
- Se comprobó la sintaxis de los archivos Python, JavaScript y del inicializador de cuentas.
- Las pruebas del contrato JSON aceptaron las cuatro magnitudes numéricas y rechazaron mensajes
  incompletos, texto, booleanos, números no finitos y mensajes demasiado grandes.
- Se ejecutó Mosquitto 2.1.2 real con autenticación y las reglas ACL del proyecto. Las lecturas
  permitidas llegaron al puente; las publicaciones de la cuenta de lectura fueron rechazadas.
  También se comprobó el rechazo de credenciales incorrectas.
- Se verificó que una lectura retenida anterior no activa el indicador de recepción reciente.
- Se comprobó MQTT → Paho → aiohttp/WebSocket → Nginx 1.28.0 → navegador Chromium.
- En el navegador se verificaron las cuatro tarjetas, las cinco gráficas, el límite de 60 puntos,
  la caducidad de lecturas, la reconexión tras reiniciar Mosquitto y la última lectura al recargar.
- Se verificó la visualización en 1440 px y 390 px, sin desbordamiento horizontal en móvil,
  sin errores JavaScript y sin peticiones a CDN u otros servidores externos.
- La licencia y el archivo Chart.js 4.5.1 se obtuvieron del paquete oficial de npm; la descarga
  se verificó contra el valor de integridad del registro.

## Límites de estas pruebas

El entorno de preparación no dispone de un motor Docker. Se validó Compose con su herramienta
oficial, y se probaron los binarios de Mosquitto/Nginx de las imágenes seleccionadas fuera de
contenedores, con rutas y puertos adaptados al entorno de pruebas. El puente se ejecutó con
Python 3.12 y las versiones de Paho/aiohttp indicadas; su imagen utiliza Python 3.13.

No se afirma haber ejecutado `docker compose up` en Ubuntu ni en la Raspberry del usuario.
La construcción completa, el inicializador de cuentas dentro de Docker, los permisos de los
volúmenes y el arranque automático deben comprobarse allí con los pasos de `LEEME.md`.

Tampoco se han conectado el Arduino, la ESP32 ni sensores reales. La prueba incluida publica
valores fijos mediante MQTT; aún falta comprobar la entrada por la red desde un dispositivo
externo y la calidad de las mediciones físicas.

## Repetir las pruebas del contrato de datos

Opcional, desde la carpeta del proyecto y con Python 3.10 o posterior:

```bash
python3 -m venv .venv
.venv/bin/pip install -r bridge/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

La comprobación práctica del sistema montado se realiza con el dashboard abierto y
`python3 scripts/publicar_prueba.py`, como indica la guía.
