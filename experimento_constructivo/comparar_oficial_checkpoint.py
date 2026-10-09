# -*- coding: utf-8 -*-
"""Comparación pareada con construcción medida en esta ejecución y checkpoints.

Los tiempos presupuestados son construcción + tiempo SCIP. El armado del modelo
se informa aparte y no se incluye en el límite interno de SCIP.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "src" / "modelo.py" if (ROOT / "src" / "modelo.py").exists() else ROOT / "src_referencia" / "modelo.py"
sys.path[:0] = [str(MODEL_PATH.parent), str(ROOT / "tools"), str(Path(__file__).resolve().parent)]

from modelo import leer_instancia  # noqa: E402
from evaluar_asignacion import evaluar as evaluar_independiente  # noqa: E402
from constructivo import construct_solution  # noqa: E402
from comparar_warm_start import CSV_COLUMNS, normalized_primal_integral, run_scip  # noqa: E402


def clean_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    return value


def atomic_json(path: Path, obj: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(clean_json(obj), stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def persist_tables(folder: Path, names: list[str]) -> None:
    pairs = []
    for name in names:
        path = folder / "pares" / (name + ".json")
        if path.exists():
            pairs.append(json.loads(path.read_text(encoding="utf-8")))
    csv_tmp = folder / "comparacion_warm_start.csv.tmp"
    with csv_tmp.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for pair in pairs:
            for run in (pair["default"], pair["warm_start"]):
                writer.writerow({key: run.get(key, "") for key in CSV_COLUMNS})
    csv_tmp.replace(folder / "comparacion_warm_start.csv")
    trajectory_tmp = folder / "trayectorias.jsonl.tmp"
    with trajectory_tmp.open("w", encoding="utf-8") as stream:
        for pair in pairs:
            for condition in ("default", "warm_start"):
                run = pair[condition]
                stream.write(json.dumps(clean_json({
                    "instancia": run["instancia"], "condicion": condition,
                    "trayectoria": run["trayectoria"],
                }), ensure_ascii=False, allow_nan=False) + "\n")
    trajectory_tmp.replace(folder / "trayectorias.jsonl")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patron", default="c_n_9_l_3_s_4_i_*.txt")
    parser.add_argument("--salida", required=True)
    parser.add_argument("--presupuesto", type=float, default=3600.0)
    parser.add_argument("--seed-scip", type=int, default=0)
    parser.add_argument("--seed-heuristica", type=int, default=20261001)
    parser.add_argument("--intentos", type=int, default=20)
    parser.add_argument("--limite-nodos", type=int, default=50000)
    args = parser.parse_args()
    if args.presupuesto <= 0:
        parser.error("El presupuesto debe ser positivo")
    paths = sorted((ROOT / "instancias").glob(args.patron))
    if not paths:
        parser.error("No hay instancias para el patrón")
    folder = Path(args.salida).resolve()
    checkpoint = folder / "pares"
    checkpoint.mkdir(parents=True, exist_ok=True)
    names = [leer_instancia(path)["nombre"] for path in paths]
    configuration = {
        "version": 1, "instances": names,
        "sha256_instances": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "sha256_codigo": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                MODEL_PATH,
                ROOT / "tools" / "evaluar_asignacion.py",
                ROOT / "experimento_constructivo" / "constructivo.py",
                ROOT / "experimento_constructivo" / "comparar_warm_start.py",
                Path(__file__).resolve(),
            ]
        },
        "presupuesto_s": args.presupuesto,
        "seed_scip": args.seed_scip,
        "seed_heuristica": args.seed_heuristica,
        "intentos": args.intentos,
        "limite_nodos": args.limite_nodos,
        "python": sys.version, "pyscipopt": __import__("pyscipopt").__version__,
        "platform": platform.platform(),
        "threads": 1, "gap_target": 0.0, "lambda_0": 1.0, "lambda_1": 1.0,
        "presupuesto_definicion": "Tiempo SCIP + tiempo constructivo; no incluye armado del modelo ni serialización.",
    }
    config_file = folder / "protocolo.json"
    if config_file.exists():
        if json.loads(config_file.read_text(encoding="utf-8")) != configuration:
            parser.error("La configuración difiere de los checkpoints existentes; usar otra carpeta")
    else:
        atomic_json(config_file, configuration)

    for path, name in zip(paths, names):
        pair_file = checkpoint / (name + ".json")
        if pair_file.exists():
            print(f"[{name}] checkpoint existente", flush=True)
            continue
        inst = leer_instancia(path)
        replica = int(name.rsplit("_", 1)[-1])
        heuristic_start = time.perf_counter()
        assignment, stats = construct_solution(
            inst, seed=args.seed_heuristica + replica, attempts=args.intentos,
            node_limit_per_attempt=args.limite_nodos, improve=True,
        )
        heuristic_time = time.perf_counter() - heuristic_start
        if assignment is None:
            raise RuntimeError(f"Constructivo sin solución en {name}")
        audit = evaluar_independiente(inst, assignment, 1.0, 1.0)
        if not audit["factible"]:
            raise RuntimeError(f"Constructivo no factible en {name}: {audit['violaciones']}")
        if heuristic_time >= args.presupuesto:
            raise RuntimeError(f"Heurística agota presupuesto en {name}")

        seed = args.seed_scip + replica
        conditions = ("default", "warm_start") if replica % 2 == 0 else ("warm_start", "default")
        runs = {}
        for condition in conditions:
            runs[condition] = run_scip(
                path, condition, assignment if condition == "warm_start" else None,
                args.presupuesto - heuristic_time if condition == "warm_start" else args.presupuesto,
                seed,
            )
        default, warm = runs["default"], runs["warm_start"]
        if not warm["warm_accepted"]:
            raise RuntimeError(f"Warm start rechazado por SCIP en {name}")
        reference = min(x["mejor_objetivo"] for x in (default, warm)
                        if x["mejor_objetivo"] is not None)
        for run, cost in ((default, 0.0), (warm, heuristic_time)):
            run["tiempo_heuristica_s"] = cost
            run["presupuesto_total_s"] = args.presupuesto
            run["tiempo_pipeline_s"] = cost + run["tiempo_scip_s"]
            run["primal_integral_normalizada"] = normalized_primal_integral(
                run["trayectoria"], run["limite_scip_s"], reference,
            ) if math.isfinite(reference) else None
        pair = {"instancia": name, "orden_condiciones": list(conditions),
                "heuristica_stats": stats.to_dict(),
                "default": default, "warm_start": warm}
        atomic_json(pair_file, pair)
        persist_tables(folder, names)
        print(f"[{name}] default={default['mejor_objetivo']} {default['estado']} "
              f"warm={warm['mejor_objetivo']} {warm['estado']} "
              f"t_heur={heuristic_time:.2f}s", flush=True)
    persist_tables(folder, names)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
