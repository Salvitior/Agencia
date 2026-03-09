#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

fail() {
    printf 'ERROR %s\n' "$*" >&2
    exit 1
}

read_container_env() {
    local key="$1"
    docker compose exec -T postgres env | sed -n "s/^${key}=//p" | head -n1
}

find_latest_backup() {
    find "$ROOT_DIR/backups" -maxdepth 1 -type f \
        \( -name 'agencia_*.sql' -o -name 'agencia_*.sql.gz' \) \
        -size +0c \
        ! -name 'agencia_.sql' \
        -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2-
}

dump_file="${1:-}"
if [[ -z "$dump_file" ]]; then
    dump_file="$(find_latest_backup)"
fi

[[ -n "$dump_file" ]] || fail "No se encontró ningún dump válido en backups/"
[[ -f "$dump_file" ]] || fail "No existe el dump: $dump_file"

db_user="$(read_container_env POSTGRES_USER)"
db_name="$(read_container_env POSTGRES_DB)"

if [[ -z "$db_user" ]]; then
    db_user="$(sed -n 's/^DB_USER=//p' .env | head -n1)"
fi

if [[ -z "$db_name" ]]; then
    db_name="$(sed -n 's/^DB_NAME=//p' .env | head -n1)"
fi

[[ -n "$db_user" ]] || fail "DB_USER no está definido en .env"
[[ -n "$db_name" ]] || fail "DB_NAME no está definido en .env"

if [[ "$dump_file" == *.gz ]]; then
    gunzip -c "$dump_file" | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$db_user" -d "$db_name"
else
    cat "$dump_file" | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$db_user" -d "$db_name"
fi

docker compose exec -T postgres psql -U "$db_user" -d "$db_name" -tAc "SELECT COUNT(*) FROM tours;" | tr -d '[:space:]'
