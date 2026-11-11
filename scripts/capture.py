#!/usr/bin/env python3
"""capture.py - captura la huella de un proyecto para el loop de aprendizaje.

La huella NO se archiva con contenido de cliente. Se archiva el aprendizaje:
que habilidad se uso, donde se trabo el proceso, que se decidio y por que.

Uso:
    python3 scripts/capture.py --project <slug> --skill <skill-name> [--outcome ok|failed]
    python3 scripts/capture.py --project <slug> --gap "<descripcion del gap>"
    python3 scripts/capture.py --project <slug> --decision "<decision>" --reason "<por que>"
    python3 scripts/capture.py --project <slug> --deviation "<que se desvio>" --reason "<por que>"
    python3 scripts/capture.py --project <slug> --discard "<motivo>" --learning "<aprendizaje>"
    python3 scripts/capture.py --list [--project <slug>]

Salida: JSON a stdout. La huella se escribe en <out>/huellas/<project>.jsonl

Regla dura: el texto capturado se sanea antes de escribirse. Si el sanitizer
detecta algo que parece dato de cliente, lo reemplaza por un placeholder y
marca la entrada como 'requiere_revision'. No se escribe el dato.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# La misma lista de terminos prohibidos que usa el scanner de genericidad.
# Si una huella contiene uno, se redacta: la huella es el aprendizaje, no el dato.
try:
    sys.path.insert(0, str(Path(__file__).parent))
    from forbidden_terms import FORBIDDEN_TERMS  # type: ignore
except Exception:  # noqa: BLE001
    FORBIDDEN_TERMS = []

# Patrones que sugieren contenido de cliente. Se redactan, no se bloquean.
SENSITIVE_PATTERNS = [
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "<email>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<ip>"),
    (re.compile(r"\b(?:https?://)?(?:www\.)?[\w-]+\.(?:com|net|org|com\.ar|ar|io|ai)\b", re.I), "<url>"),
    (re.compile(r"\b(?:sk|pk|ghp|gho|xox[baprs])[-_][A-Za-z0-9_-]{16,}\b"), "<secret>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{3}){3}\b"), "<number>"),
    (re.compile(r"\b[A-Z]{2,}-[A-Z]{2,}-\d{2,}\b"), "<ticket>"),
]


def redact_forbidden(text: str) -> tuple[str, bool]:
    """Redacta terminos de cliente / marca personal. Devuelve (texto, hubo_match)."""
    if not text or not FORBIDDEN_TERMS:
        return text, False
    flagged = False
    out = text
    for term, case_sensitive, allowlist in FORBIDDEN_TERMS:
        if len(term.strip()) < 3:
            continue
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(re.escape(term), flags)

        def _sub(m, _term=term):
            return f"<cliente:{_term.strip()}>"

        new_out, n = pattern.subn(_sub, out)
        if n:
            # Si el match es parte de un termino permitido (ej: "Cosmos DB"), se revierte.
            tail_ok = any(new_out[m.end():].startswith(a) for a in allowlist)
            if not tail_ok:
                flagged = True
                out = new_out
    return out, flagged


def sanitize(text: str) -> tuple[str, bool]:
    """Redacta patrones sensibles y terminos de cliente. Devuelve (texto, requiere_revision)."""
    if not text:
        return "", False
    flagged = False
    out = text
    for pat, repl in SENSITIVE_PATTERNS:
        if pat.search(out):
            flagged = True
            out = pat.sub(repl, out)
    out, forb = redact_forbidden(out)
    flagged = flagged or forb
    return out, flagged


def huecos_dir(out_root: Path) -> Path:
    d = out_root / "huellas"
    d.mkdir(parents=True, exist_ok=True)
    return d


def append_huella(out_root: Path, project: str, record: dict) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "-", project).lower().strip("-") or "sin-proyecto"
    path = huecos_dir(out_root) / f"{safe}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def build_record(args) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    rec = {"ts": now, "project": args.project}

    if args.skill:
        clean, flagged = sanitize(args.skill)
        rec.update({
            "tipo": "skill_usada",
            "skill": clean,
            "outcome": args.outcome or "ok",
        })
    elif args.gap:
        clean, flagged = sanitize(args.gap)
        rec.update({"tipo": "gap", "descripcion": clean})
    elif args.decision:
        clean, flagged = sanitize(args.decision)
        reason, flagged2 = sanitize(args.reason or "")
        rec.update({"tipo": "decision", "decision": clean, "razon": reason})
        flagged = flagged or flagged2
    elif args.deviation:
        clean, flagged = sanitize(args.deviation)
        reason, flagged2 = sanitize(args.reason or "")
        rec.update({"tipo": "desviacion", "desvio": clean, "razon": reason})
        flagged = flagged or flagged2
    elif args.discard:
        clean, flagged = sanitize(args.discard)
        learning, flagged2 = sanitize(args.learning or "")
        rec.update({"tipo": "descarte", "motivo": clean, "aprendizaje": learning})
        flagged = flagged or flagged2
    else:
        rec.update({"tipo": "nota", "nota": ""})

    if flagged:
        rec["requiere_revision"] = True
        rec["nota"] = "Se detecto posible contenido sensible: redactado antes de archivar."
    return rec


def main():
    ap = argparse.ArgumentParser(description="Captura huellas del loop de aprendizaje.")
    ap.add_argument("--project", default="")
    ap.add_argument("--out", default=os.environ.get("DEV_KIT_HUELLAS", "./huellas"))
    ap.add_argument("--skill")
    ap.add_argument("--outcome", choices=["ok", "failed"])
    ap.add_argument("--gap")
    ap.add_argument("--decision")
    ap.add_argument("--reason")
    ap.add_argument("--deviation")
    ap.add_argument("--discard")
    ap.add_argument("--learning")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    out_root = Path(args.out).expanduser()

    if args.list:
        d = huecos_dir(out_root)
        files = sorted(d.glob("*.jsonl"))
        if not files:
            print(json.dumps({"huellas": []}, ensure_ascii=False))
            return 0
        resumen = []
        for f in files:
            tipos = {}
            total = 0
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                tipos[rec.get("tipo", "?")] = tipos.get(rec.get("tipo", "?"), 0) + 1
                total += 1
            resumen.append({
                "proyecto": f.stem,
                "total": total,
                "por_tipo": tipos,
            })
        print(json.dumps({"huellas": resumen}, indent=2, ensure_ascii=False))
        return 0

    if not args.project:
        ap.error("--project es obligatorio salvo con --list")

    rec = build_record(args)
    path = append_huella(out_root, args.project, rec)
    print(json.dumps({"escrito": str(path), "registro": rec}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
