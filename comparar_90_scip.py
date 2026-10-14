#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoría y comparación pareada de 90 corridas NLHPC: base, warm goloso y replay SCIP.

No modifica ninguna corrida ni el modelo. Solo lee CSV existentes.
Uso: python comparar_90_scip.py --raiz ~/student-course-reassignment
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
import math
import sys

CS = (4, 5, 6)
EXPECTED = {f"c_n_9_l_3_s_{c}_i_{i}" for c in CS for i in range(10)}
SPECS = {
    "base": ("base_5cpu_v1", "resultados_familia.csv"),
    "warm": ("warm_5cpu_v2", "resultados_familia.csv"),
    "replay": ("replay_scip_base_5cpu_v1", "resultado_replay.csv"),
}
FIELDNAMES = [
    "instancia", "C", "replica", "sha256_instancia",
    "estado_base", "estado_warm", "estado_replay",
    "optimal_base", "optimal_warm", "optimal_replay",
    "primal_base", "primal_warm", "primal_replay", "dual_base", "dual_warm", "dual_replay",
    "gap_base", "gap_warm", "gap_replay",
    "tiempo_scip_base", "tiempo_scip_warm", "tiempo_scip_replay",
    "tiempo_total_base", "tiempo_total_warm", "tiempo_total_replay",
    "tiempo_previo_base_replay", "tiempo_previo_mas_replay",
    "nodos_base", "nodos_warm", "nodos_replay",
    "auditado_base", "auditado_warm", "auditado_replay",
    "replay_checksol_original", "replay_aceptada_addsol",
    "replay_objetivo_inicial", "replay_costo_previo_excluido",
]


def norm_bool(x):
    if x is None or str(x).strip() == "":
        return None
    v = str(x).strip().lower()
    return True if v in ("true", "1", "yes", "si", "sí") else False if v in ("false", "0", "no") else None


def number(x):
    if x is None or str(x).strip() == "":
        return None
    try:
        f = float(str(x).strip())
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def fld(record, *names):
    for n in names:
        if n in record and str(record[n]).strip() != "":
            return record[n]
    return None


def collect(folder, filename, errors, method):
    result = {}
    if not folder.is_dir():
        errors.append((method, "CARPETA_INEXISTENTE", str(folder)))
        return result
    paths = sorted(folder.rglob(filename))
    for path in paths:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
        except (OSError, UnicodeError, csv.Error) as exc:
            errors.append((method, "ERROR_LECTURA", f"{path}: {exc}"))
            continue
        if len(rows) != 1:
            errors.append((method, "FILAS_CSV", f"{path}: {len(rows)} filas (esperada 1)"))
        for row in rows:
            inst = str(row.get("instancia", "")).strip()
            if not inst:
                errors.append((method, "SIN_INSTANCIA", str(path)))
                continue
            if inst in result:
                errors.append((method, "INSTANCIA_DUPLICADA", f"{inst}: {path}"))
            else:
                result[inst] = row
    missing = sorted(EXPECTED - set(result))
    extra = sorted(set(result) - EXPECTED)
    for inst in missing:
        errors.append((method, "FALTA_INSTANCIA", inst))
    for inst in extra:
        errors.append((method, "INSTANCIA_EXTRA", inst))
    return result


def nearly(a, b, tol=1e-5):
    return a is not None and b is not None and abs(a-b) <= tol * max(1, abs(a), abs(b))


def safe_mean(values):
    v = [x for x in values if x is not None]
    return mean(v) if v else None


def fmt(x, places=2):
    return "ND" if x is None else f"{x:.{places}f}"


