# Dev Agent Kit

**Kit de agentes de IA para desarrollo de software.** Conocimiento destilado de
metodologia,(stack, agentes y operacion) en forma de skills portable, instalable
en cualquier maquina, para cualquier cliente.

Este repo es **generico por construccion**: no contiene datos de cliente, marcas,
personas ni rutas de ninguna maquina concreta. Eso no es una promesa editorial,
es una propiedad verificada por un script (`scripts/scan_clean.py`) que corre
en CI y falla el build.

---

## Que es y que no es

| Es | No es |
|---|---|
| Metodologia de desarrollo (SDD de 9 fases) codificada como skills | Un framework deOpinion |
| Un roster de agentes con roles y reglas de routing | Un producto cerrado con licence lock-in |
| Estandares de ingenieria verificados por auditoria | Codigo de aplicacion que hay que mantener |
| Un instalador que levanta una instancia limpia | Un clone de la maquina de origen |

---

## Estructura

```
dev-agent-kit/
├── skills/                  # Skills genéricas (cada una autocontenida)
│   ├── dev-kit-<area>-<tema>/
│   │   ├── SKILL.md         # frontmatter + workflow + pitfalls
│   │   ├── references/      # detalle largo, templates, ejemplos
│   │   ├── templates/       # artefactos copiables
│   │   └── scripts/         # verificadores ejecutables
├── scripts/
│   ├── forbidden_terms.py   # reglas publicas de genericidad
│   ├── scan_clean.py        # verificador de genericidad (CI)
│   ├── install.sh           # instala el kit en un runtime
│   └── smoke_test.sh        # prueba de instalacion limpia
├── templates/               # plantillas de proyecto entregables
├── references/              # documentacion de arquitectura del kit
├── docs/                    # guia de uso, catalogo de skills, changelog
└── manifest.yaml            # inventario de skills + metadatos
```

---

## Las tres capas del kit

El kit separa **conocimiento** (que es lo que se vende) de **configuracion**
(que es lo que cambia por cliente) y de **contenido** (que no viaja).

```
CAPA 1 - NUCLEO VENDIBLE (este repo, generico)
  skills/ + templates/ + scripts/
  Metodologia, roster de agentes, estandares, instalador, auditor.

CAPA 2 - CONFIGURACION DEL CLIENTE (por instalacion, no en el repo)
  memoria, crons, canales, credenciales, taxonomia propia, proyectos.
  Se genera en la maquina destino. Nunca se versiona aqui.

CAPA 3 - CONTENIDO DE CLIENTE (no viaja)
  codigo, datos, secretos, conversaciones, historia de proyectos.
```

La regla que hace que esto funcione: **CAPA 1 nunca menciona nada de CAPA 3.**

---

## Instalacion

```bash
./scripts/install.sh --target <SKILLS_DIR> --profile minimal
```

`<SKILLS_DIR>` es el directorio donde el runtime lee las skills (por ejemplo
`~/.hermes/skills` en Hermes, `~/.claude/skills` en Claude Code).

Perfiles disponibles:

- `minimal` — solo el spine de metodologia (8 skills). Para empezar.
- `standard` — metodologia + agentes + ingenieria (default).
- `full` — todo, incluyendo las verticales opcionales (RAG, browser, video).

Despues de instalar, correr el smoke test:

```bash
./scripts/smoke_test.sh
```

El smoke test verifica, en una maquina limpia:
1. Que todas las skills cargan (frontmatter valido, `name` == directorio).
2. Que no hay terminos de cliente ni rutas absolutas.
3. Que los punteros a `references/`, `templates/` y `scripts/` no estan rotos.
4. Que el kit se instala en un directorio destino vacio sin sobrescribir nada.

---

## Uso

El kit no es una app. Es un **kit de skills** que se carga en un runtime de
agentes (Hermes, Claude Code, o cualquier compatible con el formato de skill).

El ciclo de trabajo que codifica:

```
CONSTITUCION -> SPEC -> CLARIFICAR -> PLAN -> ESTIMAR -> ANALIZAR
   -> TAREAS -> CHECKLIST -> IMPLEMENTAR
```

Cada fase tiene una skill que la gobierna y un artefacto verificable que
produce. El agente no avanza de fase sin el artefacto.

---

## Regla de oro del kit

> **Ninguna skill entra al kit sin pasar `scan_clean.py`.**

Si una skill menciona un cliente, una persona o una ruta concreta, no entra.
Si aporta un patron reusable, entra. La destilacion es parte del trabajo, no
un extra.

### Denylist privada (opcional)

El repo es publico, asi que **no puede contener la lista de terminos
prohibidos**: seria tan sensible como los terminos que prohibe. En su lugar:

- `scripts/forbidden_terms.py` publica **reglas estructurales** que detectan la
  clase de contaminacion sin nombrar a nadie: rutas de maquina concreta,
  dominios de empresa, hosts personales.
- Los terminos concretos se cargan de una **denylist local**, que no se
  versiona:

```bash
mkdir -p ~/.config/dev-agent-kit
cat > ~/.config/dev-agent-kit/denylist.local.json <<'JSON'
{
  "version": 1,
  "terms": [
    {"term": "NombreDeCliente", "case_sensitive": false, "allow": []},
    {"term": "MarcaPersonal", "case_sensitive": true, "allow": [" DB"]}
  ]
}
JSON
```

Tambien se puede ubicar con la variable `DEVKIT_DENYLIST`.

**Privacidad en los logs:** cuando el scanner detecta un termino de la denylist
privada, lo reporta por **hash** (`privado#8d2a6a7c54`), no por nombre: el log
de CI es publico. Para ver el nombre real en uso local:

```bash
python3 scripts/scan_clean.py --private-labels
```

Con esto, el repo se puede publicar y auditar sin filtrar nada, y la deteccion
sigue siendo completa.

---

## Licencia

MIT. Ver `LICENSE`.
