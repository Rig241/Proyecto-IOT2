# Monitoreo eléctrico IoT — versión local

Preparado para pruebas en Ubuntu AMD64 y despliegue en Raspberry Pi 4 con Debian 13 ARM64.
Conserva el diseño del dashboard original y reemplaza sus datos aleatorios por mediciones MQTT.

## Recorrido de los datos

Sensores → Arduino Uno → ESP32 → Mosquitto → puente Python → dashboard.

En este paquete se implementa el tramo desde Mosquitto hasta el navegador. Los programas y conexiones
eléctricas del Arduino y la ESP32 se preparan aparte. No se requieren dispositivos USB ni acceso
privilegiado de los contenedores al hardware de la Raspberry.

| Servicio | Acceso |
|---|---|
| Mosquitto | Puerto TCP 1883 del equipo, para la ESP32 |
| Puente Python | Puerto 8765 dentro de Docker; no se publica en la red |
| Nginx | Puerto HTTP 8080 del equipo; sirve el panel y reenvía `/ws` al puente |

Esta versión funciona sin dominio y sin túnel. El dashboard no tiene inicio de sesión: cualquier
equipo con acceso al puerto 8080 puede verlo. Úsalo en una red local de confianza y no redirijas
estos puertos desde el router a Internet. MQTT y HTTP locales no están cifrados.

## 1. Extraer y comprobar requisitos

Extrae el ZIP en una carpeta nueva, por ejemplo al lado de tu carpeta anterior de Mosquitto.
No extraigas encima de `mosquitto/config`, `data` o `log` existentes.
Abre una terminal dentro de `Proyecto-IoT-Local` y comprueba:

```bash
docker info
docker compose version
python3 --version
```

Se requiere Docker Engine funcionando, Compose v2 o posterior y Python 3 en el equipo anfitrión.
Python solo usa su biblioteca estándar para configurar y enviar pruebas; las dependencias del
puente se instalan dentro de su imagen. La descarga de imágenes y la primera construcción
requieren Internet. Una vez construidas, las gráficas y la comunicación local no lo necesitan.

## 2. Preparar las cuentas

```bash
python3 scripts/configurar.py
```

El asistente pide dos veces una contraseña de al menos 8 caracteres para **IoTProyecto**.
Puedes utilizar la que ya conoces para facilitar la futura configuración de la ESP32.
No recupera ni copia las credenciales del broker anterior.

También genera la cuenta **dashboard** con una contraseña aleatoria. La guarda en `.env`
con permisos 600. Las cuentas se crean en un volumen exclusivo de este proyecto.

| Cuenta | Permiso |
|---|---|
| `IoTProyecto` | Publicar en `iot/monitoreo/mediciones` |
| `dashboard` | Leer `iot/monitoreo/mediciones` |

No publiques `.env` ni lo agregues al repositorio. Su contraseña está codificada en Base64 para
evitar problemas con caracteres especiales; **Base64 no es cifrado**. El asistente no muestra
las contraseñas ni las escribe en el historial de la terminal.

## 3. Liberar el puerto 1883 en Ubuntu

En tu Ubuntu ya hay un contenedor llamado `mosquitto` que ocupa ese puerto. Comprueba su estado:

```bash
docker ps --filter name=mosquitto
```

Cuando vayas a probar la nueva versión, detén el contenedor anterior:

```bash
docker stop mosquitto
```

No lo borres. Sus carpetas, cuentas y datos permanecen intactos. Habrá una interrupción breve
del broker mientras cambias de uno al otro. En la Raspberry, si no hay otro broker, omite este paso.

Si prefieres ejecutar ambos a la vez en Ubuntu, cambia `MQTT_PORT=1884` en `.env` en lugar de
detener el anterior. La ESP32 se conectaría entonces al puerto **1884**. El puente sigue usando
el puerto interno 1883. La prueba incluida también utiliza el puerto interno del nuevo broker.

## 4. Validar y arrancar

