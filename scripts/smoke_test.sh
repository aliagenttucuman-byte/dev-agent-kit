#!/usr/bin/env bash
# smoke_test.sh - prueba de que el kit instala y carga limpio en una maquina vacia.
#
# Uso:
#   ./scripts/smoke_test.sh [--target <dir>] [--keep]
#
# Que verifica:
#   1. genericidad   -> scan_clean.py sin hallazgos
#   2. instalacion   -> instala en un directorio temporal vacio
#   3. carga         -> cada SKILL.md tiene frontmatter valido y name == directorio
#   4. punteros      -> references/, templates/, scripts/ referenciados existen
#   5. aislamiento   -> el destino no quedo contaminado por el repo de origen
#
# Exit: 0 = todo verde, 1 = fallo.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET=""
KEEP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "Argumento desconocido: $1" >&2; exit 2 ;;
  esac
done

PASS=0
FAIL=0
RESULTS=()

ok()   { PASS=$((PASS+1)); RESULTS+=("  OK    $1"); }
bad()  { FAIL=$((FAIL+1)); RESULTS+=("  FAIL  $1"); }
info() { RESULTS+=("  --    $1"); }

# ---------------------------------------------------------------- 1. genericidad
echo "[1/5] Genericidad del repo"
SCAN_OUT="$REPO_ROOT/scripts/scan_clean.py"
if [[ -x "$SCAN_OUT" || -f "$SCAN_OUT" ]]; then
  if python3 "$SCAN_OUT" --strict "$REPO_ROOT" >/tmp/devkit_scan.txt 2>&1; then
    ok "scan_clean.py: 0 hallazgos"
  else
    bad "scan_clean.py encontro hallazgos"
    sed -n '1,60p' /tmp/devkit_scan.txt
  fi
else
  bad "no existe scripts/scan_clean.py"
fi

# ---------------------------------------------------------------- 2. instalacion
WORKDIR="$(mktemp -d)"
if [[ -n "$TARGET" ]]; then
  DEST="$TARGET"
else
  DEST="$WORKDIR/skills"
fi
mkdir -p "$DEST"

echo "[2/5] Instalacion en destino limpio"
INSTALL_OUT="$(bash "$REPO_ROOT/scripts/install.sh" --target "$DEST" --profile standard 2>&1)"
if [[ $? -eq 0 ]]; then
  N="$(find "$DEST" -maxdepth 1 -mindepth 1 -type d | wc -l)"
  ok "instaladas $N skills en $DEST"
else
  bad "el instalador fallo"
  echo "$INSTALL_OUT" | sed -n '1,40p'
fi

# ---------------------------------------------------------------- 3. carga
echo "[3/5] Carga de skills (frontmatter + name == dir)"
LOAD_FAIL=0
while IFS= read -r skill_md; do
  dir="$(dirname "$skill_md")"
  name="$(basename "$dir")"
  if ! head -1 "$skill_md" | grep -q '^---$'; then
    bad "$name: sin frontmatter"
    LOAD_FAIL=$((LOAD_FAIL+1))
    continue
  fi
  if ! python3 - "$skill_md" "$name" <<'PY'
import sys, re
text = open(sys.argv[1], encoding="utf-8").read()
expected = sys.argv[2]
parts = text.split("---", 2)
if len(parts) < 3:
    sys.exit(1)
fm = parts[1]
m = re.search(r"^name:\s*[\"']?([A-Za-z0-9_.-]+)[\"']?\s*$", fm, re.M)
if not m:
    sys.exit(1)
if m.group(1) != expected:
    sys.exit(1)
if not re.search(r"^description:\s*\S", fm, re.M):
    sys.exit(1)
sys.exit(0)
PY
  then
    bad "$name: frontmatter invalido o name != directorio"
    LOAD_FAIL=$((LOAD_FAIL+1))
  fi
done < <(find "$DEST" -name SKILL.md -not -path "*/node_modules/*")
if [[ $LOAD_FAIL -eq 0 ]]; then
  ok "todas las skills cargan"
fi

# ---------------------------------------------------------------- 4. punteros
echo "[4/5] Punteros a references/ templates/ scripts/"
PTR_FAIL=0
while IFS= read -r skill_md; do
  dir="$(dirname "$skill_md")"
  name="$(basename "$dir")"
  while IFS= read -r ref; do
    [[ -e "$dir/$ref" ]] || { bad "$name -> $ref (roto)"; PTR_FAIL=$((PTR_FAIL+1)); }
  done < <(grep -oE '`(references|templates|scripts|examples)/[A-Za-z0-9_./-]+`' "$skill_md" 2>/dev/null \
           | tr -d '`' | sort -u)
done < <(find "$DEST" -name SKILL.md -not -path "*/node_modules/*")
if [[ $PTR_FAIL -eq 0 ]]; then
  ok "ningun puntero roto"
fi

# ---------------------------------------------------------------- 5. aislamiento
echo "[5/5] Aislamiento del destino"
if [[ -z "$TARGET" ]]; then
  if find "$DEST" -type f \( -name "*.py" -o -name "*.md" \) -exec grep -lE '/home/[a-z]+/|127\.0\.0\.1:8[0-9]{3}' {} + 2>/dev/null | grep -q .; then
    bad "el destino contiene rutas absolutas a maquinas concretas"
  else
    ok "el destino no contiene rutas de maquinas concretas"
  fi
else
  info "destino provisto por el usuario: se omite el chequeo de aislamiento"
fi

# ---------------------------------------------------------------- resultado
echo
echo "=========================================="
for r in "${RESULTS[@]}"; do echo "$r"; done
echo "=========================================="
echo "PASS: $PASS   FAIL: $FAIL"

if [[ $KEEP -eq 0 && -z "$TARGET" ]]; then
  rm -rf "$WORKDIR"
else
  echo "WORKDIR conservado: $WORKDIR"
fi

[[ $FAIL -eq 0 ]] && exit 0 || exit 1
