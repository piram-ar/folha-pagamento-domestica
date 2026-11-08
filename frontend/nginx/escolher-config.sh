#!/bin/sh
# Roda na subida do container (/docker-entrypoint.d). Com certificado, liga o HTTPS; sem, fica só HTTP.
set -e
if [ -s /etc/nginx/certs/servidor.crt ] && [ -s /etc/nginx/certs/servidor.key ]; then
    cp /etc/nginx/folha/https.conf /etc/nginx/conf.d/default.conf
    if [ "${API_HTTP_LEGADO:-1}" = "0" ]; then
        sed -i '/API_HTTP_LEGADO/,/FIM_API_HTTP_LEGADO/d' /etc/nginx/conf.d/default.conf
    fi
    echo "folha: HTTPS ligado (API pela porta 80: ${API_HTTP_LEGADO:-1})"
else
    cp /etc/nginx/folha/http.conf /etc/nginx/conf.d/default.conf
    echo "folha: sem certificado em /etc/nginx/certs, servindo só HTTP"
fi
