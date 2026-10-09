# -*- coding: utf-8 -*-
"""Revalida TXT heurísticos exclusivamente con el evaluador independiente existente."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src" if (ROOT / "src" / "modelo.py").exists() else ROOT / "src_referencia"), str(ROOT / "tools")]

from modelo import leer_instancia  # noqa: E402
from evaluar_asignacion import leer_asignacion, evaluar  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patron", required=True)
    parser.add_argument("--soluciones", required=True)
    parser.add_argument("--salida", required=True)
    args = parser.parse_args()

    output = Path(args.salida)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for instance_path in sorted((ROOT / "instancias").glob(args.patron)):
        inst = leer_instancia(instance_path)
        solution_path = Path(args.soluciones) / f"heur_{inst['nombre']}.txt"
        assignment = leer_asignacion(solution_path)
        result = evaluar(inst, assignment, 1.0, 1.0)
        (output / f"validacion_{inst['nombre']}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        rows.append({
            "instancia": inst["nombre"], "factible": result["factible"],
            "violaciones": len(result["violaciones"]),
            "objetivo": result.get("objetivo", ""), "T": result.get("T", ""),
            "suma_z": result.get("suma_z", ""),
            "no_satisfechos": result.get("no_satisfechos", ""),
        })

    with (output / "validacion_independiente.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["instancia", "factible", "violaciones", "objetivo", "T", "suma_z", "no_satisfechos"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Validadas {len(rows)} soluciones; factibles: {sum(r['factible'] for r in rows)}")
    return 0 if rows and all(row["factible"] for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())

