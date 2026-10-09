# -*- coding: utf-8 -*-
"""Ejecuta y valida la heuristica constructiva sobre una familia SCRP."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" if (ROOT / "src" / "modelo.py").exists() else ROOT / "src_referencia"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from modelo import leer_instancia  # noqa: E402
from evaluar_asignacion import evaluar as evaluar_independiente  # noqa: E402
from constructivo import (  # noqa: E402
    construct_solution,
    objective_components,
    violations_by_constraint,
)


RESULT_COLUMNS = [
    "instancia", "N", "L", "P", "C", "semilla_heuristica", "factible",
    "tiempo_primera_factible_s", "tiempo_construccion_s", "tiempo_mejora_s",
    "tiempo_total_s", "objetivo", "no_satisfechos", "suma_z", "T",
    "F_academico", "F_socioemocional", "F_convivencia",
    "viol_asignacion_unica", "viol_capacidad", "viol_separaciones",
    "viol_genero", "viol_origen", "viol_total",
    "validador_independiente_factible", "coincide_objetivo_independiente",
    "intentos", "nodos_busqueda", "backtracks", "estados_bloqueados",
    "reinicios_reparacion", "swaps_reparacion", "swaps_mejora",
    "reubicaciones_mejora", "archivo_solucion",
]


def write_solution(path: Path, inst: dict, assignment: dict[int, int],
                   metrics: dict, stats: dict, audit: dict) -> None:
    lines = [
        f"# Solucion heuristica constructiva - {inst['nombre']}",
        "# Los testigos no fueron leidos ni utilizados.",
        f"# factible={audit['factible']}",
        f"# objetivo={metrics['objetivo']}",
        f"# no_satisfechos={metrics['no_satisfechos']}",
        f"# suma_z={metrics['suma_z']}",
        f"# T={metrics['T']}",
        f"# F={json.dumps(metrics['F'], ensure_ascii=False, sort_keys=True)}",
        f"# tiempo_construccion_s={stats['construction_seconds']:.9f}",
        f"# tiempo_mejora_s={stats['improvement_seconds']:.9f}",
        f"# violaciones={json.dumps({k: audit[k]['violaciones'] for k in ['asignacion_unica','capacidad','separaciones','genero','origen']}, ensure_ascii=False)}",
        "",
        "[ASIGNACION]",
        "estudiante;curso_asignado",
    ]
    lines.extend(f"{i};{assignment[i]}" for i in sorted(assignment))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_one(instance_path: Path, output_dir: Path, seed: int,
            attempts: int, node_limit: int, improve: bool) -> tuple[dict, list[dict]]:
    inst = leer_instancia(instance_path)
    started = time.perf_counter()
    assignment, stats = construct_solution(
        inst,
        seed=seed,
        attempts=attempts,
        node_limit_per_attempt=node_limit,
        improve=improve,
    )
    elapsed = time.perf_counter() - started

    if assignment is None:
        empty_audit = {
            "asignacion_unica": {"violaciones": inst["N"]},
            "capacidad": {"violaciones": 0}, "separaciones": {"violaciones": 0},
            "genero": {"violaciones": 0}, "origen": {"violaciones": 0},
            "total_violaciones": inst["N"], "factible": False,
        }
        row = {
            "instancia": inst["nombre"], "N": inst["N"], "L": inst["L"],
            "P": inst["P"], "C": inst["C"], "semilla_heuristica": seed,
            "factible": False, "tiempo_primera_factible_s": "",
            "tiempo_construccion_s": stats.construction_seconds,
            "tiempo_mejora_s": stats.improvement_seconds, "tiempo_total_s": elapsed,
            "objetivo": "", "no_satisfechos": "", "suma_z": "", "T": "",
            "F_academico": "", "F_socioemocional": "", "F_convivencia": "",
            "viol_asignacion_unica": inst["N"], "viol_capacidad": 0,
            "viol_separaciones": 0, "viol_genero": 0, "viol_origen": 0,
            "viol_total": inst["N"], "validador_independiente_factible": False,
            "coincide_objetivo_independiente": False,
            "intentos": stats.attempts, "nodos_busqueda": stats.search_nodes,
            "backtracks": stats.backtracks, "estados_bloqueados": stats.blocked_states,
            "reinicios_reparacion": stats.repair_restarts,
            "swaps_reparacion": stats.repair_swaps,
            "swaps_mejora": stats.local_search_swaps,
            "reubicaciones_mejora": stats.local_search_relocations,
            "archivo_solucion": "",
        }
        return row, []

    audit = violations_by_constraint(inst, assignment)
    metrics = objective_components(inst, assignment)
    independent = evaluar_independiente(inst, assignment, 1.0, 1.0)
    objective_match = (
        independent.get("objetivo") is not None
        and abs(independent["objetivo"] - metrics["objetivo"]) <= 1e-8
    )

    solution_path = output_dir / "soluciones" / f"heur_{inst['nombre']}.txt"
    write_solution(solution_path, inst, assignment, metrics, stats.to_dict(), audit)

    violation_counts = {
        key: audit[key]["violaciones"]
        for key in ("asignacion_unica", "capacidad", "separaciones", "genero", "origen")
    }
    row = {
        "instancia": inst["nombre"], "N": inst["N"], "L": inst["L"],
        "P": inst["P"], "C": inst["C"], "semilla_heuristica": seed,
        "factible": audit["factible"],
        "tiempo_primera_factible_s": stats.first_feasible_seconds,
        "tiempo_construccion_s": stats.construction_seconds,
        "tiempo_mejora_s": stats.improvement_seconds, "tiempo_total_s": elapsed,
        "objetivo": metrics["objetivo"], "no_satisfechos": metrics["no_satisfechos"],
        "suma_z": metrics["suma_z"], "T": metrics["T"],
        "F_academico": metrics["F"].get("academico", ""),
        "F_socioemocional": metrics["F"].get("socioemocional", ""),
        "F_convivencia": metrics["F"].get("convivencia", ""),
        "viol_asignacion_unica": violation_counts["asignacion_unica"],
        "viol_capacidad": violation_counts["capacidad"],
        "viol_separaciones": violation_counts["separaciones"],
        "viol_genero": violation_counts["genero"],
        "viol_origen": violation_counts["origen"],
        "viol_total": audit["total_violaciones"],
        "validador_independiente_factible": independent["factible"],
        "coincide_objetivo_independiente": objective_match,
        "intentos": stats.attempts, "nodos_busqueda": stats.search_nodes,
        "backtracks": stats.backtracks, "estados_bloqueados": stats.blocked_states,
        "reinicios_reparacion": stats.repair_restarts,
        "swaps_reparacion": stats.repair_swaps,
        "swaps_mejora": stats.local_search_swaps,
        "reubicaciones_mejora": stats.local_search_relocations,
        "archivo_solucion": str(solution_path.relative_to(output_dir)),
    }
    assignment_rows = [
        {"instancia": inst["nombre"], "estudiante": i, "curso": assignment[i]}
        for i in sorted(assignment)
    ]
    return row, assignment_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instancias", default=str(ROOT / "instancias"))
    parser.add_argument("--patron", default="c_n_9_l_3_s_4_i_*.txt")
    parser.add_argument("--salida", default=str(ROOT / "resultados_constructivo" / "L9_P3_C4"))
    parser.add_argument("--seed", type=int, default=20261001)
    parser.add_argument("--intentos", type=int, default=20)
    parser.add_argument("--limite-nodos", type=int, default=100000)
    parser.add_argument("--sin-mejora", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.salida)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(Path(args.instancias).glob(args.patron))
    if not paths:
        parser.error(f"No se encontraron instancias con patron {args.patron}")

    rows = []
    assignment_rows = []
    for index, path in enumerate(paths):
        row, assignments = run_one(
            path, output_dir, args.seed + index, args.intentos,
            args.limite_nodos, not args.sin_mejora,
        )
        rows.append(row)
        assignment_rows.extend(assignments)
        print(
            f"[{index + 1}/{len(paths)}] {row['instancia']}: "
            f"factible={row['factible']} obj={row['objetivo']} "
            f"T={row['T']} t={float(row['tiempo_total_s']):.4f}s",
            flush=True,
        )

    with (output_dir / "resultados_constructivo.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    with (output_dir / "asignaciones_constructivo.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["instancia", "estudiante", "curso"])
        writer.writeheader()
        writer.writerows(assignment_rows)

    metadata = {
        "python": sys.version,
        "platform": platform.platform(),
        "command": " ".join(sys.argv),
        "instances": len(paths),
        "all_feasible": all(str(row["factible"]).lower() == "true" for row in rows),
        "all_independently_validated": all(
            str(row["validador_independiente_factible"]).lower() == "true" for row in rows
        ),
        "testigos_used": False,
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if metadata["all_independently_validated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