Desde la carpeta del proyecto:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail 30 mosquitto puente web
```

Abre en el equipo que ejecuta Docker:

```text
http://localhost:8080
```

Debe indicar **Esperando mediciones**, con las tarjetas vacías. No genera lecturas automáticamente.
El arranque puede tardar mientras se construye el puente y pasa su comprobación de salud.
Si muestra MQTT desconectado, revisa los registros de `mosquitto` y `puente`.

Desde otro equipo de la misma red utiliza `http://IP_DEL_SERVIDOR:8080`. Para identificar la IP:

```bash
ip -4 addr show
```

Usa la dirección de la interfaz WiFi o Ethernet conectada, no las direcciones de las redes Docker.
No abras `index.html` con doble clic: el WebSocket necesita el servidor web.

## 5. Probar el recorrido sin ESP32

Con el dashboard abierto, ejecuta:

```bash
python3 scripts/publicar_prueba.py
```

Introduce la contraseña de **IoTProyecto** que elegiste en el paso 2. El script publica cinco
lecturas fijas de prueba, una por segundo. Son datos simulados enviados explícitamente por MQTT:

| Medición | Valor esperado |
|---|---|
| Voltaje | 220.50 V |
| Corriente | 1.230 A |
| Resistencia | 179.30 Ω |
| Fase | 45.2° |

El panel debe mostrar **Recibiendo datos** y actualizar las cinco gráficas. Tras aproximadamente
10 segundos sin lecturas nuevas debe mostrar **Sin lecturas recientes**, conservando los últimos
valores y su fecha. El indicador no afirma que un sensor esté físicamente conectado: solo informa
si el puente recibe datos recientes.

Esta prueba comprueba MQTT → puente → servidor web → navegador. Para verificar la entrada desde
la red y el acceso del puerto 1883/1884 se necesita publicar desde la ESP32 u otro equipo.

## 6. Contrato que deberá utilizar la ESP32

| Parámetro | Valor |
|---|---|
| Broker | IP local del equipo que ejecuta Docker |
| Puerto | 1883, o el valor de `MQTT_PORT` en `.env` |
| Usuario | `IoTProyecto` |
| Contraseña | La elegida con el configurador |
| Tema | `iot/monitoreo/mediciones` |
| Formato | Un objeto JSON con las cuatro mediciones numéricas |
| Retain | **false** |
| Frecuencia inicial propuesta | Una lectura por segundo |

Ejemplo de carga útil:

```json
{"voltaje":220.5,"corriente":1.23,"resistencia":179.3,"fase":45.2}
```

Usa números JSON, no cadenas como `"220.5"`, unidades dentro del valor ni nombres diferentes.
Los cuatro campos son obligatorios y deben ser finitos; los mensajes incorrectos se descartan.
Un mensaje tiene un límite de 4096 bytes. Los campos adicionales se ignoran.
El sistema todavía no verifica rangos físicos ni la coherencia eléctrica entre las magnitudes.

El puente ignora los mensajes retenidos que recibe al suscribirse, para no presentar una lectura
antigua como si fuera nueva. Publica periódicamente con `retain=false`.
La hora mostrada es la recepción en el servidor, no el instante de adquisición en el Arduino.

## 7. Llevarlo a la Raspberry o cambiar de red

1. Copia esta carpeta, sin `.env`, a la Raspberry Pi 4 con Debian 13 ARM64.
2. Comprueba que Docker Engine, Compose y Python 3 estén disponibles.
3. Ejecuta el configurador y después `docker compose up -d --build` en la Raspberry.
4. Si mantienes la contraseña de IoTProyecto, esa credencial de la ESP32 no cambia.
5. Cambia la dirección del broker en la ESP32 para que apunte a la Raspberry.
6. Abre el dashboard con la IP local de la Raspberry.

La construcción en cada equipo selecciona imágenes de su arquitectura. No copies una imagen
del puente construida exclusivamente para AMD64 esperando ejecutarla nativamente en ARM64.
Los volúmenes del equipo anterior no se copian con la carpeta: esta instalación crea cuentas y
estado nuevos. Este paquete no migra el historial ni el estado del broker anterior.

