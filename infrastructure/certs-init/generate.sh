#!/bin/sh
# Self-signed certificate for local use; skipped when a cert already exists in the volume.
set -eu
cd /certs
[ -s tls.crt ] && [ -s tls.key ] && { echo "certs present"; exit 0; }
openssl req -x509 -newkey rsa:2048 -nodes -days 825 -keyout tls.key -out tls.crt \
  -subj "/CN=${OPENWATCH_HOSTNAME:-localhost}" \
  -addext "subjectAltName=DNS:${OPENWATCH_HOSTNAME:-localhost},DNS:localhost,IP:127.0.0.1"
chmod 644 tls.crt tls.key
echo "generated self-signed cert for ${OPENWATCH_HOSTNAME:-localhost}"
