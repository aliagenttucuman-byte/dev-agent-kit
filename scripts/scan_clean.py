#!/usr/bin/env python3
"""scan_clean.py - verificador de genericidad del kit.

Escanea archivos del kit y falla si encuentra:
  1. terminos de cliente / persona / marca personal (ver forbidden_terms.py)
  2. rutas absolutas a maquinas concretas
  3. puertos del stack personal hardcodeados
  4. skills sin frontmatter valido
  5. referencias a archivos que no existen (punteros rotos)

Uso:
    python3 scripts/scan_clean.py                # escanea el repo entero
    python3 scripts/scan_clean.py --strict       # exit 1 si hay ERROR
    python3 scripts/scan_clean.py <ruta> ...     # escanea rutas especificas
    python3 scripts/scan_clean.py --json         # salida JSON

Exit codes: 0 = limpio, 1 = hay ERROR (con --strict), 2 = error de ejecucion.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from forbidden_terms import (  # noqa: E402
    FORBIDDEN_PATH_PATTERNS,
    FORBIDDEN_PORTS,
    etiqueta_segura,
    iter_forbidden,
)


def _resolver_hash(etiqueta: str) -> str:
    """Devuelve el termino real de una etiqueta 'privado#hash'. '' si no existe."""
    if not etiqueta.startswith("privado#"):
        return ""
    from forbidden_terms import LOCAL_TOKEN_MAP  # noqa: PLC0415

    return LOCAL_TOKEN_MAP.get(etiqueta.split("#", 1)[1], "")

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", "site-packages",
}
TEXT_EXT = {
    ".md", ".py", ".sh", ".bash", ".yaml", ".yml", ".json", ".txt", ".toml",
    ".cfg", ".ini", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".env",
    ".example", ".sql", "",
}
SKIP_FILES = {".gitignore", ".DS_Store", "LICENSE", "package-lock.json"}

# Archivos que declaran los terminos prohibidos: se auto-eximen del chequeo
# de "forbidden-term" (pero no del resto de los chequeos).
SELF_EXEMPT = {"scripts/forbidden_terms.py", "scripts/scan_clean.py"}


class Finding:
    def __init__(self, path, line, kind, token, message):
        self.path = path
        self.line = line
        self.kind = kind
        self.token = token
        self.message = message

    def as_dict(self):
        return {
            "path": self.path,
            "line": self.line,
            "kind": self.kind,
            "token": self.token,
            "message": self.message,
        }


def iter_files(roots):
    for root in roots:
        root = Path(root)
        if root.is_file():
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn in SKIP_FILES:
                    continue
                if Path(fn).suffix.lower() not in TEXT_EXT:
                    continue
                yield Path(dirpath) / fn


def scan_text(path, rel, text):
    findings = []
    self_exempt = rel in SELF_EXEMPT
    lines = text.splitlines()
    for term, case_sensitive, allowlist in iter_forbidden():
        # Limites de palabra: sin esto "Alma" matchea "Almacenamiento" y
        # "Nico" matchea "tecnico". Un scanner con falsos positivos pierde
        # autoridad: hay que reportar solo lo que de verdad esta.
        core = term.strip()
        if core and (core[0].isalnum() or core[0] == "_"):
            needle = r"\b" + re.escape(core) + r"\b"
        else:
            needle = re.escape(core)
        pattern = re.compile(needle, 0 if case_sensitive else re.IGNORECASE)
        for i, line in enumerate(lines, 1):
            m = pattern.search(line)
            if not m:
                continue
            tail = line[m.end():]
            if any(tail.startswith(a) for a in allowlist):
                continue
            # El propio archivo forbidden_terms.py y los scripts de scan se auto-declaran
            if self_exempt:
                break
            # Los terminos de la denylist PRIVADA se reportan por hash: el log
            # de CI es publico y no puede revelar el nombre del cliente.
            findings.append(Finding(
                rel, i, "forbidden-term", etiqueta_segura(term),
                f"termino prohibido '{etiqueta_segura(term)}' (case_sensitive={case_sensitive})",
            ))
            break  # una vez por archivo y termino basta
    for pat in FORBIDDEN_PATH_PATTERNS:
        for i, line in enumerate(lines, 1):
            if re.search(pat, line):
                if self_exempt:
                    break
                findings.append(Finding(rel, i, "absolute-path", pat, f"ruta fija detectada /{pat}/"))
                break
    for port in FORBIDDEN_PORTS:
        for i, line in enumerate(lines, 1):
            if re.search(rf"(?<!\d){port}(?!\d)", line):
                if self_exempt:
                    break
                findings.append(Finding(rel, i, "hardcoded-port", port, f"puerto personal hardcodeado {port}"))
                break
    findings.extend(check_corrupted_chars(rel, lines))
    return findings


# Caracteres fuera del rango latino habitual que son casi siempre basura:
# ideogramas CJK, hangul, kana, cirílico, presentation forms y el bloque
# de diagramas. El arbol ASCII con caracteres de caja (U+2500 y familia) si
# esta permitido: se usa para dibujar estructuras de carpetas.
_ALLOWED_BOX_CHARS = set(
    "─│├└┌┐┘┬┴┼"
    "━┃┏┓┗┛┣┫┳┻╋"
    "═║╔╗╚╝╠╣╦╩╬"
    "▸▾◂◃►"
    "•●○◦▪▫"
    "✓✔✗✘"
    "→←↑↓↔⇒⇐"
    "…—–"
    "‘’“”"
)


def check_corrupted_chars(rel, lines):
    """Detecta caracteres corruptos: CJK, cirilico y otros alfabetos no esperados.

    Sin este check, un ideograma colado por autocompletado pasa el build y
    llega al cliente. Se permite el set de dibujo de cajas para los arboles
    de estructura de carpetas.
    """
    findings = []
    for i, line in enumerate(lines, 1):
        for ch in line:
            cp = ord(ch)
            if cp < 128:
                continue
            if ch in _ALLOWED_BOX_CHARS:
                continue
            # Latin-1 supplement y latino extendido: tildes, enye, dieresis.
            if 0x00A0 <= cp <= 0x024F:
                continue
            # Simbolos comunes y punctuation Unicode util.
            if 0x2000 <= cp <= 0x206F:
                continue
            if 0x20A0 <= cp <= 0x20BF:
                continue
            if 0x2100 <= cp <= 0x214F:
                continue
            # Emoji: no aportan nada en documentacion tecnica.
            if 0x1F300 <= cp <= 0x1FAFF:
                findings.append(Finding(
                    rel, i, "corrupted-char", f"U+{cp:04X}",
                    f"caracter no permitido (emoji o pictograma): U+{cp:04X}",
                ))
                break
            # Todo lo demas (CJK, hangul, kana, cirilico, presentation forms).
            findings.append(Finding(
                rel, i, "corrupted-char", f"U+{cp:04X}",
                f"caracter fuera del alfabeto esperado (posible corrupcion): U+{cp:04X} {ch!r}",
            ))
            break
    return findings


def check_frontmatter(path, rel, text, findings):
    if not path.name == "SKILL.md":
        return
    if not text.startswith("---"):
        findings.append(Finding(rel, 1, "frontmatter", "-", "SKILL.md sin frontmatter YAML"))
        return
    parts = text.split("---", 2)
    if len(parts) < 3:
        findings.append(Finding(rel, 1, "frontmatter", "-", "frontmatter sin cierre"))
        return
    fm = parts[1]
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(fm)
    except Exception as exc:  # noqa: BLE001
        findings.append(Finding(rel, 1, "frontmatter", "-", f"YAML invalido: {exc}"))
        return
    if not isinstance(data, dict):
        findings.append(Finding(rel, 1, "frontmatter", "-", "frontmatter no es un mapping"))
        return
    for key in ("name", "description"):
        if key not in data:
            findings.append(Finding(rel, 1, "frontmatter", key, f"falta campo '{key}'"))
    name = data.get("name")
    if name and name != path.parent.name:
        findings.append(Finding(
            rel, 1, "frontmatter", "name",
            f"name='{name}' != directorio '{path.parent.name}'",
        ))
    desc = data.get("description")
    if isinstance(desc, str):
        # El chequeo real es que YAML haya parseado: si "description" tiene
        # ': ' adentro pero esta entre comillas, YAML lo resuelve bien.
        # Solo es error si el YAML no parseo (ya verificado arriba).
        if not desc.strip():
            findings.append(Finding(rel, 1, "frontmatter", "description",
                                    "description vacio"))


def check_broken_pointers(path, rel, text, findings):
    if path.name != "SKILL.md":
        return
    for m in re.finditer(r"`((?:references|templates|scripts|examples)/[A-Za-z0-9_./\-]+)`", text):
        ref = m.group(1)
        if not (path.parent / ref).exists():
            findings.append(Finding(rel, text[:m.start()].count("\n") + 1,
                                    "broken-pointer", ref, f"puntero roto -> {ref}"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", default=None)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--private-labels",
        action="store_true",
        help=(
            "Muestra el nombre real de los terminos de la denylist privada. "
            "Solo para uso local: el log de CI es publico y no debe revelar "
            "el nombre del cliente. El default (hash) es el seguro."
        ),
    )
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    # El kit se compone de dos repos: el de skills (biblioteca) y el de tooling.
    # Por defecto se escanean los dos, para que la genericidad se verifique
    # sobre el producto completo y no solo sobre una parte.
    sibling_skills = repo_root.parent / "dev-agent-skills"
    if args.paths:
        roots = [Path(p) for p in args.paths]
    else:
        roots = [repo_root]
        if sibling_skills.is_dir():
            roots.append(sibling_skills)

    findings = []
    scanned = 0
    for path in iter_files(roots):
        try:
            rel = str(path.relative_to(repo_root))
        except ValueError:
            try:
                rel = "../" + str(path.relative_to(sibling_skills))
            except ValueError:
                rel = str(path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            findings.append(Finding(rel, 0, "io", "-", f"no se pudo leer: {exc}"))
            continue
        scanned += 1
        findings.extend(scan_text(path, rel, text))
        check_frontmatter(path, rel, text, findings)
        check_broken_pointers(path, rel, text, findings)

    # Con --private-labels se revela el nombre real de los terminos privados.
    # El default los deja como hash: el log de CI es publico.
    if args.private_labels:
        for f in findings:
            if f.kind == "forbidden-term" and f.token.startswith("privado#"):
                real = _resolver_hash(f.token)
                if real:
                    f.token = real
                    f.message = f"termino prohibido '{real}'"

    errors = [f for f in findings if f.kind in ("forbidden-term", "absolute-path", "hardcoded-port", "frontmatter", "broken-pointer")]
    if args.json:
        print(json.dumps({
            "scanned": scanned,
            "findings": [f.as_dict() for f in findings],
            "errors": len(errors),
        }, indent=2, ensure_ascii=False))
        return 1 if (args.strict and errors) else 0

    if not findings:
        print(f"OK - {scanned} archivos escaneados, 0 hallazgos.")
        return 0

    by_kind = {}
    for f in findings:
        by_kind.setdefault(f.kind, []).append(f)
    print(f"ESCANEADOS: {scanned} archivos")
    for kind, items in sorted(by_kind.items()):
        print(f"\n[{kind}] {len(items)} hallazgo(s)")
        for f in items[:40]:
            print(f"  {f.path}:{f.line}  {f.message}")
        if len(items) > 40:
            print(f"  ... +{len(items) - 40} mas")
    print(f"\nTOTAL: {len(findings)} hallazgos ({len(errors)} errores)")
    return 1 if (args.strict and errors) else 0


if __name__ == "__main__":
    sys.exit(main())
