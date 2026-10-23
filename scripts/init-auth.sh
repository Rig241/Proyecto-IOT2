#!/bin/sh
set -eu
umask 077
IFS= read -r device_b64
IFS= read -r bridge_b64
device_password=$(printf '%s' "$device_b64" | base64 -d)
bridge_password=$(printf '%s' "$bridge_b64" | base64 -d)
test -n "$device_password"
test -n "$bridge_password"
# Archivo nuevo dentro de un volumen exclusivo de este proyecto.
# No toca el password.txt ni los datos del broker anterior.
tmp=/auth/passwords.new
trap 'rm -f "$tmp"' EXIT
rm -f "$tmp"
mosquitto_passwd -b -c "$tmp" IoTProyecto "$device_password"
mosquitto_passwd -b "$tmp" dashboard "$bridge_password"
chown 1883:1883 "$tmp"
chmod 600 "$tmp"
mv "$tmp" /auth/passwords
cp /acl-template /auth/acl
chown 1883:1883 /auth/acl
chmod 600 /auth/acl
chown 1883:1883 /auth
chmod 750 /auth
echo 'Cuentas MQTT preparadas: IoTProyecto (publicar), dashboard (leer).'
