# -*- coding: utf-8 -*-
"""
Construye, a partir de resultados/resultados.csv, las tablas de reporte
computacional en el estilo de Perez-Galarce et al. (2014), C&OR 47, 114-122:

  Tabla 1  cantidad de instancias resueltas a optimalidad dentro del limite
  Tabla 2  estadisticas de tiempo (Min / Prom / Max) sobre las que cerraron
  Tabla 3  estadisticas de gap sobre las que llegaron al limite de tiempo
  Perfil   % acumulado de instancias resueltas en funcion del tiempo

Cada fila de las tablas es una celda del diseno factorial (n, l, s), que
agrega las 10 replicas i = 0..9.

Uso:
    python analizar_resultados.py --resultados resultados/resultados.csv \
                                  --salida analisis
"""
from pathlib import Path
import argparse
import csv
import statistics as st


def cargar(ruta):
    filas = []
    with open(ruta, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["estado"] in (None, "", "ERROR"):
                continue
            for k in ("n", "l", "s", "i", "N", "nodos", "variables", "restricciones"):
                r[k] = int(r[k]) if r[k] not in (None, "") else None
            for k in ("tiempo_seg", "gap", "objetivo", "cota_dual", "T"):
                r[k] = float(r[k]) if r[k] not in (None, "") else None
            filas.append(r)
    return filas


def es_optima(r):
    return r["estado"] == "optimal" and r["gap"] is not None and r["gap"] <= 1e-9


def fmt(x, dec=2):
    return "-" if x is None else f"{x:.{dec}f}"


def celdas(filas):
    d = {}
    for r in filas:
        d.setdefault((r["n"], r["l"], r["s"]), []).append(r)
    return d


# ----------------------------------------------------------------------
# TABLA 1 - instancias resueltas a optimalidad
# ----------------------------------------------------------------------

def tabla_1(d, salida):
    lineas = []
    lineas.append("Tabla 1. Instancias resueltas a optimalidad dentro del limite de tiempo.")
    lineas.append("Cada celda agrega las replicas disponibles en el registro.\n")
    lineas.append(f"{'n':>4} {'l':>4} {'s':>4} {'N':>6} {'#Opt':>6} {'#Total':>7} {'%Opt':>7}")
    lineas.append("-" * 44)
    for (n, l, s) in sorted(d):
        g = d[(n, l, s)]
        nopt = sum(1 for r in g if es_optima(r))
        lineas.append(
            f"{n:>4} {l:>4} {s:>4} {n*s:>6} {nopt:>6} {len(g):>7} "
            f"{100*nopt/len(g):>6.0f}%"
        )
    texto = "\n".join(lineas)
    (salida / "tabla1_optimalidad.txt").write_text(texto + "\n", encoding="utf-8")
    return texto


# ----------------------------------------------------------------------
# TABLA 2 - estadisticas de tiempo sobre las que cerraron
# ----------------------------------------------------------------------

def tabla_2(d, salida):
    lineas = []
    lineas.append("Tabla 2. Estadisticas de tiempo de ejecucion (segundos) sobre las")
    lineas.append("instancias en que se demostro optimalidad.\n")
    lineas.append(f"{'n':>4} {'l':>4} {'s':>4} {'Min':>10} {'Prom':>10} "
                  f"{'Mediana':>10} {'Max':>10} {'#Opt':>6}")
    lineas.append("-" * 70)
    for (n, l, s) in sorted(d):
        t = [r["tiempo_seg"] for r in d[(n, l, s)] if es_optima(r)]
        if t:
            lineas.append(
                f"{n:>4} {l:>4} {s:>4} {fmt(min(t)):>10} {fmt(st.mean(t)):>10} "
                f"{fmt(st.median(t)):>10} {fmt(max(t)):>10} {len(t):>6}"
            )
        else:
            lineas.append(f"{n:>4} {l:>4} {s:>4} {'-':>10} {'-':>10} "
                          f"{'-':>10} {'-':>10} {0:>6}")
    texto = "\n".join(lineas)
    (salida / "tabla2_tiempos.txt").write_text(texto + "\n", encoding="utf-8")
    return texto


# ----------------------------------------------------------------------
# TABLA 3 - gaps de las que llegaron al limite
# ----------------------------------------------------------------------

def tabla_3(d, salida):
    lineas = []
    lineas.append("Tabla 3. Estadisticas del gap (%) sobre las instancias que")
    lineas.append("alcanzaron el limite de tiempo sin demostrar optimalidad.\n")
    lineas.append(f"{'n':>4} {'l':>4} {'s':>4} {'GapProm':>10} {'GapMax':>10} "
                  f"{'#NOpt':>7} {'#SinSol':>8}")
    lineas.append("-" * 58)
    hay = False
    for (n, l, s) in sorted(d):
        g = d[(n, l, s)]
        abiertas = [r for r in g if not es_optima(r)]
        if not abiertas:
            continue
        hay = True
        gaps = [100 * r["gap"] for r in abiertas if r["gap"] is not None]
        sin_sol = sum(1 for r in abiertas if r["objetivo"] is None)
        lineas.append(
            f"{n:>4} {l:>4} {s:>4} "
            f"{fmt(st.mean(gaps)) if gaps else '-':>10} "
            f"{fmt(max(gaps)) if gaps else '-':>10} "
            f"{len(abiertas):>7} {sin_sol:>8}"
        )
    if not hay:
        lineas.append("(todas las instancias cerraron dentro del limite)")
    texto = "\n".join(lineas)
    (salida / "tabla3_gaps.txt").write_text(texto + "\n", encoding="utf-8")
    return texto


# ----------------------------------------------------------------------
# EFECTO MARGINAL - la pregunta del experimento
# ----------------------------------------------------------------------

def efecto_marginal(filas, salida):
    """Aisla el efecto de l y de s sobre el tiempo, promediando el otro factor."""
    lineas = []
    lineas.append("Efecto marginal de cada factor sobre el tiempo de ejecucion.")
    lineas.append("Se promedia sobre los demas factores. Solo instancias cerradas.\n")

    for etiqueta, clave in (("DENSIDAD DE PREFERENCIAS (l)", "l"),
                            ("FRAGMENTACION EN CURSOS (s)", "s"),
                            ("ALUMNOS POR CURSO (n)", "n")):
        lineas.append(etiqueta)
        lineas.append(f"  {'valor':>6} {'#Opt':>6} {'#Total':>7} {'TiempoProm':>12} "
                      f"{'TiempoMax':>11} {'NodosProm':>12} {'VarsProm':>10}")
        valores = sorted({r[clave] for r in filas})
        for v in valores:
            g = [r for r in filas if r[clave] == v]
            cerradas = [r for r in g if es_optima(r)]
            t = [r["tiempo_seg"] for r in cerradas]
            nod = [r["nodos"] for r in cerradas if r["nodos"] is not None]
            var = [r["variables"] for r in g if r["variables"] is not None]
            lineas.append(
                f"  {v:>6} {len(cerradas):>6} {len(g):>7} "
                f"{fmt(st.mean(t)) if t else '-':>12} "
                f"{fmt(max(t)) if t else '-':>11} "
                f"{fmt(st.mean(nod), 0) if nod else '-':>12} "
                f"{fmt(st.mean(var), 0) if var else '-':>10}"
            )
        lineas.append("")

    lineas.append("Lectura: si al subir l el tiempo crece pero los NODOS se mantienen,")
    lineas.append("el costo viene del tamano del modelo. Si al subir s explotan los")
    lineas.append("NODOS, el costo viene del arbol de busqueda (simetria entre cursos).")
    texto = "\n".join(lineas)
    (salida / "efecto_marginal.txt").write_text(texto + "\n", encoding="utf-8")
    return texto


# ----------------------------------------------------------------------
# PERFIL DE DESEMPENO
# ----------------------------------------------------------------------

def perfil(filas, salida, limite):
    """% acumulado de instancias resueltas en funcion del tiempo."""
    t = sorted(r["tiempo_seg"] for r in filas if es_optima(r))
    total = len(filas)
    ruta = salida / "perfil_desempeno.csv"
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tiempo_seg", "resueltas", "porcentaje_acumulado"])
        for k, seg in enumerate(t, 1):
            w.writerow([round(seg, 2), k, round(100 * k / total, 2)])
    hitos = [1, 10, 60, 300, 600, 1800, limite]
    lineas = ["Perfil de desempeno: % acumulado de instancias resueltas.\n"]
    lineas.append(f"  {'<= seg':>8} {'resueltas':>10} {'% del total':>12}")
    for h in hitos:
        k = sum(1 for x in t if x <= h)
        lineas.append(f"  {h:>8} {k:>10} {100*k/total:>11.1f}%")
    texto = "\n".join(lineas)
    (salida / "perfil_desempeno.txt").write_text(texto + "\n", encoding="utf-8")
    return texto


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resultados", default="resultados/resultados.csv")
    ap.add_argument("--salida", default="analisis")
    ap.add_argument("--limite", type=float, default=3600)
    a = ap.parse_args()

    filas = cargar(a.resultados)
    if not filas:
        print("No hay resultados que analizar.")
        return

    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    d = celdas(filas)

    print(f"Instancias en el registro: {len(filas)}")
    print(f"Celdas (n,l,s) cubiertas : {len(d)} de 36\n")
    for texto in (tabla_1(d, salida), tabla_2(d, salida), tabla_3(d, salida),
                  efecto_marginal(filas, salida), perfil(filas, salida, a.limite)):
        print(texto)
        print("\n" + "=" * 72 + "\n")
    print("Archivos escritos en:", salida)


if __name__ == "__main__":
    main()
