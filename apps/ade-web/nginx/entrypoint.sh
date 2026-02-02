#!/usr/bin/env sh
set -e

: "${ADE_WEB_PROXY_TARGET:=http://api:8000}"
export ADE_WEB_PROXY_TARGET

envsubst '${ADE_WEB_PROXY_TARGET}' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
