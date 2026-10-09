# -*- coding: utf-8 -*-
"""Consolida checkpoints oficiales y conserva explícitas las réplicas pendientes."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = [
    "instancia", "familia", "presupuesto_s", "estado", "tiempo_constructivo_s",
    "objetivo_constructivo", "warm_aceptado", "base_estado", "base_objetivo",
    "base_cota_dual", "base_gap", "base_tiempo_scip_s", "base_nodos",
    "warm_estado", "warm_objetivo_final", "warm_cota_dual", "warm_gap",
    "warm_tiempo_scip_s", "warm_nodos", "delta_obj_warm_menos_base",
    "base_solucion_validada", "warm_solucion_validada",
]


def rows_from_checkpoints(root: Path) -> list[dict]:
    rows = []
    for family in (4, 5, 6):
        for replica in range(10):
            name = f"c_n_9_l_3_s_{family}_i_{replica}"
            checkpoint = root / f"C{family}_i{replica}" / "pares" / f"{name}.json"
            row = dict.fromkeys(COLUMNS, "")
            row.update(instancia=name, familia=f"L9_P3_C{family}", estado="pendiente")
            if checkpoint.exists():
                pair = json.loads(checkpoint.read_text(encoding="utf-8"))
                base, warm = pair["default"], pair["warm_start"]
                if pair["instancia"] != name or base["instancia"] != name or warm["instancia"] != name:
                    raise ValueError(f"Identidad de instancia inconsistente: {checkpoint}")
                if base["presupuesto_total_s"] != warm["presupuesto_total_s"]:
                    raise ValueError(f"Presupuestos no coinciden: {name}")
                if not warm["warm_accepted"]:
                    raise ValueError(f"Warm start rechazado: {name}")
                row.update({
                    "presupuesto_s": base["presupuesto_total_s"],
                    "estado": "completo",
                    "tiempo_constructivo_s": warm["tiempo_heuristica_s"],
                    "objetivo_constructivo": warm["warm_objetivo"],
                    "warm_aceptado": warm["warm_accepted"],
                    "base_estado": base["estado"],
                    "base_objetivo": base["mejor_objetivo"],
                    "base_cota_dual": base["cota_dual"],
                    "base_gap": base["gap_final"],
                    "base_tiempo_scip_s": base["tiempo_scip_s"],
                    "base_nodos": base["nodos"],
                    "warm_estado": warm["estado"],
                    "warm_objetivo_final": warm["mejor_objetivo"],
                    "warm_cota_dual": warm["cota_dual"],
                    "warm_gap": warm["gap_final"],
                    "warm_tiempo_scip_s": warm["tiempo_scip_s"],
                    "warm_nodos": warm["nodos"],
                    "delta_obj_warm_menos_base": (
                        warm["mejor_objetivo"] - base["mejor_objetivo"]
                        if warm["mejor_objetivo"] is not None and base["mejor_objetivo"] is not None
                        else ""
                    ),
                    "base_solucion_validada": base["final_validador_independiente"],
                    "warm_solucion_validada": warm["final_validador_independiente"],
                })
            rows.append(row)
    return rows


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--raiz", default=str(ROOT / "resultados_warm_start" / "oficial_3600s"))
    p.add_argument("--salida", default=str(ROOT / "resultados_resumen" / "tabla_oficial_3600s.csv"))
    p.add_argument("--exigir-completo", action="store_true")
    args = p.parse_args()
    rows = rows_from_checkpoints(Path(args.raiz))
    out = Path(args.salida)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    completed = sum(r["estado"] == "completo" for r in rows)
    print(f"{completed}/30 pares completos; tabla: {out}")
    return 0 if not args.exigir_completo or completed == 30 else 2


if __name__ == "__main__":
    raise SystemExit(main())
