# -*- coding: utf-8 -*-
"""
Compara, replica por replica, el baseline (resolver_familia.py) contra la
corrida con warm start (resolver_familia_warm.py).

Entradas: los resultados_familia.csv (o .txt) de cada condicion. Se pueden dar
varias familias a la vez. El warm_start.csv se busca junto al resultado warm.

Tiempo comparado = tiempo del pipeline:
  base  = tiempo_total_seg
  warm  = tiempo_total_seg + tiempo_constructivo_seg
para no regalarle al warm start el tiempo del constructivo.

Salidas (--salida):
  comparacion_base_warm.csv / .txt   una fila (bloque) por replica, ambas condiciones y deltas
  resumen_base_warm.csv / resumen_base_warm_detalle.txt   una fila (bloque) por C y una global
  resumen_base_warm.txt      tablas legibles + chequeos de consistencia
  tab_base_warm.tex          tabla resumen para el manuscrito

Uso:
  python src/comparar_base_warm.py \
     --base  corridas/prueba_familia_L9_P3_C4_T3600s/resultados_familia.csv \
     --warm  corridas/warm_familia_L9_P3_C4_T3600s/resultados_familia.csv \
     --salida comparacion_warm
"""
from pathlib import Path
import argparse
import csv
import math
import statistics as st

TOL = 1e-6
DESPLAZAMIENTO = 10.0  # media geometrica desplazada (estandar MIPLIB)


# ----------------------------------------------------------------------
# lectura
# ----------------------------------------------------------------------

def leer_familia(ruta):
    """Filas de resultados_familia.csv o de su gemelo .txt."""
    ruta = Path(ruta)
    if ruta.is_dir():
        ruta = ruta / "resultados_familia.csv"
    if ruta.suffix == ".csv" and ruta.exists():
        with open(ruta, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f)), ruta
    txt = ruta.with_suffix(".txt")
    filas, actual = [], None
    for linea in txt.read_text(encoding="utf-8").splitlines():
        s = linea.strip()
        if s.startswith("[") and s.endswith("]"):
            actual = {}
            filas.append(actual)
        elif actual is not None and " = " in s:
            k, v = s.split(" = ", 1)
            actual[k.strip()] = "" if v.strip() == "NO DISPONIBLE" else v.strip()
    return [r for r in filas if r.get("instancia")], txt


def leer_ws(ruta_resultados):
    ruta = Path(ruta_resultados).parent / "warm_start.csv"
    if not ruta.exists():
        return {}
    with open(ruta, encoding="utf-8", newline="") as f:
        return {r["instancia"]: r for r in csv.DictReader(f)}


def f(x):
    if x in (None, ""):
        return None
    try:
        v = float(x)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


# ----------------------------------------------------------------------

def condicion(r, ws=None):
    t_ws = f(ws.get("tiempo_constructivo_seg")) if ws else None
    t = f(r.get("tiempo_total_seg"))
    return {
        "estado": r.get("estado", ""),
        "tiempo": None if t is None else t + (t_ws or 0.0),
        "tiempo_scip": f(r.get("tiempo_scip_seg")),
        "primal": f(r.get("primal_bound")),
        "dual_raiz": f(r.get("dual_bound_raiz")),
        "dual": f(r.get("dual_bound")),
        "gap": f(r.get("gap")),
        "nodos": None if f(r.get("nodos")) is None else int(f(r.get("nodos"))),
        "t_mejor": f(r.get("tiempo_mejor_incumbente_final")),
        "auditada": r.get("solucion_auditada", ""),
        "objetivo_ws": f(ws.get("objetivo_recalculado")) if ws else None,
        "t_constructivo": t_ws,
        "limite": f(r.get("limite_seg")),
    }


def clasificar(b, w):
    ob, ow = b["estado"] == "optimal", w["estado"] == "optimal"
    if ob and ow:
        if b["tiempo"] is None or w["tiempo"] is None:
            return "ambos cierran"
        if w["tiempo"] < b["tiempo"] - TOL:
            return "ambos cierran: warm mas rapido"
        if w["tiempo"] > b["tiempo"] + TOL:
            return "ambos cierran: warm mas lento"
        return "ambos cierran: empate"
    if ow:
        return "solo warm cierra"
    if ob:
        return "solo base cierra"
    if None in (b["primal"], w["primal"]):
        return "ninguno cierra"
    if w["primal"] < b["primal"] - TOL:
        return "ninguno cierra: warm mejor primal"
    if w["primal"] > b["primal"] + TOL:
        return "ninguno cierra: warm peor primal"
    if (w["dual"] or 0) > (b["dual"] or 0) + TOL:
        return "ninguno cierra: mismo primal, warm mejor dual"
    if (w["dual"] or 0) < (b["dual"] or 0) - TOL:
        return "ninguno cierra: mismo primal, warm peor dual"
    return "ninguno cierra: igual"