Al cambiar de casa o escuela, conecta Raspberry y ESP32 a una red que permita la comunicación
entre clientes y revisa la IP del broker. Docker no configura el WiFi del anfitrión.
Puedes utilizar un hotspot compatible con ambos dispositivos; prueba antes que los clientes
se puedan comunicar. La página calcula su dirección WebSocket a partir de la URL con la que
se abre, de modo que no hay que editar `app.js` al cambiar de IP.

No fijes la IP antigua `10.100.77.165` en el proyecto: pertenecía a una conexión concreta de Ubuntu.

## 8. Operación y diagnóstico

```bash
docker compose logs -f puente
docker compose logs -f mosquitto
docker compose ps
```

Para apagar los servicios conservando los volúmenes:

```bash
docker compose down
```

Para volver a arrancar:

```bash
docker compose up -d
```

No utilices `docker compose down -v` si quieres conservar las cuentas y los datos del broker.
La política de reinicio es `unless-stopped`; Docker debe arrancar con el sistema. Si detuviste
manualmente el proyecto, tendrás que arrancarlo de nuevo. Antes de desconectar físicamente
la Raspberry, apaga Debian de forma normal.

Para cambiar las contraseñas:

```bash
docker compose down
python3 scripts/configurar.py --actualizar
docker compose up -d
```

Actualiza la contraseña en la ESP32. El configurador solo administra las dos cuentas de este
proyecto y reemplaza su archivo de cuentas, no el de tu instalación anterior.

Para volver al broker anterior en Ubuntu:

```bash
docker compose down
docker start mosquitto
```

| Problema | Qué revisar |
|---|---|
| `address already in use` | Otro contenedor o servicio ocupa 1883 o 8080; detén el anterior o cambia el puerto en `.env` |
| Broker no arranca por credenciales | Ejecuta el configurador; verifica los registros de Mosquitto |
| MQTT desconectado en el panel | Revisa `.env` y los registros del puente; no cambies la contraseña dashboard manualmente |
| Esperando mediciones | Tema, cuenta, contraseña y JSON de la ESP32; comprueba con el script de prueba |
| Funciona en localhost, pero no en otro equipo | IP correcta, firewall y posible aislamiento de clientes del WiFi |
| No actualiza después de modificar `.env` | Ejecuta `docker compose up -d`; `restart` no actualiza las variables del contenedor |
| Faltan gráficos sin Internet | Comprueba que exista `web/vendor/chart.umd.min.js`; no depende de un CDN |

`STALE_SECONDS=10` define cuántos segundos sin lectura se consideran datos no recientes.
Si cambias deliberadamente la frecuencia de publicación, ajusta ese umbral.
Los registros Docker se rotan para evitar crecimiento ilimitado de logs.

## Alcance

- Ventana de 60 puntos por navegador, sin base de datos ni historial permanente.
- El puente conserva una última lectura en memoria para un navegador que acaba de conectarse;
  las 60 lecturas previas no se restauran al recargar.
- No incluye control remoto de actuadores ni comandos desde el navegador.
- La exposición a Internet queda para una siguiente etapa; `/ws` ya utiliza el mismo origen de
  la página y selecciona WSS cuando la página se sirve por HTTPS.

## Dependencias y referencias

- Mosquitto: `eclipse-mosquitto:2.1.2-alpine`.
- Nginx: `nginx:1.28.0-alpine`.
- Python base: `python:3.13-slim-bookworm` (la revisión de parche de la imagen puede cambiar).
- Paho MQTT 2.1.0 y aiohttp 3.14.5, fijados en `bridge/requirements.txt`.
- Chart.js 4.5.1 incluido localmente; licencia MIT en `web/vendor/Chart.js-LICENSE.md`.
- Docker Compose: https://docs.docker.com/compose/
- Mosquitto: https://mosquitto.org/documentation/
- Paho: https://eclipse.dev/paho/clients/python/docs/
- aiohttp: https://docs.aiohttp.org/en/stable/

Las pruebas realizadas y sus límites se documentan en `VALIDACION.md`.
