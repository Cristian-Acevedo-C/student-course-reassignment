# -*- coding: utf-8 -*-
"""Compara SCIP por defecto contra SCIP con warm start constructivo."""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
from pathlib import Path
import sys
import time

from pyscipopt import Eventhdlr, SCIP_EVENTTYPE

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" if (ROOT / "src" / "modelo.py").exists() else ROOT / "src_referencia"))
sys.path.insert(0, str(ROOT / "tools"))

from modelo import leer_instancia, construir_modelo, extraer_solucion  # noqa: E402
from evaluar_asignacion import leer_asignacion, evaluar as evaluar_independiente  # noqa: E402


class IncumbentTrajectory(Eventhdlr):
    def __init__(self):
        super().__init__()
        self.rows = []

    def eventinit(self):
        self.model.catchEvent(SCIP_EVENTTYPE.BESTSOLFOUND, self)
        self.model.catchEvent(SCIP_EVENTTYPE.DUALBOUNDIMPROVED, self)

    def eventexit(self):
        self.model.dropEvent(SCIP_EVENTTYPE.BESTSOLFOUND, self)
        self.model.dropEvent(SCIP_EVENTTYPE.DUALBOUNDIMPROVED, self)

    def eventexec(self, event):
        model = self.model
        if event.getType() == SCIP_EVENTTYPE.BESTSOLFOUND:
            best = model.getBestSol()
            pb = model.getSolObjVal(best) if best is not None else model.getPrimalbound()
            kind = "PB"
        else:
            pb = model.getPrimalbound()
            kind = "DB"
        self.rows.append({
            "t": float(model.getSolvingTime()),
            "kind": kind,
            "pb": float(pb),
            "db": float(model.getDualbound()),
            "nodes": int(model.getNNodes()),
        })


def complete_solution_values(inst: dict, assignment: dict[int, int]) -> dict[str, float]:
    """Valores consistentes para x,y,w,z,d+,d-,F,T del MILP sin cambiarlo."""
    students = sorted(inst["estudiantes"])
    courses = list(inst["cursos"])
    values: dict[str, float] = {}

    for i in students:
        for c in courses:
            values[f"x_{i}_{c}"] = float(assignment[i] == c)

    for i in students:
        same_any = 0
        for j in inst["preferencias"].get(i, []):
            together = int(assignment[i] == assignment[j])
            same_any = max(same_any, together)
            values[f"w_{i}_{j}"] = float(together)
            for c in courses:
                values[f"y_{i}_{j}_{c}"] = float(
                    assignment[i] == c and assignment[j] == c
                )
        values[f"z_{i}"] = float(same_any)

    dispersions = {}
    for criterion in inst["criterios"]:
        total = 0.0
        for level in inst["niveles"]:
            members = [
                i for i in students if inst["estudiantes"][i][criterion] == level
            ]
            average = len(members) / len(courses)
            for c in courses:
                difference = sum(assignment[i] == c for i in members) - average
                values[f"dp_{c}_{criterion}_{level}"] = max(difference, 0.0)
                values[f"dm_{c}_{criterion}_{level}"] = max(-difference, 0.0)
                total += abs(difference)
        dispersions[criterion] = total
        values[f"F_{criterion}"] = total
    values["T"] = max(dispersions.values()) if dispersions else 0.0
    return values


def inject_warm_start(model, inst: dict, assignment: dict[int, int]) -> dict:
    independent = evaluar_independiente(inst, assignment, 1.0, 1.0)
    if not independent["factible"]:
        return {"checked": False, "accepted": False, "reason": "auditoria_independiente"}

    values = complete_solution_values(inst, assignment)
    by_name = {var.name: var for var in model.getVars()}
    missing = sorted(set(by_name) - set(values))
    extra = sorted(set(values) - set(by_name))
    if missing or extra:
        return {
            "checked": False, "accepted": False,
            "reason": f"variables_inconsistentes missing={missing[:8]} extra={extra[:8]}",
        }

    solution = model.createSol()
    for name, var in by_name.items():
        model.setSolVal(solution, var, values[name])
    checked = bool(model.checkSol(
        solution, printreason=True, completely=True,
        checkbounds=True, checkintegrality=True, checklprows=True, original=True,
    ))
    accepted = bool(model.addSol(solution, free=True)) if checked else False
    return {
        "checked": checked,
        "accepted": accepted,
        "reason": "ok" if checked and accepted else "rechazada_por_scip",
        "objective": float(independent["objetivo"]),
        "T": float(independent["T"]),
        "no_satisfechos": int(independent["no_satisfechos"]),
    }


