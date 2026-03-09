#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p backups

timestamp="$(date +%Y%m%d_%H%M%S)"
db_user="$(sed -n 's/^DB_USER=//p' .env | head -n1)"
db_name="$(sed -n 's/^DB_NAME=//p' .env | head -n1)"

if [[ -z "$db_user" || -z "$db_name" ]]; then
    echo "Faltan DB_USER o DB_NAME en .env" >&2
    exit 1
fi

out_file="backups/agencia_${timestamp}.sql"

docker compose exec -T postgres pg_dump \
    -U "$db_user" \
    -d "$db_name" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    > "$out_file"

if [[ ! -s "$out_file" ]]; then
    echo "El dump se generó vacío" >&2
    exit 1
fi

printf '%s\n' "$out_file"
