# -*- coding: utf-8 -*-
"""
Resuelve instancias en lote y deja el registro del protocolo experimental:

  resultados/resultados.csv      nombre de la instancia, tiempo y gap
  soluciones/sol_<nombre>.txt    la solucion entregada por el solver

Cada instancia se resuelve hasta 3600 segundos. El registro distingue
explicitamente entre optimo demostrado (gap = 0) y corte por tiempo
(gap > 0), que es la informacion que permite leer el experimento.

Uso:
    python resolver_lote.py --instancias instancias --salida resultados
    python resolver_lote.py --instancias instancias --patron "c_n_36_*"
"""
from pathlib import Path
import argparse
import csv
import time
import traceback

from modelo import leer_instancia, construir_modelo, extraer_solucion

COLUMNAS = [
    "instancia", "n", "l", "s", "i", "N",
    "estado", "tiempo_seg", "gap", "limite_seg", "hilos",
    "lambda_0", "lambda_1", "gap_objetivo",
    "objetivo", "cota_dual", "suma_z", "no_satisfechos", "T",
    "nodos", "variables", "restricciones",
]


def parametros_desde_nombre(nombre):
    """c_n_36_l_7_s_4_i_0 -> (36, 7, 4, 0)"""
    p = nombre.split("_")
    try:
        return (int(p[2]), int(p[4]), int(p[6]), int(p[8]))
    except (IndexError, ValueError):
        return (None, None, None, None)


def valor_compatible(fila, campo, actual, predeterminado=None):
    """Compara un parámetro actual con un registro previo del CSV."""
    valor = fila.get(campo)
    if valor in (None, ""):
        return predeterminado is not None and actual == predeterminado
    try:
        return abs(float(valor) - float(actual)) <= 1e-12
    except ValueError:
        return False


def escribir_solucion(ruta, inst, asignacion, resumen):
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        w = f.write
        w(f"# Solucion de la instancia {inst['nombre']}\n")
        w(f"# estado={resumen['estado']}\n")
        w(f"# tiempo_seg={resumen['tiempo_seg']:.2f}\n")
        w(f"# gap={resumen['gap']}\n")
        w(f"# limite_seg={resumen['limite_seg']}  hilos={resumen['hilos']}\n")
        w(f"# lambda_0={resumen['lambda_0']}  lambda_1={resumen['lambda_1']}\n")
        w(f"# gap_objetivo={resumen['gap_objetivo']}\n")
        w(f"# objetivo={resumen['objetivo']}\n")
        w(f"# cota_dual={resumen['cota_dual']}\n")
        w(f"# suma_z={resumen['suma_z']}  no_satisfechos={resumen['no_satisfechos']}\n")
        w(f"# T={resumen['T']}\n\n")

        if asignacion is None:
            w("# El solver no encontro ninguna solucion factible.\n")
            return

        w("[ASIGNACION]\n")
        w("estudiante;curso_asignado\n")
        for i in sorted(asignacion):
            w(f"{i};{asignacion[i]}\n")
        w("\n")

        w("[RESUMEN_POR_CURSO]\n")
        w("curso;total;" + ";".join(f"genero_{g}" for g in inst["grupos_genero"])
          + ";" + ";".join(f"origen_{o}" for o in inst["cursos_origen"]) + "\n")
        est = inst["estudiantes"]
        for c in inst["cursos"]:
            miembros = [i for i in asignacion if asignacion[i] == c]
            fila = [str(c), str(len(miembros))]
            fila += [str(sum(1 for i in miembros if est[i]["genero"] == g))
                     for g in inst["grupos_genero"]]
            fila += [str(sum(1 for i in miembros if est[i]["origen"] == o))
                     for o in inst["cursos_origen"]]
            w(";".join(fila) + "\n")