def run_scip(instance_path: Path, condition: str, assignment: dict[int, int] | None,
             time_limit: float, seed: int) -> dict:
    inst = leer_instancia(instance_path)
    model, variables = construir_modelo(
        inst, lambda_0=1.0, lambda_1=1.0,
        tiempo=time_limit, hilos=1, gap=0.0,
    )
    model.setParam("randomization/randomseedshift", int(seed))
    try:
        model.setParam("lp/threads", 1)
    except Exception:
        pass

    trajectory = IncumbentTrajectory()
    model.includeEventhdlr(trajectory, "trayectoria_scrp", "PB/DB SCRP")
    warm = {"checked": False, "accepted": False, "reason": "no_aplica"}
    if condition == "warm_start":
        if assignment is None:
            raise ValueError("La condicion warm_start requiere asignacion")
        warm = inject_warm_start(model, inst, assignment)
        if warm["accepted"]:
            trajectory.rows.append({
                "t": 0.0, "kind": "PB", "pb": warm["objective"],
                "db": -math.inf, "nodes": 0, "source": "warm_start",
            })

    wall_started = time.perf_counter()
    model.optimize()
    wall_seconds = time.perf_counter() - wall_started
    solving_seconds = float(model.getSolvingTime())

    pb_rows = [
        row for row in trajectory.rows
        if row["kind"] == "PB" and math.isfinite(row["pb"])
    ]
    pb_rows.sort(key=lambda row: row["t"])
    first = pb_rows[0] if pb_rows else None
    best_row = min(pb_rows, key=lambda row: (row["pb"], row["t"])) if pb_rows else None

    assignment_final, sum_z, value_t, _ = extraer_solucion(model, variables, inst)
    independent_final = (
        evaluar_independiente(inst, assignment_final, 1.0, 1.0)
        if assignment_final is not None else None
    )
    has_solution = model.getNSols() > 0
    return {
        "instancia": inst["nombre"],
        "condicion": condition,
        "seed_scip": seed,
        "limite_scip_s": time_limit,
        "estado": str(model.getStatus()),
        "tiempo_scip_s": solving_seconds,
        "tiempo_wall_s": wall_seconds,
        "tiempo_primer_incumbente_s": first["t"] if first else None,
        "calidad_primer_incumbente": first["pb"] if first else None,
        "tiempo_mejor_incumbente_s": best_row["t"] if best_row else None,
        "mejor_objetivo": float(model.getPrimalbound()) if has_solution else None,
        "cota_dual": float(model.getDualbound()) if has_solution else None,
        "gap_final": float(model.getGap()) if has_solution else None,
        "nodos": int(model.getNTotalNodes()),
        "iteraciones_lp": int(model.getNLPIterations()),
        "soluciones": int(model.getNSols()),
        "primal_dual_integral_scip": float(model.getPrimalDualIntegral()),
        "warm_checked": warm.get("checked"),
        "warm_accepted": warm.get("accepted"),
        "warm_reason": warm.get("reason"),
        "warm_objetivo": warm.get("objective"),
        "warm_T": warm.get("T"),
        "warm_no_satisfechos": warm.get("no_satisfechos"),
        "final_validador_independiente": independent_final["factible"] if independent_final else False,
        "final_T": value_t,
        "final_suma_z": sum_z,
        "trayectoria": trajectory.rows,
    }


def normalized_primal_integral(rows: list[dict], horizon: float, reference: float) -> float:
    """Integral primal normalizada respecto del mejor valor observado en el par."""
    pb_rows = sorted(
        (row for row in rows if row["kind"] == "PB" and math.isfinite(row["pb"])),
        key=lambda row: row["t"],
    )
    area = 0.0
    previous_t = 0.0
    current_gap = 1.0  # sin incumbente
    for row in pb_rows:
        t = min(max(float(row["t"]), 0.0), horizon)
        area += (t - previous_t) * current_gap
        pb = float(row["pb"])
        denominator = max(abs(pb), abs(reference), 1e-9)
        current_gap = min(1.0, max(0.0, (pb - reference) / denominator))
        previous_t = t
        if t >= horizon:
            break
    area += max(0.0, horizon - previous_t) * current_gap
    return area


def load_constructive_times(csv_path: Path) -> dict[str, float]:
    if not csv_path.exists():
        return {}
    with csv_path.open(encoding="utf-8", newline="") as stream:
        return {
            row["instancia"]: float(row["tiempo_total_s"])
            for row in csv.DictReader(stream)
        }