def geo(xs, s=DESPLAZAMIENTO):
    xs = [x for x in xs if x is not None]
    return math.exp(sum(math.log(x + s) for x in xs) / len(xs)) - s if xs else None


def media(xs):
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else None


def prueba_signo(gana, pierde):
    """p-valor exacto, dos colas, de la prueba de signo (empates excluidos)."""
    n = gana + pierde
    if n == 0:
        return None
    k = min(gana, pierde)
    cola = sum(math.comb(n, j) for j in range(k + 1)) / 2 ** n
    return min(1.0, 2 * cola)


def valor_txt(v):
    if v is None or v == "":
        return "NO DISPONIBLE"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        if math.isinf(v):
            return "inf" if v > 0 else "-inf"
        return repr(round(v, 6))
    return str(v)


def escribir_txt(ruta, titulo, filas, clave):
    """Gemelo .txt de un CSV, en el formato de resultados_familia.txt:
    un bloque [clave] por fila y una linea 'campo = valor' por columna."""
    lineas = [titulo, "NO DISPONIBLE corresponde a una celda vacia del CSV."]
    for r in filas:
        lineas += ["", f"[{r[clave]}]"] + [f"{k} = {valor_txt(v)}" for k, v in r.items()]
    Path(ruta).write_text("\n".join(lineas) + "\n", encoding="utf-8")


def fmt(v, d=2):
    return "-" if v is None else f"{v:.{d}f}"


# ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", nargs="+", required=True)
    ap.add_argument("--warm", nargs="+", required=True)
    ap.add_argument("--salida", default="comparacion_warm")
    a = ap.parse_args()
    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)

    base, warm, ws, avisos = {}, {}, {}, []
    for r_ in a.base:
        filas, origen = leer_familia(r_)
        for r in filas:
            base[r["instancia"]] = r
    for r_ in a.warm:
        filas, origen = leer_familia(r_)
        ws.update(leer_ws(origen))
        for r in filas:
            warm[r["instancia"]] = r

    sin_warm = sorted(set(base) - set(warm))
    sin_base = sorted(set(warm) - set(base))
    if sin_warm:
        avisos.append(f"PENDIENTE warm ({len(sin_warm)}): {', '.join(sin_warm)}")
    if sin_base:
        avisos.append(f"SIN BASELINE ({len(sin_base)}): {', '.join(sin_base)}")

    pares = []
    for inst in sorted(set(base) & set(warm)):
        rb, rw = base[inst], warm[inst]
        if rb.get("sha256_instancia") and rw.get("sha256_instancia") \
                and rb["sha256_instancia"] != rw["sha256_instancia"]:
            avisos.append(f"INSTANCIA DISTINTA {inst}: sha256 no coincide")
        for k in ("limite_seg", "hilos", "gap_objetivo", "lambda_0", "lambda_1"):
            if f(rb.get(k)) != f(rw.get(k)):
                avisos.append(f"PROTOCOLO DISTINTO {inst}: {k} base={rb.get(k)} warm={rw.get(k)}")
        if inst not in ws:
            avisos.append(f"SIN REGISTRO DE WARM START {inst}: no se puede sumar el constructivo")
        b, w = condicion(rb), condicion(rw, ws.get(inst))

        # consistencia: dos optimos iguales; ningun primal bajo la cota del otro
        if b["estado"] == w["estado"] == "optimal" and abs(b["primal"] - w["primal"]) > TOL:
            avisos.append(f"INCONSISTENCIA {inst}: optimos distintos base={b['primal']} warm={w['primal']}")
        for n1, c1, n2, c2 in (("base", b, "warm", w), ("warm", w, "base", b)):
            if c1["primal"] is not None and c2["dual"] is not None and c1["primal"] < c2["dual"] - TOL:
                avisos.append(f"INCONSISTENCIA {inst}: primal {n1}={c1['primal']} < dual {n2}={c2['dual']}")
        for n_, c_ in (("base", b), ("warm", w)):
            if c_["auditada"] not in ("TRUE", "True", "true", ""):
                avisos.append(f"AUDITORIA {inst} [{n_}]: {c_['auditada']}")

        p = rb["instancia"].split("_")
        pares.append({
            "instancia": inst, "C": int(p[6]), "replica": int(p[8]),
            "clasificacion": clasificar(b, w),
            **{f"base_{k}": v for k, v in b.items()
               if k not in ("objetivo_ws", "t_constructivo")},
            **{f"warm_{k}": v for k, v in w.items()},
            "delta_tiempo": None if None in (b["tiempo"], w["tiempo"]) else w["tiempo"] - b["tiempo"],
            "razon_tiempo_base_sobre_warm":
                (b["tiempo"] / w["tiempo"]) if (b["estado"] == w["estado"] == "optimal"
                                                and w["tiempo"]) else None,
            "delta_primal": None if None in (b["primal"], w["primal"]) else w["primal"] - b["primal"],
            "delta_dual": None if None in (b["dual"], w["dual"]) else w["dual"] - b["dual"],
            "delta_gap_abs": (None if None in (b["primal"], b["dual"], w["primal"], w["dual"])
                              else (w["primal"] - w["dual"]) - (b["primal"] - b["dual"])),
            "delta_nodos": None if None in (b["nodos"], w["nodos"]) else w["nodos"] - b["nodos"],
        })

    if not pares:
        raise SystemExit("No hay replicas con ambas condiciones.\n" + "\n".join(avisos))

    with open(out / "comparacion_base_warm.csv", "w", encoding="utf-8", newline="") as fh:
        w_ = csv.DictWriter(fh, fieldnames=list(pares[0]))
        w_.writeheader()
        w_.writerows(pares)
    escribir_txt(out / "comparacion_base_warm.txt",
                 "COMPARACION BASE vs WARM POR REPLICA - mismos campos que comparacion_base_warm.csv",
                 pares, "instancia")

    # --- resumen por C y global ----------------------------------------
    grupos = [(str(C), [p for p in pares if p["C"] == C]) for C in sorted({p["C"] for p in pares})]
    grupos.append(("todas", pares))
    resumen = []
    for nombre, ps in grupos:
        # Ganar en tiempo = resolver (probar optimo) antes. Una corrida que no
        # cierra cuenta con tiempo infinito; si ninguna cierra, es empate.
        def t_res(p, c):
            return p[f"{c}_tiempo"] if p[f"{c}_estado"] == "optimal" else math.inf
        gt = sum(1 for p in ps if t_res(p, "warm") < t_res(p, "base") - TOL)
        pt = sum(1 for p in ps if t_res(p, "warm") > t_res(p, "base") + TOL)
        gp = sum(1 for p in ps if p["delta_primal"] is not None and p["delta_primal"] < -TOL)
        pp = sum(1 for p in ps if p["delta_primal"] is not None and p["delta_primal"] > TOL)
        gd = sum(1 for p in ps if p["delta_dual"] is not None and p["delta_dual"] > TOL)
        pd = sum(1 for p in ps if p["delta_dual"] is not None and p["delta_dual"] < -TOL)
        resumen.append({
            "C": nombre, "pares": len(ps),
            "optimas_base": sum(p["base_estado"] == "optimal" for p in ps),
            "optimas_warm": sum(p["warm_estado"] == "optimal" for p in ps),
            "solo_warm_cierra": sum(p["clasificacion"] == "solo warm cierra" for p in ps),
            "solo_base_cierra": sum(p["clasificacion"] == "solo base cierra" for p in ps),
            "tiempo_geo_base": geo([p["base_tiempo"] for p in ps]),
            "tiempo_geo_warm": geo([p["warm_tiempo"] for p in ps]),
            "warm_resuelve_antes": gt, "warm_resuelve_despues": pt,
            "p_signo_tiempo": prueba_signo(gt, pt),
            "primal_medio_base": media([p["base_primal"] for p in ps]),
            "primal_medio_warm": media([p["warm_primal"] for p in ps]),
            "warm_mejor_primal": gp, "warm_peor_primal": pp,
            "dual_medio_base": media([p["base_dual"] for p in ps]),
            "dual_medio_warm": media([p["warm_dual"] for p in ps]),
            "warm_mejor_dual": gd, "warm_peor_dual": pd,
            "gap_medio_base": media([p["base_gap"] for p in ps]),
            "gap_medio_warm": media([p["warm_gap"] for p in ps]),
            "nodos_medio_base": media([p["base_nodos"] for p in ps]),
            "nodos_medio_warm": media([p["warm_nodos"] for p in ps]),
            "objetivo_ws_medio": media([p["warm_objetivo_ws"] for p in ps]),
        })
    with open(out / "resumen_base_warm.csv", "w", encoding="utf-8", newline="") as fh:
        w_ = csv.DictWriter(fh, fieldnames=list(resumen[0]))
        w_.writeheader()
        w_.writerows(resumen)
    escribir_txt(out / "resumen_base_warm_detalle.txt",
                 "RESUMEN BASE vs WARM POR FAMILIA - mismos campos que resumen_base_warm.csv",
                 [{"grupo": f"C={r['C']}", **r} for r in resumen], "grupo")

    # --- texto -----------------------------------------------------------
    L = ["COMPARACION BASELINE vs WARM START (constructivo)", "",
         "Tiempo = pipeline (warm incluye el constructivo). Media geometrica "
         f"desplazada s={DESPLAZAMIENTO:.0f} s; las cortadas por tiempo entran con su tiempo.",
         "Gap = gap relativo de SCIP (fraccion). Delta = warm - base.", "",
         "POR REPLICA"]
    enc = (f"{'instancia':<20}{'base':>9}{'t_base':>9}{'P':>7}{'D':>7}"
           f"{'warm':>9}{'t_warm':>9}{'ws':>7}{'P':>7}{'D':>7}  clasificacion")
    L += [enc, "-" * len(enc)]
    abrev = {"optimal": "opt", "timelimit_with_incumbent": "TL",
             "timelimit_without_incumbent": "TL-sin", "infeasible": "infact"}
    for p in pares:
        L.append(
            f"{p['instancia']:<20}{abrev.get(p['base_estado'], p['base_estado']):>9}"
            f"{fmt(p['base_tiempo'], 1):>9}{fmt(p['base_primal']):>7}{fmt(p['base_dual']):>7}"
            f"{abrev.get(p['warm_estado'], p['warm_estado']):>9}{fmt(p['warm_tiempo'], 1):>9}"
            f"{fmt(p['warm_objetivo_ws']):>7}{fmt(p['warm_primal']):>7}{fmt(p['warm_dual']):>7}"
            f"  {p['clasificacion']}")
    L += ["", "RESUMEN"]
    for r in resumen:
        L += [f"[C={r['C']}] pares={r['pares']}  optimas base/warm={r['optimas_base']}/{r['optimas_warm']}"
              f"  solo warm cierra={r['solo_warm_cierra']}  solo base cierra={r['solo_base_cierra']}",
              f"   tiempo geo base={fmt(r['tiempo_geo_base'], 1)} s  warm={fmt(r['tiempo_geo_warm'], 1)} s"
              f"  warm resuelve antes/despues={r['warm_resuelve_antes']}/{r['warm_resuelve_despues']}"
              f"  p(signo)={fmt(r['p_signo_tiempo'], 3)}",
              f"   primal medio base={fmt(r['primal_medio_base'])} warm={fmt(r['primal_medio_warm'])}"
              f"  warm mejor/peor={r['warm_mejor_primal']}/{r['warm_peor_primal']}",
              f"   dual medio base={fmt(r['dual_medio_base'])} warm={fmt(r['dual_medio_warm'])}"
              f"  warm mejor/peor={r['warm_mejor_dual']}/{r['warm_peor_dual']}",
              f"   gap medio base={fmt(r['gap_medio_base'], 3)} warm={fmt(r['gap_medio_warm'], 3)}"
              f"  nodos medios base={fmt(r['nodos_medio_base'], 0)} warm={fmt(r['nodos_medio_warm'], 0)}"]
    L += ["", "CHEQUEOS"] + (avisos or ["sin inconsistencias ni pendientes"])
    texto = "\n".join(L) + "\n"
    (out / "resumen_base_warm.txt").write_text(texto, encoding="utf-8")

    # --- LaTeX -------------------------------------------------------------
    T = [r"\begin{tabular}{lrrrrrrrr}", r"\toprule",
         r" & \multicolumn{2}{c}{\#Ópt.} & \multicolumn{2}{c}{$\bar t_{geo}$ (s)} "
         r"& \multicolumn{2}{c}{Primal medio} & \multicolumn{2}{c}{Gap medio (\%)} \\",
         r"$|C|$ & Base & Warm & Base & Warm & Base & Warm & Base & Warm \\", r"\midrule"]
    for r in resumen:
        g = lambda v: fmt(None if v is None else 100 * v, 1)  # noqa: E731
        T.append(f"{r['C']} & {r['optimas_base']} & {r['optimas_warm']} & "
                 f"{fmt(r['tiempo_geo_base'], 1)} & {fmt(r['tiempo_geo_warm'], 1)} & "
                 f"{fmt(r['primal_medio_base'])} & {fmt(r['primal_medio_warm'])} & "
                 f"{g(r['gap_medio_base'])} & {g(r['gap_medio_warm'])} \\\\")
    T += [r"\bottomrule", r"\end{tabular}"]
    (out / "tab_base_warm.tex").write_text("\n".join(T) + "\n", encoding="utf-8")

    print(texto)
    print(f"Archivos en {out.resolve()}")


if __name__ == "__main__":
    main()