def resolver_una(ruta, dir_soluciones, tiempo, hilos, gap, lambda_0, lambda_1):
    inst = leer_instancia(ruta)
    n, l, s, i = parametros_desde_nombre(inst["nombre"])

    m, vars_ = construir_modelo(
        inst, lambda_0=lambda_0, lambda_1=lambda_1,
        tiempo=tiempo, hilos=hilos, gap=gap,
    )

    t0 = time.perf_counter()
    m.optimize()
    transcurrido = time.perf_counter() - t0

    estado = m.getStatus()
    asignacion, suma_z, valor_T, _ = extraer_solucion(m, vars_, inst)

    if m.getNSols() > 0:
        objetivo = m.getObjVal()
        cota = m.getDualbound()
        gap_final = m.getGap()
    else:
        objetivo = cota = gap_final = None

    resumen = {
        "instancia": inst["nombre"],
        "n": n, "l": l, "s": s, "i": i, "N": inst["N"],
        "estado": estado,
        "tiempo_seg": round(transcurrido, 2),
        "gap": None if gap_final is None else round(gap_final, 8),
        "limite_seg": tiempo,
        "hilos": hilos,
        "lambda_0": lambda_0,
        "lambda_1": lambda_1,
        "gap_objetivo": gap,
        "objetivo": None if objetivo is None else round(objetivo, 6),
        "cota_dual": None if cota is None else round(cota, 6),
        "suma_z": suma_z,
        "no_satisfechos": None if suma_z is None else inst["N"] - suma_z,
        "T": None if valor_T is None else round(valor_T, 6),
        "nodos": m.getNTotalNodes(),
        "variables": m.getNVars(),
        "restricciones": m.getNConss(),
    }

    dir_soluciones.mkdir(parents=True, exist_ok=True)
    escribir_solucion(
        dir_soluciones / f"sol_{inst['nombre']}.txt", inst, asignacion, resumen
    )
    return resumen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instancias", default="instancias")
    ap.add_argument("--salida", default="resultados")
    ap.add_argument("--soluciones", default="soluciones")
    ap.add_argument("--patron", default="c_n_*.txt")
    ap.add_argument("--tiempo", type=float, default=3600.0,
                    help="limite por instancia en segundos (default 3600)")
    ap.add_argument("--hilos", type=int, default=1)
    ap.add_argument("--gap", type=float, default=0.0)
    ap.add_argument("--lambda-0", type=float, default=1.0)
    ap.add_argument("--lambda-1", type=float, default=1.0)
    ap.add_argument("--rehacer", action="store_true",
                    help="reprocesa instancias que ya tienen solucion")
    a = ap.parse_args()

    if a.tiempo <= 0:
        ap.error("--tiempo debe ser mayor que 0")
    if a.hilos < 1:
        ap.error("--hilos debe ser al menos 1")
    if not 0 <= a.gap <= 1:
        ap.error("--gap debe estar entre 0 y 1")
    if a.lambda_0 < 0 or a.lambda_1 < 0:
        ap.error("los pesos lambda deben ser no negativos")
    if a.lambda_0 == 0 and a.lambda_1 == 0:
        ap.error("al menos uno de los pesos lambda debe ser positivo")

    dir_inst = Path(a.instancias)
    dir_sal = Path(a.salida)
    dir_sol = Path(a.soluciones)
    dir_sal.mkdir(parents=True, exist_ok=True)

    archivos = sorted(dir_inst.glob(a.patron))
    if not archivos:
        print(f"No se encontraron instancias en {dir_inst} con patron {a.patron}")
        return

    # Una instancia se omite SOLO si el registro previo sigue siendo valido
    # para el limite actual: o bien cerro a optimalidad, o bien ya se corrio
    # con un limite de tiempo mayor o igual al pedido ahora. Asi, subir el
    # limite (por ejemplo de una calibracion de 15 s al protocolo de 3600 s)
    # vuelve a resolver lo que habia quedado cortado, en vez de arrastrar
    # resultados de dos protocolos distintos en el mismo CSV.
    csv_ruta = dir_sal / "resultados.csv"
    hechas = set()
    conservadas = []
    obsoletas = 0

    if csv_ruta.exists() and not a.rehacer:
        with open(csv_ruta, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                cerrada = (
                    r.get("estado") == "optimal"
                    and r.get("gap") not in (None, "")
                    and float(r["gap"]) <= 1e-9
                )
                try:
                    limite_previo = float(r.get("limite_seg") or 0)
                except ValueError:
                    limite_previo = 0.0
                mismo_protocolo = (
                    valor_compatible(r, "hilos", a.hilos, 1)
                    and valor_compatible(r, "lambda_0", a.lambda_0, 1.0)
                    and valor_compatible(r, "lambda_1", a.lambda_1, 1.0)
                    and valor_compatible(r, "gap_objetivo", a.gap, 0.0)
                )
                if mismo_protocolo and (cerrada or limite_previo >= a.tiempo):
                    hechas.add(r["instancia"])
                    conservadas.append({c: r.get(c, "") for c in COLUMNAS})
                else:
                    obsoletas += 1

    if obsoletas:
        print(f"Aviso: {obsoletas} registros previos no son compatibles con "
              "el protocolo solicitado. Se descartan y se vuelven a resolver "
              "para no mezclar configuraciones en el mismo CSV.\n")

    # se reescribe el CSV conservando solo los registros vigentes
    with open(csv_ruta, "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        escritor.writeheader()
        for r in conservadas:
            escritor.writerow(r)

    with open(csv_ruta, "a", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)

        for k, ruta in enumerate(archivos, 1):
            nombre = ruta.stem
            if nombre in hechas:
                print(f"[{k}/{len(archivos)}] {nombre}: ya registrada, se omite")
                continue
            print(f"[{k}/{len(archivos)}] {nombre}: resolviendo "
                  f"(limite {a.tiempo:.0f} s)...", flush=True)
            try:
                r = resolver_una(ruta, dir_sol, a.tiempo, a.hilos, a.gap,
                                 a.lambda_0, a.lambda_1)
            except Exception:
                traceback.print_exc()
                r = {c: None for c in COLUMNAS}
                r["instancia"] = nombre
                r["estado"] = "ERROR"
            escritor.writerow(r)
            f.flush()
            print(f"    estado={r['estado']}  tiempo={r['tiempo_seg']} s  "
                  f"gap={r['gap']}  objetivo={r['objetivo']}", flush=True)

    print("\nRegistro:", csv_ruta)
    print("Soluciones:", dir_sol)


if __name__ == "__main__":
    main()