CSV_COLUMNS = [
    "instancia", "condicion", "seed_scip", "presupuesto_total_s",
    "tiempo_heuristica_s", "limite_scip_s", "tiempo_scip_s", "tiempo_pipeline_s",
    "estado", "tiempo_primer_incumbente_s", "calidad_primer_incumbente",
    "tiempo_mejor_incumbente_s", "mejor_objetivo", "cota_dual", "gap_final",
    "primal_integral_normalizada", "primal_dual_integral_scip", "nodos",
    "iteraciones_lp", "soluciones", "warm_checked", "warm_accepted", "warm_reason",
    "warm_objetivo", "warm_T", "warm_no_satisfechos",
    "final_validador_independiente", "final_T", "final_suma_z",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instancias", default=str(ROOT / "instancias"))
    parser.add_argument("--patron", default="c_n_9_l_3_s_4_i_*.txt")
    parser.add_argument("--soluciones", default=str(ROOT / "resultados_constructivo" / "L9_P3_C4" / "soluciones"))
    parser.add_argument("--resultados-constructivo", default=str(ROOT / "resultados_constructivo" / "L9_P3_C4" / "resultados_constructivo.csv"))
    parser.add_argument("--salida", default=str(ROOT / "resultados_warm_start" / "L9_P3_C4"))
    parser.add_argument("--presupuesto", type=float, default=30.0)
    parser.add_argument("--modo-presupuesto", choices=("igual_total", "igual_scip"), default="igual_total")
    parser.add_argument("--seed-scip", type=int, default=0)
    args = parser.parse_args()

    instance_paths = sorted(Path(args.instancias).glob(args.patron))
    if not instance_paths:
        parser.error("No se encontraron instancias")
    output_dir = Path(args.salida)
    output_dir.mkdir(parents=True, exist_ok=True)
    heuristic_times = load_constructive_times(Path(args.resultados_constructivo))

    all_runs = []
    for index, instance_path in enumerate(instance_paths):
        inst = leer_instancia(instance_path)
        solution_path = Path(args.soluciones) / f"heur_{inst['nombre']}.txt"
        if not solution_path.exists():
            raise FileNotFoundError(f"Falta {solution_path}")
        assignment = leer_asignacion(solution_path)
        heuristic_time = heuristic_times.get(inst["nombre"], 0.0)
        baseline_limit = args.presupuesto
        warm_limit = (
            max(0.1, args.presupuesto - heuristic_time)
            if args.modo_presupuesto == "igual_total" else args.presupuesto
        )
        seed = args.seed_scip + index

        baseline = run_scip(instance_path, "default", None, baseline_limit, seed)
        warm = run_scip(instance_path, "warm_start", assignment, warm_limit, seed)
        baseline["tiempo_heuristica_s"] = 0.0
        warm["tiempo_heuristica_s"] = heuristic_time
        for run in (baseline, warm):
            run["presupuesto_total_s"] = args.presupuesto
            run["tiempo_pipeline_s"] = run["tiempo_scip_s"] + run["tiempo_heuristica_s"]

        feasible_objs = [
            run["mejor_objetivo"] for run in (baseline, warm)
            if run["mejor_objetivo"] is not None
        ]
        reference = min(feasible_objs) if feasible_objs else math.inf
        for run in (baseline, warm):
            run["primal_integral_normalizada"] = (
                normalized_primal_integral(run["trayectoria"], run["limite_scip_s"], reference)
                if math.isfinite(reference) else None
            )
            all_runs.append(run)

        print(
            f"[{index + 1}/{len(instance_paths)}] {inst['nombre']}: "
            f"default obj={baseline['mejor_objetivo']} gap={baseline['gap_final']} | "
            f"warm obj={warm['mejor_objetivo']} gap={warm['gap_final']} "
            f"accepted={warm['warm_accepted']}",
            flush=True,
        )

    with (output_dir / "comparacion_warm_start.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for run in all_runs:
            writer.writerow({column: run.get(column, "") for column in CSV_COLUMNS})

    with (output_dir / "trayectorias.jsonl").open("w", encoding="utf-8") as stream:
        for run in all_runs:
            stream.write(json.dumps({
                "instancia": run["instancia"], "condicion": run["condicion"],
                "trayectoria": run["trayectoria"],
            }, ensure_ascii=False) + "\n")

    metadata = {
        "python": sys.version,
        "pyscipopt": __import__("pyscipopt").__version__,
        "platform": platform.platform(),
        "command": " ".join(sys.argv),
        "lambda_0": 1.0, "lambda_1": 1.0, "threads": 1, "gap_target": 0.0,
        "budget_mode": args.modo_presupuesto,
        "testigos_used": False,
        "primal_integral_definition": "area de gap primal normalizado respecto del mejor objetivo observado en cada par; gap=1 antes del primer incumbente",
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if all(run["warm_accepted"] for run in all_runs if run["condicion"] == "warm_start") else 2


if __name__ == "__main__":
    raise SystemExit(main())