def comparison(rows, method1, method2, key):
    better = worse = equal = missing = 0
    for row in rows:
        a, b = number(row[f"{key}_{method1}"]), number(row[f"{key}_{method2}"])
        if a is None or b is None:
            missing += 1
        elif nearly(a, b):
            equal += 1
        elif b < a:
            better += 1
        else:
            worse += 1
    return better, worse, equal, missing


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raiz", type=Path, default=Path.cwd(), help="raíz del repositorio")
    p.add_argument("--salida", type=Path, default=None, help="directorio de análisis")
    a = p.parse_args()
    root = a.raiz.expanduser().resolve()
    out = a.salida.expanduser().resolve() if a.salida else root / "corridas_nlhpc" / "comparacion_3_metodos_5cpu_v1"
    errors = []
    data = {}
    for method, (directory, filename) in SPECS.items():
        path = root / "corridas_nlhpc" / directory / "T3600"
        data[method] = collect(path, filename, errors, method)
        print(f"{method.upper():6s}: {len(data[method])}/30 instancias CSV únicas")
    if any(len(data[m]) != 30 for m in SPECS):
        print("ERROR: faltan o sobran instancias; no se generará comparación parcial.")
        for e in errors: print("  ", *e)
        return 2

    combined = []
    for c in CS:
        for i in range(10):
            inst = f"c_n_9_l_3_s_{c}_i_{i}"
            b, w, r = (data[method][inst] for method in ("base", "warm", "replay"))
            hashes = [fld(rec, "sha256_instancia") for rec in (b, w, r)]
            if any(not h for h in hashes) or len(set(hashes)) != 1:
                errors.append((inst, "HASH_INSTANCIA", str(hashes)))
            for method, rec in (("base", b), ("warm", w), ("replay", r)):
                hilos = number(fld(rec, "hilos"))
                limite = number(fld(rec, "tiempo_limite_seg", "limite_seg"))
                lam0 = number(fld(rec, "lambda_0"))
                lam1 = number(fld(rec, "lambda_1"))
                gapobj = number(fld(rec, "gap_objetivo"))
                if any(v is None for v in (hilos, limite, lam0, lam1, gapobj)):
                    errors.append((inst, "PARAMETROS_INCOMPLETOS", method))
                elif (not nearly(hilos, 5) or not nearly(limite, 3600)
                      or not nearly(lam0, 1) or not nearly(lam1, 1) or not nearly(gapobj, 0)):
                    errors.append((inst, "PARAMETROS_DIFERENTES", f"{method}: hilos={hilos}, limite={limite}, lambdas={lam0}/{lam1}, gap={gapobj}"))
            estado = {method: (fld(rec, "estado_scip", "estado") or "").lower()
                      for method, rec in (("base", b), ("warm", w), ("replay", r))}
            aud_b = norm_bool(fld(b, "solucion_auditada"))
            aud_w = norm_bool(fld(w, "solucion_auditada"))
            aud_r = norm_bool(fld(r, "auditoria_final"))
            check_r = norm_bool(fld(r, "checksol_original"))
            accepted = norm_bool(fld(r, "aceptada_addsol"))
            prior_excluded = norm_bool(fld(r, "costo_previo_no_incluido_en_tiempo_replay"))
            if aud_b is not True or aud_w is not True or aud_r is not True:
                errors.append((inst, "AUDITORIA_NO_CONFIRMADA", f"base={aud_b} warm={aud_w} replay={aud_r}"))
            if accepted is not True or check_r is not True:
                errors.append((inst, "REPLAY_INICIAL_NO_CONFIRMADO", f"checksol={check_r}, addsol={accepted}"))
            if prior_excluded is not True:
                errors.append((inst, "COSTO_REPLAY", f"costo_previo_no_incluido={prior_excluded}"))
            if fld(r, "violaciones_final") not in (None, "[]"):
                errors.append((inst, "VIOLACIONES_REPLAY", str(r["violaciones_final"])))
            if fld(r, "inconsistencias_objetivo_final") not in (None, "[]"):
                errors.append((inst, "INCONSISTENCIAS_REPLAY", str(r["inconsistencias_objetivo_final"])))
            primals = {
                "base": number(fld(b, "primal_bound", "objetivo_incumbente")),
                "warm": number(fld(w, "primal_bound", "objetivo_incumbente")),
                "replay": number(fld(r, "primal_final")),
            }
            original = number(fld(r, "primal_base"))
            initial = number(fld(r, "primal_inicial_scip"))
            if not nearly(original, primals["base"]):
                errors.append((inst, "REPLAY_ORIGEN_DISTINTO", f"primal_base_replay={original}, primal_base_csv={primals['base']}"))
            if not nearly(initial, original):
                errors.append((inst, "REPLAY_INICIAL_DISTINTO", f"inicial={initial}, origen={original}"))
            previous_t = number(fld(r, "tiempo_previo_base_seg"))
            replay_total = number(fld(r, "tiempo_total_seg"))
            row = {"instancia": inst, "C": c, "replica": i, "sha256_instancia": hashes[0]}
            for method, rec in (("base", b), ("warm", w), ("replay", r)):
                row[f"estado_{method}"] = estado[method]
                row[f"optimal_{method}"] = estado[method] == "optimal"
                row[f"primal_{method}"] = primals[method]
                row[f"dual_{method}"] = number(fld(rec, "dual_final" if method == "replay" else "dual_bound"))
                row[f"gap_{method}"] = number(fld(rec, "gap_final" if method == "replay" else "gap"))
                row[f"tiempo_scip_{method}"] = number(fld(rec, "tiempo_scip_seg"))
                row[f"tiempo_total_{method}"] = number(fld(rec, "tiempo_total_seg"))
                row[f"nodos_{method}"] = number(fld(rec, "nodos"))
            row.update({
                "tiempo_previo_base_replay": previous_t,
                "tiempo_previo_mas_replay": previous_t + replay_total if previous_t is not None and replay_total is not None else None,
                "auditado_base": aud_b,
                "auditado_warm": aud_w,
                "auditado_replay": aud_r,
                "replay_checksol_original": check_r,
                "replay_aceptada_addsol": accepted,
                "replay_objetivo_inicial": initial,
                "replay_costo_previo_excluido": prior_excluded,
            })
            combined.append(row)

    out.mkdir(parents=True, exist_ok=True)
    with (out / "consolidado_90.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(combined)
    with (out / "incidencias_90.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["instancia_o_metodo", "tipo", "detalle"])
        writer.writerows(errors)

    report = [
        "ANÁLISIS PAREADO DE 90 CORRIDAS (L=9, P=3; C=4,5,6)",
        "Las tres condiciones usan las mismas 30 instancias; 5 hilos solicitados y 3600 s SCIP.",
        "Los recursos físicamente utilizados no se infieren del parámetro hilos.",
        "REPLAY SCIP REUTILIZA UNA SOLUCIÓN DE UNA CORRIDA ANTERIOR: el tiempo de obtención NO forma parte de su tiempo reportado.",
        "No comparar el tiempo replay como si fuera una heurística independiente.",
        "Óptimo probado = estado_scip 'optimal', no simplemente gap reducido.",
        "",
    ]
    for c in (*CS, None):
        rows = [row for row in combined if c is None or row["C"] == c]
        title = f"C={c}" if c is not None else "TOTAL C=4+5+6"
        report.append(f"===== {title} (n={len(rows)}) =====")
        for method in ("base", "warm", "replay"):
            optimum = sum(row[f"optimal_{method}"] for row in rows)
            valid = sum(row[f"auditado_{method}"] is True for row in rows)
            report.append(
                f"{method:6s}: óptimos {optimum:2d}/{len(rows)}; auditorías {valid:2d}/{len(rows)}; "
                f"primal medio {fmt(safe_mean([row[f'primal_{method}'] for row in rows]))}; "
                f"gap medio {fmt(safe_mean([row[f'gap_{method}'] for row in rows]),3)}; "
                f"tiempo SCIP medio {fmt(safe_mean([row[f'tiempo_scip_{method}'] for row in rows]))}s; "
                f"nodos medios {fmt(safe_mean([row[f'nodos_{method}'] for row in rows]),0)}"
            )
        for m in ("warm", "replay"):
            better, worse, ties, missing = comparison(rows, "base", m, "primal")
            both_opt = [row for row in rows if row["optimal_base"] and row[f"optimal_{m}"]]
            base_t = safe_mean([row["tiempo_scip_base"] for row in both_opt])
            alt_t = safe_mean([row[f"tiempo_scip_{m}"] for row in both_opt])
            report.append(
                f"base vs {m}: objetivos mejores/peores/iguales/sin_dato = {better}/{worse}/{ties}/{missing}; "
                f"ambos óptimos n={len(both_opt)}; t_scip media sobre ambos óptimos base={fmt(base_t)}s y {m}={fmt(alt_t)}s"
            )
        report.append("")
    accepted = sum(row["replay_aceptada_addsol"] is True for row in combined)
    valid_replay = sum(row["replay_checksol_original"] is True for row in combined)
    report += [
        f"REPLAY: checkSol original={valid_replay}/30; addSol aceptado={accepted}/30.",
        f"INCIDENCIAS DE VALIDACIÓN: {len(errors)} (detalles en incidencias_90.csv)",
        "NOTA: Los tiempos de replay no incluyen los costos de las corridas previas usadas para generar el incumbente.",
        "Para costos secuenciales consultar las columnas tiempo_previo_mas_replay de consolidado_90.csv.",
        "Las medias de tiempo no reemplazan análisis de supervivencia/censura si hay timelimits.",
    ]
    result_text = "\n".join(report) + "\n"
    (out / "resumen_90.txt").write_text(result_text, encoding="utf-8")
    print("\n" + result_text)
    print("Archivos creados:")
    for name in ("consolidado_90.csv", "resumen_90.txt", "incidencias_90.csv"):
        print("  ", out / name)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
