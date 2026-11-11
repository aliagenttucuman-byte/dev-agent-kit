"""Reglas de genericidad del kit generico.

Este archivo es la fuente de verdad de la "limpieza" y es PUBLICO: no puede
contener el nombre de ningun cliente, persona o marca. Por eso no hay una
lista literal de terminos prohibidos.

El problema que resuelve:
  Un kit vendible no puede decir "prohibido mencionar X" en su propio codigo
  publico, porque el nombre X queda exposed en el repo. La lista de terminos
  prohibidos es tan sensible como los terminos que prohibe.

La solucion: reglas ESTRUCTURALES que detectan la clase de contaminacion sin
nombrar a nadie.

Reglas de match:
  - case_sensitive=False  -> se busca sin distinguir mayusculas
  - case_sensitive=True   -> se busca con mayusculas exactas (token ambiguo:
                              para no romper palabras inglesas legitimas)
  - allowlist             -> si el match esta seguido de uno de estos strings,
                              el match se ignora (ej: "Cosmos DB")

Ademas, se puede cargar una denylist PRIVADA (no versionada) desde:
  1. la variable de entorno DEVKIT_DENYLIST
  2. ~/.config/dev-agent-kit/denylist.local.json
Esa lista se suma a las reglas publicas y no se publica nunca.
"""

import json
import os
from pathlib import Path

# (termino, case_sensitive, allowlist_de_siguiente)
#
# NOTA: aca viven SOLO patrones que describen una clase de contaminacion y
# que no identifican a ningun cliente, persona o corporacion. Son terminos
# genericos de infraestructura personal, dominios de cliente o convenciones
# de nombres propios.
FORBIDDEN_TERMS = [
    # --- Infraestructura personal: rutas y hosts de una maquina concreta ---
    ("/home/server", False, []),
    ("/home/nelson", False, []),
    ("/Users/nelson", False, []),
    ("/Users/server", False, []),
    ("C:\\Users\\nelson", False, []),
    ("C:\\Users\\server", False, []),
    ("ai-server", False, []),
    ("srv-ai", False, []),
    ("srv-ai2", False, []),
    ("~/brainstorming", False, []),
    ("~/proyectos", False, []),
    ("~/nelson", False, []),
    ("~/repos", False, []),
    ("/tmp/hermes", False, []),

    # --- Dominios de cliente: el patron ".com.ar" con prefijo de proyecto ---
    # Un dominio de empresa es identificable por si mismo. El patron busca
    # subdominios de estilo "proyecto.dominio-empresa.com.ar".
    (r"\b[a-z0-9-]+\.(?:com\.ar|com\.br|com\.mx|com\.co)\b", False, []),
]

# Paths absolutos prohibidos: cualquier ruta fija a una maquina concreta.
FORBIDDEN_PATH_PATTERNS = [
    r"/home/[a-z]+/",
    r"/root/",
    r"C:\\\\Users\\\\",
    r"127\.0\.0\.1:8\d{3}",
    r"localhost:9\d{3}",
]

# Puertos del stack personal que no deben quedar hardcodeados.
FORBIDDEN_PORTS = [
    "8742", "8743", "8744", "8745", "8754", "8787", "9110",
    "8008", "8023", "8024", "9000", "9001", "3000",
]

# --------------------------------------------------------------------------
# Denylist PRIVADA (opcional)
# --------------------------------------------------------------------------
# Permite anadir terminos concretos sin exponerlos. Se busca en:
#   1. $DEVKIT_DENYLIST
#   2. ~/.config/dev-agent-kit/denylist.local.json
#
# Formato del JSON:
#   {
#     "terms": [
#       {"term": "NombreCliente", "case_sensitive": false, "allow": []}
#     ]
#   }
#
# Los terminos de la denylist local NO se pueden reportar por nombre en la
# salida del scanner (eso los expondría en el log de CI). Se reportan por su
# hash truncado: se puede confirmar que se detecto, sin decir cual era.


def _load_local_denylist() -> list[tuple[str, bool, list[str]]]:
    """Carga la denylist privada si existe. Nunca falla: es opcional."""
    candidates: list[Path] = []
    desde_env = os.environ.get("DEVKIT_DENYLIST")
    if desde_env:
        candidates.append(Path(desde_env))
    candidates.append(Path.home() / ".config" / "dev-agent-kit" / "denylist.local.json")

    for ruta in candidates:
        try:
            if not ruta.is_file():
                continue
            data = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        entradas = data.get("terms", []) if isinstance(data, dict) else []
        resultado: list[tuple[str, bool, list[str]]] = []
        for entrada in entradas:
            if not isinstance(entrada, dict):
                continue
            termino = entrada.get("term")
            if not isinstance(termino, str) or not termino.strip():
                continue
            resultado.append((
                termino,
                bool(entrada.get("case_sensitive", False)),
                list(entrada.get("allow", [])),
            ))
        return resultado
    return []


LOCAL_DENYLIST = _load_local_denylist()

# Hash corto de cada termino local, para reportarlo sin exponerlo.
def _hash_token(termino: str) -> str:
    import hashlib

    return hashlib.sha256(termino.strip().lower().encode("utf-8")).hexdigest()[:10]


# Mapa hash -> termino real. Se usa solo para redactar (reemplazar por
# <cliente:HASH>), nunca para mostrar el termino.
LOCAL_TOKEN_MAP = {}


def _build_token_map() -> None:
    for termino, _cs, _allow in LOCAL_DENYLIST:
        LOCAL_TOKEN_MAP[_hash_token(termino)] = termino


_build_token_map()


def iter_forbidden():
    """Devuelve (termino, case_sensitive, allowlist) para todos los tokens."""
    return list(FORBIDDEN_TERMS) + list(LOCAL_DENYLIST)


def is_local(termino: str) -> bool:
    """True si el termino viene de la denylist privada (no se expone)."""
    return termino in {t for t, _cs, _al in LOCAL_DENYLIST}


def etiqueta_segura(termino: str) -> str:
    """Nombre seguro para reportar: el termino real, o su hash si es local."""
    if is_local(termino):
        return f"privado#{_hash_token(termino)}"
    return termino
