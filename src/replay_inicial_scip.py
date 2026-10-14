#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Experimento C: reinyectar en SCIP un incumbente de la corrida base.

Mantiene intacto src/modelo.py. Verifica identidad SHA-256 de la instancia,
configuracion de la corrida donante y factibilidad original de la solucion
antes de hacer m.optimize(). Abortara si no puede verificar la donacion.

Ejemplo (desde raiz del repositorio):
  ~/venv_scip/bin/python src/replay_inicial_scip.py --L 9 --P 3 --C 4 --replica 0 \
    --base-root corridas_nlhpc/base_5cpu_v1/T3600 \
    --salida corridas_nlhpc/replay_scip_base_5cpu_v1/T60/C4/i0 --tiempo 60 --hilos 5
"""
import argparse
import csv
import hashlib
import json
import math
import sys
import time
from pathlib import Path

from modelo import construir_modelo, leer_instancia
from auditar_solucion import auditar

RAIZ = Path(__file__).resolve().parents[1]

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bool_csv(value):
    return str(value).strip().upper() == "TRUE"


def comprobar_valor(row, key, expected):
    try:
        v = float(row[key])
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError(f"CSV base sin parametro {key} valido") from exc
    if not math.isclose(v, float(expected), abs_tol=1e-8, rel_tol=1e-8):
        raise ValueError(f"Protocolo incompatible: {key}={v}; esperado={expected}")


def cargar_donante(base_root, nombre, args, instancia, out):
    directorio = (base_root / f"C{args.C}" / f"i{args.replica}").resolve()
    csv_src = directorio / "resultados_familia.csv"
    if not csv_src.is_file():
        raise FileNotFoundError(f"No hay CSV de base: {csv_src}")
    with csv_src.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1 or rows[0].get("instancia") != nombre:
        raise ValueError(f"CSV base debe contener solo la replica {nombre}: {csv_src}")
    row = rows[0]
    if row.get("sha256_instancia") != sha256(instancia):
        raise ValueError(f"SHA-256 de la instancia difiere de corrida base: {nombre}")
    if not bool_csv(row.get("tiene_incumbente")):
        raise ValueError(f"La corrida base no tiene incumbente: {nombre}")
    if not bool_csv(row.get("solucion_auditada")) or not bool_csv(row.get("checksol_scip")):
        raise ValueError(f"La solucion donante no esta validada por ambas auditorias: {nombre}")
    for k, v in (("limite_seg", 3600), ("hilos", args.hilos),
                 ("gap_objetivo", 0), ("lambda_0", 1), ("lambda_1", 1)):
        comprobar_valor(row, k, v)

    manifest = directorio / "manifiesto.json"
    if not manifest.is_file():
        raise FileNotFoundError(f"No existe manifiesto base: {manifest}")
    mdata = json.loads(manifest.read_text(encoding="utf-8"))
    sha_modelo_base = mdata.get("fuentes", {}).get("modelo.py")
    sha_modelo_local = sha256(RAIZ / "src" / "modelo.py")
    if not sha_modelo_base or sha_modelo_base != sha_modelo_local:
        raise ValueError("src/modelo.py no coincide con el usado en la corrida base")

    sol_rel = row.get("solucion_completa", "")
    if not sol_rel or Path(sol_rel).is_absolute():
        raise ValueError("Ruta de solucion_completa ausente o absoluta en CSV base")
    sol_file = (directorio / sol_rel).resolve()
    if not sol_file.is_relative_to(directorio) or not sol_file.is_file():
        raise ValueError(f"Solucion donante ausente/fuera del directorio: {sol_file}")

    hashes = json.loads(row.get("artefactos_sha256") or "{}")
    hash_prev = hashes.get("solucion_completa")
    if not hash_prev or hash_prev != sha256(sol_file):
        raise ValueError(f"Hash de archivo .sol no coincide con CSV base: {sol_file}")

    return row, sol_file, {
        "tipo": "incumbente_previo_scip", "instancia": nombre,
        "sha256_instancia": sha256(instancia),
        "origen_csv": str(csv_src), "sha256_csv": sha256(csv_src),
        "origen_solucion": str(sol_file), "sha256_solucion": sha256(sol_file),
        "sha256_modelo": sha_modelo_local,
        "estado_base": row["estado"], "primal_base": row.get("primal_bound"),
        "tiempo_previo_base_seg": row.get("tiempo_total_seg"),
        "costo_previo_no_incluido_en_tiempo_replay": True,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--L", type=int, required=True, choices=(9, 18, 27, 36))
    ap.add_argument("--P", type=int, required=True, choices=(3, 5, 7))
    ap.add_argument("--C", type=int, required=True, choices=(4, 5, 6, 7))
    ap.add_argument("--replica", type=int, required=True, choices=range(10))
    ap.add_argument("--tiempo", type=float, default=3600)
    ap.add_argument("--hilos", type=int, default=5)
    ap.add_argument("--base-root", type=Path, default=RAIZ / "corridas_nlhpc/base_5cpu_v1/T3600")
    ap.add_argument("--salida", type=Path, required=True)
    args = ap.parse_args()

    if args.tiempo <= 0 or args.hilos <= 0:
        ap.error("Tiempo e hilos deben ser positivos")
    nombre = f"c_n_{args.L}_l_{args.P}_s_{args.C}_i_{args.replica}"
    ruta_instancia = RAIZ / "instancias" / f"{nombre}.txt"
    if not ruta_instancia.is_file():
        raise FileNotFoundError(f"Instancia no encontrada: {ruta_instancia}")
    inst = leer_instancia(ruta_instancia)
    if ((inst["L"], inst["P"], inst["C"], inst["N"], inst["nombre"])
            != (args.L, args.P, args.C, args.L * args.C, nombre)):
        raise ValueError("Cabecera de instancia incompatible con nombre/parametros")

    salida = args.salida.resolve()
    if salida.exists() and any(salida.iterdir()):
        raise ValueError(f"Salida no vacia; se preservan los resultados: {salida}")

    inicio = time.perf_counter()
    row_src, sol_file, meta = cargar_donante(args.base_root.resolve(), nombre, args,
                                              ruta_instancia, salida)
    from pyscipopt import __version__ as pyscipopt_version

    m, vars_ = construir_modelo(inst, lambda_0=1.0, lambda_1=1.0,
                                tiempo=args.tiempo, hilos=args.hilos, gap=0.0)
    if "lp/threads" in m.getParams():
        m.setParam("lp/threads", args.hilos)
    m.setParam("parallel/maxnthreads", args.hilos)
    m.setParam("timing/clocktype", 2)
    version_scip = f"{m.getMajorVersion()}.{m.getMinorVersion()}.{m.getTechVersion()}"
    if pyscipopt_version != "6.2.1" or version_scip != "10.0.2":
        raise ValueError(f"Version de SCIP distinta de base: PySCIPOpt {pyscipopt_version} / SCIP {version_scip}")
    meta.update({"pyscipopt": pyscipopt_version, "scip": version_scip,
                 "hilos": args.hilos, "tiempo_limite_seg": args.tiempo,
                 "lambda_0": 1.0, "lambda_1": 1.0, "gap_objetivo": 0.0})

    # NO se optimiza antes de cargar; esta es la solucion completa de SCIP normal.
    t0 = time.perf_counter()
    sol = m.readSolFile(str(sol_file))
    meta["tiempo_lectura_seg"] = time.perf_counter() - t0
    verificada = bool(m.checkSol(sol, printreason=True, completely=True, original=True))
    meta["checksol_original"] = verificada
    meta["primal_inicial_scip"] = m.getSolObjVal(sol)
    if not verificada:
        raise RuntimeError(f"SCIP rechazo factibilidad del archivo donante: {sol_file}")
    if not math.isclose(float(meta["primal_inicial_scip"]), float(row_src["primal_bound"]),
                        abs_tol=1e-4, rel_tol=1e-7):
        raise ValueError("Objetivo donante .sol distinto del CSV original")
    aceptada = bool(m.addSol(sol))
    meta["aceptada_addsol"] = aceptada
    if not aceptada or m.getNSols() < 1:
        raise RuntimeError("La solucion no fue aceptada como incumbente por SCIP")
    meta["tiempo_carga_total_seg"] = time.perf_counter() - t0

    salida.mkdir(parents=True, exist_ok=True)
    m.setLogfile(str(salida / "scip.log"))
    t1 = time.perf_counter()
    m.optimize()
    meta["tiempo_optimizacion_pared_seg"] = time.perf_counter() - t1
    status = str(m.getStatus())
    meta.update({
        "estado_scip": status, "tiempo_scip_seg": m.getSolvingTime(),
        "tiempo_total_seg": time.perf_counter() - inicio,
        "primal_final": m.getPrimalbound(), "dual_final": m.getDualbound(),
        "gap_final": m.getGap(), "nodos": m.getNTotalNodes(),
        "numero_soluciones": m.getNSols(),
    })

    if m.getNSols() > 0:
        final = m.getBestSol()
        comprobado = bool(m.checkSol(final, printreason=True, completely=True, original=True))
        valores_x = {k: m.getSolVal(final, var) for k, var in vars_["x"].items()}
        suma_z = int(round(sum(m.getSolVal(final, var) for var in vars_["z"].values())))
        valor_T = m.getSolVal(final, vars_["T"])
        auditoria = auditar(inst, valores_x, 1.0, 1.0,
                            objetivo_solver=m.getObjVal(), suma_z_solver=suma_z,
                            T_solver=valor_T)
        meta["checksol_final"] = comprobado
        meta["auditoria_final"] = auditoria["solucion_auditada"]
        meta["violaciones_final"] = auditoria["violaciones"]
        meta["inconsistencias_objetivo_final"] = auditoria["inconsistencias_objetivo"]
        if not comprobado or not auditoria["solucion_auditada"]:
            raise RuntimeError("Solucion final no pasa verificacion independiente")
        m.writeBestSol(str(salida / "final.sol"), write_zeros=True)
    else:
        raise RuntimeError("Inconsistencia: desaparecio incumbente cargado")

    m.writeStatistics(str(salida / "stats.txt"))
    m.setLogfile(None)
    m.freeProb()
    meta["tiempo_total_seg"] = time.perf_counter() - inicio
    (salida / "replay_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    campos = list(meta)
    with (salida / "resultado_replay.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict))
                         else v for k, v in meta.items()})
    print(f"OK {nombre}: estado={status}; inicial={meta['primal_inicial_scip']:.6g}; "
          f"final={meta['primal_final']:.6g}; gap={meta['gap_final']:.5g}; "
          f"t_scip={meta['tiempo_scip_seg']:.1f}s; auditada={meta['auditoria_final']}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR replay: {exc}", file=sys.stderr, flush=True)
        raise
