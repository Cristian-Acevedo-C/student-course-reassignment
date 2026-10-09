# -*- coding: utf-8 -*-
"""Genera tablas agregadas reproducibles a partir de los CSV del experimento."""

from __future__ import annotations

import csv
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def mean(rows: list[dict[str, str]], column: str) -> float | None:
    values = [float(row[column]) for row in rows if row.get(column) not in (None, "")]
    return statistics.mean(values) if values else None


def main() -> None:
    output = ROOT / "resultados_resumen"
    output.mkdir(parents=True, exist_ok=True)
    summary = []

    for family in ("L9_P3_C4", "L9_P3_C5", "L9_P3_C6"):
        rows = read_csv(ROOT / "resultados_constructivo" / family / "resultados_constructivo.csv")
        summary.append({
            "experimento": "constructivo",
            "familia": family,
            "condicion": "heuristica",
            "n": len(rows),
            "factibles_o_aceptados": sum(row["factible"] == "True" for row in rows),
            "validados_independientemente": sum(
                row["validador_independiente_factible"] == "True" for row in rows
            ),
            "tiempo_medio_s": mean(rows, "tiempo_total_s"),
            "objetivo_medio": mean(rows, "objetivo"),
            "T_medio": mean(rows, "T"),
            "no_satisfechos_medio": mean(rows, "no_satisfechos"),
            "gap_final_medio": "",
            "primal_integral_medio": "",
        })

    warm_files = {
        "L9_P3_C4_diag5s": ROOT / "resultados_warm_start" / "L9_P3_C4_diag5s" / "comparacion_warm_start.csv",
        "L9_P3_C4_fair12s": ROOT / "resultados_warm_start" / "L9_P3_C4_fair12s" / "comparacion_warm_start.csv",
        "L9_P3_C5_diag3s": ROOT / "resultados_warm_start" / "L9_P3_C5_diag3s" / "comparacion_warm_start.csv",
        "L9_P3_C6_diag3s": ROOT / "resultados_warm_start" / "L9_P3_C6_diag3s" / "comparacion_warm_start.csv",
    }
    for family, path in warm_files.items():
        rows = read_csv(path)
        for condition in ("default", "warm_start"):
            selected = [row for row in rows if row["condicion"] == condition]
            summary.append({
                "experimento": "SCIP",
                "familia": family,
                "condicion": condition,
                "n": len(selected),
                "factibles_o_aceptados": (
                    sum(row["warm_accepted"] == "True" for row in selected)
                    if condition == "warm_start" else ""
                ),
                "validados_independientemente": sum(
                    row["final_validador_independiente"] == "True" for row in selected
                ),
                "tiempo_medio_s": mean(selected, "tiempo_pipeline_s"),
                "objetivo_medio": mean(selected, "mejor_objetivo"),
                "T_medio": mean(selected, "final_T"),
                "no_satisfechos_medio": "",
                "gap_final_medio": mean(selected, "gap_final"),
                "primal_integral_medio": mean(selected, "primal_integral_normalizada"),
            })
            # N puede variar entre familias; calcular insatisfechos desde el nombre de familia.
            n_students = 36 if "C4" in family else 45 if "C5" in family else 54
            summary[-1]["no_satisfechos_medio"] = n_students - mean(selected, "final_suma_z")

    columns = [
        "experimento", "familia", "condicion", "n", "factibles_o_aceptados",
        "validados_independientemente", "tiempo_medio_s", "objetivo_medio", "T_medio",
        "no_satisfechos_medio", "gap_final_medio", "primal_integral_medio",
    ]
    with (output / "resumen_agregado.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(summary)

    fair = read_csv(warm_files["L9_P3_C4_fair12s"])
    by_instance = {}
    for row in fair:
        by_instance.setdefault(row["instancia"], {})[row["condicion"]] = row
    paired_columns = [
        "instancia", "obj_default", "obj_warm", "delta_obj_warm_menos_default",
        "gap_default", "gap_warm", "primer_obj_default", "primer_obj_warm",
        "t_primer_default", "t_primer_warm", "integral_default", "integral_warm",
        "warm_accepted",
    ]
    paired = []
    for instance in sorted(by_instance):
        default = by_instance[instance]["default"]
        warm = by_instance[instance]["warm_start"]
        paired.append({
            "instancia": instance,
            "obj_default": default["mejor_objetivo"],
            "obj_warm": warm["mejor_objetivo"],
            "delta_obj_warm_menos_default": float(warm["mejor_objetivo"]) - float(default["mejor_objetivo"]),
            "gap_default": default["gap_final"], "gap_warm": warm["gap_final"],
            "primer_obj_default": default["calidad_primer_incumbente"],
            "primer_obj_warm": warm["calidad_primer_incumbente"],
            "t_primer_default": default["tiempo_primer_incumbente_s"],
            "t_primer_warm": warm["tiempo_primer_incumbente_s"],
            "integral_default": default["primal_integral_normalizada"],
            "integral_warm": warm["primal_integral_normalizada"],
            "warm_accepted": warm["warm_accepted"],
        })
    with (output / "comparacion_pareada_C4_fair12s.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=paired_columns)
        writer.writeheader()
        writer.writerows(paired)


if __name__ == "__main__":
    main()
