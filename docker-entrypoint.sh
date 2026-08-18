#!/bin/sh
set -eu

if [ "$(id -u)" = "0" ]; then
  # Volumes existentes podem ter sido criados pelo Nixpacks como root. Ajuste somente
  # o volume de dados conhecido antes de reduzir privilégios para o usuário da aplicação.
  chown -R sivs:sivs /data
  exec gosu sivs "$@"
fi

exec "$@"
