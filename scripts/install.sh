#!/usr/bin/env bash
# install.sh - instala las skills del kit en un runtime de agentes.
#
# Uso:
#   ./scripts/install.sh --target <dir> [--profile minimal|standard|full] [--dry-run]
#
# El instalador es idempotente y NO sobrescribe archivos existentes sin --force.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${HOME}/.hermes/skills"
PROFILE="standard"
DRY_RUN=0
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Argumento desconocido: $1" >&2; exit 2 ;;
  esac
done

case "$PROFILE" in
  minimal|standard|full) ;;
  *) echo "Perfil invalido: $PROFILE (minimal|standard|full)" >&2; exit 2 ;;
esac

if [[ ! -d "$REPO_ROOT/skills" ]]; then
  echo "ERROR: no existe $REPO_ROOT/skills" >&2
  exit 2
fi

PROFILE_FILE="$REPO_ROOT/manifest.yaml"
SKILL_LIST=()
if [[ -f "$PROFILE_FILE" ]]; then
  # Lee el bloque "profiles:" del manifest y toma las skills del perfil pedido.
  mapfile -t SKILL_LIST < <(python3 - "$PROFILE_FILE" "$PROFILE" <<'PY'
import sys, re
path, profile = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
lines = text.splitlines()
in_profiles = False
in_block = False
out = []
for line in lines:
    if re.match(r"^profiles:", line):
        in_profiles = True
        continue
    if in_profiles:
        if re.match(r"^\S", line) and not line.startswith(" "):
            break
        m = re.match(r"^\s{2}([a-z]+):\s*$", line)
        if m:
            in_block = (m.group(1) == profile)
            continue
        if in_block:
            m2 = re.match(r"^\s*-\s*([A-Za-z0-9_.-]+)\s*$", line)
            if m2:
                out.append(m2.group(1))
for s in out:
    print(s)
PY
  )
fi

if [[ ${#SKILL_LIST[@]} -eq 0 ]]; then
  echo "ERROR: el perfil '$PROFILE' no produjo skills. Revisar $PROFILE_FILE" >&2
  exit 2
fi

echo "Instalador Dev Agent Kit"
echo "  origen : $REPO_ROOT/skills"
echo "  destino: $TARGET"
echo "  perfil : $PROFILE ($(( ${#SKILL_LIST[@]} )) skills)"

mkdir -p "$TARGET"
INSTALLED=0
SKIPPED=0
MISSING=0

for skill in "${SKILL_LIST[@]}"; do
  src="$REPO_ROOT/skills/$skill"
  dst="$TARGET/$skill"
  if [[ ! -d "$src" ]]; then
    echo "  FALTA   $skill (no existe en el repo)"
    MISSING=$((MISSING + 1))
    continue
  fi
  if [[ -e "$dst" && $FORCE -eq 0 ]]; then
    echo "  EXISTE  $skill (omitido, usar --force para reemplazar)"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "  [dry]   $skill -> $dst"
    continue
  fi
  rm -rf "$dst"
  cp -r "$src" "$dst"
  echo "  OK      $skill"
  INSTALLED=$((INSTALLED + 1))
done

echo
echo "Instaladas: $INSTALLED | omitidas (ya existian): $SKIPPED | faltantes: $MISSING"
if [[ $MISSING -gt 0 ]]; then
  echo "AVISO: hay skills declaradas en el manifest que no existen en el repo." >&2
  exit 1
fi
if [[ $DRY_RUN -eq 0 && $INSTALLED -gt 0 ]]; then
  echo
  echo "Siguiente paso: bash $REPO_ROOT/scripts/smoke_test.sh --target $TARGET"
fi
