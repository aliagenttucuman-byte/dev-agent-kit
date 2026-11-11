"""Lista única de términos prohibidos en el kit genérico.

Este archivo es la fuente de verdad de la "limpieza". Todo lo que el kit
genera (skills, templates, docs, scripts) debe pasar el filtro sin excepciones.

Reglas de match:
  - case_sensitive=False  -> se busca sin distinguir mayúsculas (token fuerte)
  - case_sensitive=True   -> se busca con mayúsculas exactas (token ambiguo,
                              para no romper palabras inglesas legitimas)
  - allowlist             -> si el match esta seguido de uno de estos strings,
                              el match se ignora (ej: "Cosmos DB")
"""

# (termino, case_sensitive, allowlist_de_siguiente)
FORBIDDEN_TERMS = [
    # --- Cliente /Corporacion ---
    ("LATAM", False, []),
    ("AlegentAI", False, []),
    ("alegentai.com", False, []),
    ("YPF", False, []),
    ("ForestAI", False, []),
    ("Fleet Optimizer", False, []),
    ("Fleet Optimiser", False, []),
    ("Expreso Bisonte", False, []),
    ("Bisonte", False, []),
    ("CODEEN", False, []),
    ("Vitoco", False, []),
    ("Ground Handling", False, []),
    ("Smart Contracts", False, []),
    ("Propension", False, []),
    ("Propensión", False, []),
    ("handson", False, []),
    ("Hands-On", False, []),
    ("Flores S.A", False, []),
    ("Nemo", False, []),
    ("Dalto", False, []),
    ("Ultravini", False, []),
    ("AeroVinci", False, []),
    ("Aerolineas", False, []),
    ("Aerolíneas", False, []),
    ("MRO", False, ["\n"]),
    ("ReFores", False, []),
    ("Embraer", False, []),
    ("LATAM ", False, []),
    # --- Proyecto interno (word-boundary, sensible a mayusculas) ---
    ("Cosmos", True, [" DB", "Db", " db", "DB"]),
    ("floci", False, []),
    ("FLoCI", False, []),
    ("finanzas", False, []),
    ("Finanzas", False, []),
    # --- Personas / marcas personales ---
    ("Nelson", False, []),
    ("Tony", False, []),
    ("Pablo Terian", False, []),
    ("Beto", False, []),
    ("Ricky", False, []),
    ("Mercedes", False, []),
    ("Nico ", False, []),
    ("Diego", False, []),
    ("Alma", False, []),
    ("Julian", False, []),
    ("Julián", False, []),
    ("Gino", False, []),
    ("Luigi", False, []),
    ("upsolver", False, []),
    ("aliagenttucuman", False, []),
    # --- Infraestructura personal ---
    ("/home/server", False, []),
    ("/home/nelson", False, []),
    ("ai-server", False, []),
    ("srv-ai", False, []),
    ("srv-ai2", False, []),
    ("~/.hermes/skills", False, []),
    ("~/brainstorming", False, []),
    ("~/proyectos", False, []),
    ("~/nelson", False, []),
    ("~/repos", False, []),
    ("/tmp/hermes", False, []),
    ("Nelsonardo", False, []),
    ("Dell", False, []),
    ("UTN", False, []),
    ("FRT", False, []),
    ("ADGE", False, []),
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


def iter_forbidden():
    """Devuelve (termino, case_sensitive, allowlist) para todos los tokens."""
    return list(FORBIDDEN_TERMS)
