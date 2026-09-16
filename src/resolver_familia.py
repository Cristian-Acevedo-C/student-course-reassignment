# -*- coding: utf-8 -*-
"""
Resuelve EXACTAMENTE una familia (L, P, C) de la grilla: sus 10 replicas.

Es el ejecutor de la prueba piloto acordada antes de lanzar las 480 instancias.
No modifica la formulacion: usa modelo.leer_instancia y modelo.construir_modelo
tal como estan, con lambda_0 = lambda_1 = 1, gap objetivo 0 y 1 hilo por defecto.
No lee la carpeta testigos/ y no entrega ninguna solucion inicial a SCIP.

Salida (una carpeta por corrida):
  <salida>/
    resultados_familia.csv        una fila por replica
    resultados_familia.txt        los mismos campos por replica, para revision
    resumen_familia.csv           una fila para la familia
    resumen_familia.txt           los mismos estadisticos y parametros
    resumen_familia.md            mismo resumen, con los subconjuntos usados
    resumen_global_familia_L*_P*_C*.txt   detalle de i_0..i_9 y resumen global
    verificacion_familia.txt      chequeo de que las 10 replicas son distintas
    entorno.txt                   hardware, software, parametros y comando
    parametros_scip.set           parametros SCIP distintos del default
    logs/<instancia>.log          log completo de SCIP
    stats/<instancia>.stats       SCIPprintStatistics
    stats/<instancia>.json        estadisticas en JSON
    trayectorias/<instancia>_incumbentes.csv   cada mejora del incumbente
    trayectorias/<instancia>_log.csv           filas de la tabla del log
    soluciones/sol_<instancia>.txt             asignacion auditada

Uso:
    python src/resolver_familia.py --L 9 --P 3 --C 4 --tiempo 3600
    python src/resolver_familia.py --L 9 --P 3 --C 4 --tiempo 60 \
        --replicas 0 --preflight
"""
from pathlib import Path
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import platform
import re
import statistics as st
import subprocess
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modelo import leer_instancia, construir_modelo  # noqa: E402
from auditar_solucion import auditar  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
L_VALORES, P_VALORES, C_VALORES = (9, 18, 27, 36), (3, 5, 7), (4, 5, 6, 7)
REPLICAS_ESPERADAS = 10
PROTOCOLO_OFICIAL = {"tiempo": 3600.0, "hilos": 1, "gap": 0.0,
                     "lambda_0": 1.0, "lambda_1": 1.0}
VERSIONES_OFICIALES = {"pyscipopt": "6.2.1", "scip": "10.0.2"}
ESTADOS_TERMINADOS = {"optimal", "timelimit_with_incumbent",
                     "timelimit_without_incumbent", "infeasible"}

COLUMNAS = [
    # identificacion
    "instancia", "L", "P", "C", "replica", "N", "semilla", "sha256_instancia",
    "modo",
    # estado y tiempos
    "estado", "estado_scip", "tiempo_total_seg", "tiempo_scip_seg",
    "tiempo_presolve_seg", "tiempo_construccion_seg",
    "tiempo_optimizacion_pared_seg",
    # protocolo
    "limite_seg", "hilos", "gap_objetivo", "lambda_0", "lambda_1",
    # cotas
    "tiene_incumbente", "numero_soluciones", "objetivo_incumbente",
    "primal_bound", "dual_bound", "dual_bound_raiz", "gap", "gap_pct",
    "gap_absoluto",
    # componentes del objetivo (segun SCIP)
    "T", "suma_z", "no_satisfechos",
    # arbol y tamano
    "nodos", "variables", "restricciones",
    # primera solucion / mejor incumbente
    "tiempo_primera_solucion_factible", "objetivo_primera_solucion_factible",
    "nodos_primera_solucion", "heuristica_primera_solucion",
    "tiempo_mejor_incumbente_final", "nodos_mejor_incumbente",
    "heuristica_mejor_incumbente", "fuente_tiempos_incumbente",
    # auditoria independiente
    "solucion_auditada", "n_violaciones", "n_inconsistencias_objetivo",
    "satisfechos_recalculado", "T_recalculado", "objetivo_recalculado",
    "checksol_scip",
    # archivos
    "log_scip", "stats_scip", "stats_json", "trayectoria_incumbentes",
    "trayectoria_log", "solucion", "solucion_completa", "auditoria",
    "artefactos_sha256", "error",
]


def clasificar_modo(a):
    protocolo = {k: getattr(a, k) for k in PROTOCOLO_OFICIAL}
    if a.preflight:
        return "preflight"
    if (a.lambda_0, a.lambda_1) != (1.0, 1.0):
        print("ADVERTENCIA: lambda_0 y lambda_1 deben ser exactamente 1 y 1 "
              "para una corrida oficial. Esta corrida es no_oficial.")
    if a.replicas == list(range(REPLICAS_ESPERADAS)) and protocolo == PROTOCOLO_OFICIAL:
        return "oficial"
    return "no_oficial"


def validar_lambdas_oficiales(a, modo, filas=()):
    if modo != "oficial":
        return
    if (a.lambda_0, a.lambda_1) != (1.0, 1.0):
        raise ValueError("Corrida oficial exige lambda_0 = 1 y lambda_1 = 1")
    for r in filas:
        if any(r.get(k) is None or float(r[k]) != 1.0 for k in ("lambda_0", "lambda_1")):
            raise ValueError(f"{r.get('instancia')}: lambdas incompatibles con corrida oficial")


def valor_txt(clave, valor):
    if valor is None or valor == "":
        return "NO DISPONIBLE"
    if clave in ("lambda_0", "lambda_1"):
        valor = float(valor)
        return str(int(valor)) if valor.is_integer() else repr(valor)
    return str(num(valor))


def lineas_lambdas(lambda_0, lambda_1):
    return [f"lambda_0 = {valor_txt('lambda_0', lambda_0)}",
            f"lambda_1 = {valor_txt('lambda_1', lambda_1)}"]


def configurar_scip(m, hilos):
    """Parametros de ejecucion; no cambia variables, restricciones ni objetivo."""
    m.setParam("parallel/maxnthreads", hilos)
    if "lp/threads" in m.getParams():
        m.setParam("lp/threads", hilos)
    m.setParam("timing/clocktype", 2)


def versiones_solver(m):
    import pyscipopt
    return {"pyscipopt": pyscipopt.__version__,
            "scip": f"{m.getMajorVersion()}.{m.getMinorVersion()}.{m.getTechVersion()}"}


def verificar_versiones(m, modo):
    versiones = versiones_solver(m)
    if modo == "oficial" and versiones != VERSIONES_OFICIALES:
        raise ValueError(f"Corrida oficial requiere {VERSIONES_OFICIALES}; instalado: {versiones}")
    return versiones


def escribir_json(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def manifiesto_corrida(a, modo, archivos, m):
    validar_lambdas_oficiales(a, modo)
    return {
        "esquema": 2, "modo": modo, "familia": [a.L, a.P, a.C],
        "replicas": a.replicas,
        "protocolo": {k: getattr(a, k) for k in PROTOCOLO_OFICIAL},
        "versiones": verificar_versiones(m, modo),
        "parametros_scip": {k: m.getParam(k) for k in
                            ("lp/threads", "parallel/maxnthreads", "timing/clocktype")
                            if k in m.getParams()},
        "fuentes": {n: sha256(RAIZ / "src" / n) for n in
                    ("modelo.py", "resolver_familia.py", "auditar_solucion.py")},
        "instancias": {p.stem: sha256(p) for p in archivos},
    }


def cargar_previas(out, manifiesto):
    """Nunca mezcla protocolos, fuentes o entradas; una fila completa exige evidencia."""
    ruta = out / "manifiesto.json"
    if not ruta.exists() or json.loads(ruta.read_text(encoding="utf-8")) != manifiesto:
        raise ValueError("Reanudacion incompatible o sin manifiesto: usa otra -Salida; "
                         "no se mezclan versiones, codigo, instancias ni protocolos.")
    csv_res = out / "resultados_familia.csv"
    if not csv_res.exists():
        return {}
    previas = {}
    with csv_res.open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        if lector.fieldnames != COLUMNAS:
            raise ValueError("CSV de reanudacion incompatible o incompleto")
        for r in lector:
            nombre = r["instancia"]
            if nombre in previas:
                raise ValueError(f"Replica duplicada en CSV: {nombre}")
            if r["estado"] not in ESTADOS_TERMINADOS:
                continue
            if (r["sha256_instancia"] != manifiesto["instancias"].get(nombre)
                    or r["modo"] != manifiesto["modo"]):
                raise ValueError(f"Identidad incompatible en CSV: {nombre}")
            esperados = {"limite_seg": "tiempo", "hilos": "hilos", "gap_objetivo": "gap",
                         "lambda_0": "lambda_0", "lambda_1": "lambda_1"}
            if any(float(r[c]) != manifiesto["protocolo"][p] for c, p in esperados.items()):
                raise ValueError(f"Protocolo incompatible en CSV: {nombre}")
            hashes = json.loads(r["artefactos_sha256"] or "{}")
            requeridos = ["log_scip", "stats_scip", "stats_json", "trayectoria_incumbentes",
                          "trayectoria_log", "solucion", "auditoria"]
            if r["tiene_incumbente"] == "TRUE":
                requeridos.append("solucion_completa")
            completos = True
            for c in requeridos:
                archivo = (out / (r[c] or "")).resolve()
                if (not archivo.is_relative_to(out.resolve()) or not archivo.is_file()
                        or hashes.get(c) != sha256(archivo)):
                    completos = False
                    break
            if completos:
                previas[nombre] = convertir_previa(r)
            else:
                print(f"  {nombre}: artefactos ausentes/modificados; queda pendiente")
    return previas


# ----------------------------------------------------------------------
# utilidades
# ----------------------------------------------------------------------

def sha256(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def num(x, dec=6):
    """Formato para CSV: None -> vacio, infinito -> 'inf'. Nunca convierte None en 0."""
    if x is None:
        return ""
    if isinstance(x, bool):
        return "TRUE" if x else "FALSE"
    if isinstance(x, float):
        if math.isinf(x):
            return "inf" if x > 0 else "-inf"
        if math.isnan(x):
            return "nan"
        return f"{round(x, dec)}"
    return x


def clasificar(estado_scip, n_sols):
    if estado_scip == "optimal":
        return "optimal"
    if estado_scip == "infeasible":
        return "infeasible"
    if estado_scip == "timelimit":
        return "timelimit_with_incumbent" if n_sols > 0 else "timelimit_without_incumbent"
    if estado_scip == "userinterrupt":
        return "interrupted"
    sufijo = "with_incumbent" if n_sols > 0 else "without_incumbent"
    return f"{estado_scip}_{sufijo}"


def nombre_instancia(L, P, C, i):
    return f"c_n_{L}_l_{P}_s_{C}_i_{i}"


# ----------------------------------------------------------------------
# verificacion de la familia (antes de resolver)
# ----------------------------------------------------------------------

def verificar_familia(dir_inst, L, P, C):
    """Aborta si la familia no tiene exactamente 10 replicas distintas."""
    patron = f"c_n_{L}_l_{P}_s_{C}_i_*.txt"
    archivos = sorted(dir_inst.glob(patron),
                      key=lambda p: int(p.stem.rsplit("_", 1)[1]))
    lineas = [f"Familia L={L} P={P} C={C}  patron={patron}",
              f"Archivos encontrados: {len(archivos)}"]
    errores = []

    esperados = {f"{nombre_instancia(L, P, C, i)}.txt" for i in range(REPLICAS_ESPERADAS)}
    encontrados = {p.name for p in archivos}
    if len(archivos) != REPLICAS_ESPERADAS or encontrados != esperados:
        errores.append(
            f"se esperaban exactamente {REPLICAS_ESPERADAS} replicas i=0..9; "
            f"faltan={sorted(esperados - encontrados)} sobran={sorted(encontrados - esperados)}")
        return archivos, lineas, errores

    insts = [leer_instancia(p) for p in archivos]
    hashes = [sha256(p) for p in archivos]

    for p, inst in zip(archivos, insts):
        i = int(p.stem.rsplit("_", 1)[1])
        if (inst["L"], inst["P"], inst["C"], inst["N"]) != (L, P, C, L * C):
            errores.append(f"{p.name}: parametros internos {inst['L'],inst['P'],inst['C'],inst['N']}")
        if inst["nombre"] != p.stem:
            errores.append(f"{p.name}: nombre interno {inst['nombre']}")
        lineas.append(f"  i={i}  semilla={inst['semilla']}  sha256={hashes[archivos.index(p)][:16]}  "
                      f"separaciones={len(inst['separaciones'])}")

    semillas = [inst["semilla"] for inst in insts]
    if len(set(semillas)) != len(semillas):
        errores.append(f"semillas repetidas: {semillas}")
    if len(set(hashes)) != len(hashes):
        errores.append("hay archivos con contenido identico (sha256 repetido)")

    # diferencias reales de contenido entre cada par de replicas
    def huella(inst):
        est = inst["estudiantes"]
        return {
            "perfiles": {i: (e["genero"], e["academico"], e["socioemocional"], e["convivencia"])
                         for i, e in est.items()},
            "prefs": {i: tuple(v) for i, v in inst["preferencias"].items()},
            "seps": set(inst["separaciones"]),
        }
    h = [huella(x) for x in insts]
    lineas.append("\nDiferencias por par de replicas "
                  "(estudiantes con perfil distinto / con lista de preferencias distinta / "
                  "separaciones no compartidas):")
    minimo = {"perfiles": None, "prefs": None, "seps": None}
    for a in range(len(h)):
        for b in range(a + 1, len(h)):
            dp = sum(1 for i in h[a]["perfiles"] if h[a]["perfiles"][i] != h[b]["perfiles"][i])
            dq = sum(1 for i in h[a]["prefs"] if h[a]["prefs"][i] != h[b]["prefs"][i])
            ds = len(h[a]["seps"] ^ h[b]["seps"])
            for k, v in (("perfiles", dp), ("prefs", dq), ("seps", ds)):
                minimo[k] = v if minimo[k] is None else min(minimo[k], v)
            lineas.append(f"  i={a} vs i={b}: perfiles={dp}/{L*C}  preferencias={dq}/{L*C}  "
                          f"separaciones={ds}")
            if dp == 0 and dq == 0 and ds == 0:
                errores.append(f"replicas i={a} e i={b} tienen el mismo contenido")
    lineas.append(f"\nMinimo sobre los 45 pares: perfiles={minimo['perfiles']} "
                  f"preferencias={minimo['prefs']} separaciones={minimo['seps']}")
    return archivos, lineas, errores


# ----------------------------------------------------------------------
# entorno
# ----------------------------------------------------------------------

def cpu_y_ram():
    cpu, ram = platform.processor() or "", None
    try:
        if sys.platform.startswith("win"):
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_Processor | Select-Object -First 1).Name; "
                 "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory; "
                 "(Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum; "
                 "(Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum"],
                capture_output=True, text=True, timeout=30).stdout.strip().splitlines()
            if out:
                cpu = out[0].strip()
                ram = f"{int(out[1]) / 2**30:.1f} GiB" if len(out) > 1 else None
                cpu += f" | nucleos fisicos={out[2].strip()} logicos={out[3].strip()}" if len(out) > 3 else ""
        elif Path("/proc/cpuinfo").exists():
            info = Path("/proc/cpuinfo").read_text()
            m = re.search(r"model name\s*:\s*(.+)", info)
            cpu = (m.group(1) if m else cpu) + f" | logicos={os.cpu_count()}"
            m = re.search(r"MemTotal:\s*(\d+)", Path("/proc/meminfo").read_text())
            ram = f"{int(m.group(1)) / 2**20:.1f} GiB" if m else None
        elif sys.platform == "darwin":
            cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                 capture_output=True, text=True).stdout.strip()
            ram = f"{int(subprocess.run(['sysctl', '-n', 'hw.memsize'], capture_output=True, text=True).stdout) / 2**30:.1f} GiB"
    except Exception as exc:  # el entorno se documenta aunque falle una consulta
        cpu = f"{cpu} (consulta incompleta: {exc})"
    return cpu or "no disponible", ram or "no disponible"


def git_info():
    try:
        h = subprocess.run(["git", "-C", str(RAIZ), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10).stdout.strip()
        sucio = subprocess.run(["git", "-C", str(RAIZ), "status", "--porcelain"],
                               capture_output=True, text=True, timeout=10).stdout.strip()
        return h or "no disponible", ("con cambios locales sin commit" if sucio else "limpio")
    except Exception:
        return "no disponible", "no disponible"


def escribir_entorno(ruta, a, modo, archivos, comando, m_ref):
    validar_lambdas_oficiales(a, modo)
    import pyscipopt
    cpu, ram = cpu_y_ram()
    commit, estado_git = git_info()
    params_set = ruta.parent / "parametros_scip.set"
    m_ref.writeParams(str(params_set), comments=False, onlychanged=True)
    lineas = [
        "ENTORNO DE EJECUCION - prueba de una familia",
        "=" * 60,
        f"fecha_inicio          : {dt.datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"modo                  : {modo}",
        f"familia               : L={a.L} P={a.P} C={a.C} (N={a.L * a.C})",
        f"replicas              : {a.replicas}",
        "",
        f"sistema_operativo     : {platform.platform()}",
        f"maquina               : {platform.node()}",
        f"cpu                   : {cpu}",
        f"ram                   : {ram}",
        f"python                : {sys.version.split()[0]} ({sys.executable})",
        f"pyscipopt             : {pyscipopt.__version__}",
        f"scip                  : {m_ref.getMajorVersion()}.{m_ref.getMinorVersion()}.{m_ref.getTechVersion()}",
        f"OMP_NUM_THREADS       : {os.environ.get('OMP_NUM_THREADS', 'no definido')}",
        "",
        f"limite_seg            : {a.tiempo}",
        f"hilos                 : {a.hilos}",
        f"gap_objetivo          : {a.gap}",
        *lineas_lambdas(a.lambda_0, a.lambda_1),
        "warm_start            : NO (no se llama addSol/readSol; testigos/ no se lee)",
        f"timing/clocktype      : {m_ref.getParam('timing/clocktype')} (1=CPU, 2=reloj de pared)",
        f"lp/threads            : {m_ref.getParams().get('lp/threads', 'no soportado')}",
        f"parallel/maxnthreads  : {m_ref.getParam('parallel/maxnthreads')}",
        f"randomization/randomseedshift : {m_ref.getParam('randomization/randomseedshift')}",
        f"limits/memory (MB)    : {m_ref.getParam('limits/memory')}",
        f"display/freq          : {m_ref.getParam('display/freq')}",
        "",
        f"git_commit            : {commit} ({estado_git})",
        f"sha256 src/modelo.py  : {sha256(RAIZ / 'src' / 'modelo.py')}",
        f"sha256 src/resolver_familia.py : {sha256(Path(__file__))}",
        f"sha256 src/auditar_solucion.py : {sha256(RAIZ / 'src' / 'auditar_solucion.py')}",
        "",
        "instancias (sha256):",
    ]
    lineas += [f"  {p.name}  {sha256(p)}" for p in archivos]
    lineas += ["", "comando:", f"  {comando}", "",
               "parametros SCIP distintos del default (parametros_scip.set):"]
    lineas += ["  " + x for x in params_set.read_text(encoding="utf-8").splitlines() if x.strip()]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------
# extraccion desde estadisticas y log
# ----------------------------------------------------------------------

RE_SOL = re.compile(
    r"^\s*(First Solution|Primal Bound)\s*:\s*([-+0-9.eE]+|infinity|-)\s*"
    r"\(in run \d+, after (\d+) nodes, ([0-9.]+) seconds, depth \d+, found by <([^>]*)>\)")


def leer_stats_solucion(ruta_stats):
    """Lee 'First Solution' y 'Primal Bound' de la seccion Solution de SCIP."""
    out = {}
    if not ruta_stats.exists():
        return out
    for linea in ruta_stats.read_text(encoding="utf-8", errors="replace").splitlines():
        m = RE_SOL.match(linea)
        if m:
            clave = "primera" if m.group(1) == "First Solution" else "mejor"
            out[clave] = {"objetivo": float(m.group(2)), "nodos": int(m.group(3)),
                          "tiempo": float(m.group(4)), "heuristica": m.group(5)}
    return out


def a_segundos(txt):
    txt = txt.strip()
    for suf, f in (("s", 1), ("m", 60), ("h", 3600), ("d", 86400)):
        if txt.endswith(suf):
            return float(txt[:-1]) * f
    return float(txt)


def parsear_log(ruta_log, ruta_csv):
    """Extrae las filas de la tabla de progreso del log de SCIP."""
    filas, cab = [], None
    for linea in ruta_log.read_text(encoding="utf-8", errors="replace").splitlines():
        if "dualbound" in linea and "primalbound" in linea and "|" in linea:
            cab = [c.strip() for c in linea.split("|")]
            continue
        if cab is None or linea.count("|") < len(cab) - 2:
            continue
        partes = linea.split("|")
        if len(partes) != len(cab):
            continue
        heur = linea[0].strip() if linea[:1] not in (" ", "") else ""
        reg = dict(zip(cab, [p.strip() for p in partes]))
        try:
            t = a_segundos(reg["time"].lstrip(heur).strip()) if heur else a_segundos(reg["time"])
        except (KeyError, ValueError):
            continue
        filas.append({"tiempo_seg": t, "nodo": reg.get("node", ""),
                      "abiertos": reg.get("left", ""), "dualbound": reg.get("dualbound", ""),
                      "primalbound": reg.get("primalbound", ""), "gap": reg.get("gap", ""),
                      "marca_heuristica": heur})
    with open(ruta_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["tiempo_seg", "nodo", "abiertos", "dualbound",
                                          "primalbound", "gap", "marca_heuristica"])
        w.writeheader()
        w.writerows(filas)
    return len(filas)


# ----------------------------------------------------------------------
# solucion legible
# ----------------------------------------------------------------------

def escribir_solucion(ruta, inst, fila, aud):
    est, C = inst["estudiantes"], inst["cursos"]
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        w = f.write
        w(f"# Solucion de {inst['nombre']}  (modo={fila['modo']})\n")
        for k in ("estado", "estado_scip", "tiempo_scip_seg", "tiempo_optimizacion_pared_seg", "limite_seg", "hilos",
                  "gap_objetivo", "lambda_0", "lambda_1", "objetivo_incumbente",
                  "dual_bound", "gap", "T", "suma_z", "no_satisfechos", "nodos",
                  "tiempo_primera_solucion_factible", "tiempo_mejor_incumbente_final",
                  "solucion_auditada"):
            if k in ("lambda_0", "lambda_1"):
                w(f"# {k} = {valor_txt(k, fila[k])}\n")
            else:
                w(f"# {k}={fila[k]}\n")
        if aud is None:
            w("\n# SCIP no encontro ninguna solucion factible dentro del limite.\n"
              "# Esto NO demuestra infactibilidad salvo que estado=infeasible.\n")
            return
        asg, sat = aud["asignacion"], aud["preferidos_juntos"]

        w("\n[ASIGNACION]\n")
        w("estudiante;curso_origen;genero;academico;socioemocional;convivencia;"
          "curso_nuevo;preferencias;preferidos_en_mismo_curso;satisfecho\n")
        for i in sorted(est):
            e = est[i]
            w(f"{i};{e['origen']};{e['genero']};{e['academico']};{e['socioemocional']};"
              f"{e['convivencia']};{asg.get(i, '')};"
              f"{','.join(map(str, inst['preferencias'].get(i, [])))};"
              f"{','.join(map(str, sat.get(i, [])))};{1 if sat.get(i) else 0}\n")

        w("\n[COMPOSICION_POR_CURSO]\n")
        cab = (["curso", "total", "capacidad"] + [f"genero_{g}" for g in inst["grupos_genero"]]
               + [f"origen_{o}" for o in inst["cursos_origen"]]
               + [f"{k}_{l}" for k in inst["criterios"] for l in inst["niveles"]]
               + ["satisfechos"])
        w(";".join(cab) + "\n")
        for c in C:
            mi = [i for i in asg if asg[i] == c]
            fila_c = [c, len(mi), inst["capacidad"][c]]
            fila_c += [sum(1 for i in mi if est[i]["genero"] == g) for g in inst["grupos_genero"]]
            fila_c += [sum(1 for i in mi if est[i]["origen"] == o) for o in inst["cursos_origen"]]
            fila_c += [sum(1 for i in mi if est[i][k] == l)
                       for k in inst["criterios"] for l in inst["niveles"]]
            fila_c += [sum(1 for i in mi if sat.get(i))]
            w(";".join(map(str, fila_c)) + "\n")

        w("\n[BALANCE_PERFILES]\n")
        w("criterio;F_recalculado\n")
        for k, v in aud["F_recalculado"].items():
            w(f"{k};{v:.6f}\n")
        w(f"T_recalculado;{aud['T_recalculado']:.6f}\n")

        w("\n[SEPARACIONES]\nestudiante_i;estudiante_j;curso_i;curso_j;respetada\n")
        for a_, b_ in inst["separaciones"]:
            w(f"{a_};{b_};{asg.get(a_)};{asg.get(b_)};{1 if asg.get(a_) != asg.get(b_) else 0}\n")

        w("\n[AUDITORIA]\n")
        w(f"solucion_auditada={'TRUE' if aud['solucion_auditada'] else 'FALSE'}\n")
        w(f"satisfechos_recalculado={aud['satisfechos_recalculado']}\n")
        w(f"objetivo_recalculado={aud['objetivo_recalculado']:.6f}\n")
        w(f"violaciones={len(aud['violaciones'])}\n")
        for v in aud["violaciones"]:
            w(f"  ! {v}\n")
        w(f"inconsistencias_objetivo={len(aud['inconsistencias_objetivo'])}\n")
        for v in aud["inconsistencias_objetivo"]:
            w(f"  ! {v}\n")


# ----------------------------------------------------------------------
# resolver una replica
# ----------------------------------------------------------------------

def resolver_replica(ruta, out, a, modo):
    validar_lambdas_oficiales(a, modo)
    from pyscipopt import SCIP_EVENTTYPE

    inicio_total = time.perf_counter()
    nombre = ruta.stem
    fila = {c: None for c in COLUMNAS}
    rel = lambda p: p.relative_to(out).as_posix()  # noqa: E731
    rutas = {
        "log_scip": out / "logs" / f"{nombre}.log",
        "stats_scip": out / "stats" / f"{nombre}.stats",
        "stats_json": out / "stats" / f"{nombre}.json",
        "trayectoria_incumbentes": out / "trayectorias" / f"{nombre}_incumbentes.csv",
        "trayectoria_log": out / "trayectorias" / f"{nombre}_log.csv",
        "solucion": out / "soluciones" / f"sol_{nombre}.txt",
        "solucion_completa": out / "soluciones" / f"{nombre}.sol",
        "auditoria": out / "auditorias" / f"{nombre}.json",
    }
    for p in rutas.values():
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            p.unlink()

    inst = leer_instancia(ruta)
    fila.update({
        "instancia": nombre, "L": inst["L"], "P": inst["P"], "C": inst["C"],
        "replica": int(nombre.rsplit("_", 1)[1]), "N": inst["N"],
        "semilla": inst["semilla"], "sha256_instancia": sha256(ruta), "modo": modo,
        "limite_seg": a.tiempo, "hilos": a.hilos, "gap_objetivo": a.gap,
        "lambda_0": a.lambda_0, "lambda_1": a.lambda_1,
    })

    t0 = time.perf_counter()
    m, vars_ = construir_modelo(inst, lambda_0=a.lambda_0, lambda_1=a.lambda_1,
                                tiempo=a.tiempo, hilos=a.hilos, gap=a.gap)
    configurar_scip(m, a.hilos)
    verificar_versiones(m, modo)
    fila["tiempo_construccion_seg"] = time.perf_counter() - t0
    fila["variables"] = m.getNVars()
    fila["restricciones"] = m.getNConss()

    # hideOutput(True) en modelo.py solo silencia la consola; setLogfile
    # escribe el log completo igualmente (verificado con SCIP 10.0.2).
    m.setLogfile(str(rutas["log_scip"]))

    incumbentes = []

    def al_mejorar(model, event):
        sol = model.getBestSol()
        incumbentes.append({
            "tiempo_scip_seg": model.getSolvingTime(),
            "objetivo": model.getSolObjVal(sol),
            "dual_bound": model.getDualbound(),
            "nodos": model.getNTotalNodes(),
            "soluciones_encontradas": model.getNSolsFound(),
        })

    m.attachEventHandlerCallback(al_mejorar, [SCIP_EVENTTYPE.BESTSOLFOUND],
                                 name="registro_incumbentes")

    t0 = time.perf_counter()
    m.optimize()
    fila["tiempo_optimizacion_pared_seg"] = time.perf_counter() - t0

    estado_scip = m.getStatus()
    n_sols = m.getNSols()
    fila["estado_scip"] = estado_scip
    fila["estado"] = clasificar(estado_scip, n_sols)
    fila["tiempo_scip_seg"] = m.getSolvingTime()
    fila["tiempo_presolve_seg"] = m.getPresolvingTime()
    fila["nodos"] = m.getNTotalNodes()
    fila["numero_soluciones"] = m.getNSolsFound()
    fila["tiene_incumbente"] = n_sols > 0
    # SCIP representa infinito como +-1e20; se escribe como inf/-inf
    infinito = lambda v: (math.copysign(math.inf, v) if v is not None and abs(v) >= 1e19 else v)  # noqa: E731
    fila["dual_bound"] = infinito(m.getDualbound())
    fila["primal_bound"] = infinito(m.getPrimalbound())
    fila["gap"] = infinito(m.getGap())
    fila["gap_pct"] = 100 * fila["gap"]
    fila["gap_absoluto"] = (fila["primal_bound"] - fila["dual_bound"]
                            if n_sols > 0 else None)
    try:
        fila["dual_bound_raiz"] = infinito(m.getDualboundRoot())
    except Exception:
        fila["dual_bound_raiz"] = None

    m.writeStatistics(str(rutas["stats_scip"]))
    m.writeStatisticsJson(str(rutas["stats_json"]))

    aud = None
    if n_sols > 0:
        sol = m.getBestSol()
        m.writeBestSol(str(rutas["solucion_completa"]), write_zeros=True)
        primal = m.getObjVal()
        fila["objetivo_incumbente"] = primal
        fila["primal_bound"] = m.getPrimalbound()
        g = m.getGap()
        fila["gap"] = math.inf if g >= 1e19 else g
        fila["gap_pct"] = math.inf if g >= 1e19 else 100 * g
        fila["gap_absoluto"] = primal - fila["dual_bound"]
        valores_x = {k: m.getSolVal(sol, v) for k, v in vars_["x"].items()}
        suma_z = int(round(sum(m.getSolVal(sol, v) for v in vars_["z"].values())))
        T = m.getSolVal(sol, vars_["T"])
        fila.update({"T": T, "suma_z": suma_z, "no_satisfechos": inst["N"] - suma_z})
        try:
            fila["checksol_scip"] = bool(m.checkSol(sol, printreason=False, completely=True, original=True))
        except Exception:
            fila["checksol_scip"] = None
        aud = auditar(inst, valores_x, a.lambda_0, a.lambda_1,
                      objetivo_solver=primal, suma_z_solver=suma_z, T_solver=T)
        if fila["checksol_scip"] is not True:
            aud["violaciones"].append("SCIP checkSol no confirma factibilidad de la solucion completa")
            aud["solucion_auditada"] = False
        fila.update({
            "solucion_auditada": aud["solucion_auditada"],
            "n_violaciones": len(aud["violaciones"]),
            "n_inconsistencias_objetivo": len(aud["inconsistencias_objetivo"]),
            "satisfechos_recalculado": aud["satisfechos_recalculado"],
            "T_recalculado": aud["T_recalculado"],
            "objetivo_recalculado": aud["objetivo_recalculado"],
        })
    else:
        fila["solucion_auditada"] = None  # no hay solucion que auditar

    # tiempos de primera solucion y mejor incumbente: dos fuentes independientes
    with open(rutas["trayectoria_incumbentes"], "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["orden", "tiempo_scip_seg", "objetivo",
                                          "dual_bound", "nodos", "soluciones_encontradas"])
        w.writeheader()
        for k, r in enumerate(incumbentes, 1):
            w.writerow({"orden": k, **{c: num(v) for c, v in r.items()}})
    stats = leer_stats_solucion(rutas["stats_scip"])
    if incumbentes:
        fila["tiempo_primera_solucion_factible"] = incumbentes[0]["tiempo_scip_seg"]
        fila["objetivo_primera_solucion_factible"] = incumbentes[0]["objetivo"]
        fila["nodos_primera_solucion"] = incumbentes[0]["nodos"]
        fila["tiempo_mejor_incumbente_final"] = incumbentes[-1]["tiempo_scip_seg"]
        fila["nodos_mejor_incumbente"] = incumbentes[-1]["nodos"]
    if "primera" in stats:
        fila["heuristica_primera_solucion"] = stats["primera"]["heuristica"]
    if "mejor" in stats:
        fila["heuristica_mejor_incumbente"] = stats["mejor"]["heuristica"]
    if incumbentes and "primera" in stats and "mejor" in stats:
        coinciden = (abs(stats["primera"]["tiempo"] - incumbentes[0]["tiempo_scip_seg"]) <= 0.01
                     and abs(stats["primera"]["objetivo"] - incumbentes[0]["objetivo"]) <= 1e-6
                     and abs(stats["mejor"]["objetivo"] - incumbentes[-1]["objetivo"]) <= 1e-6)
        fila["fuente_tiempos_incumbente"] = ("eventhdlr=stats" if coinciden
                                             else "eventhdlr!=stats (revisar log)")
    elif incumbentes or stats:
        fila["fuente_tiempos_incumbente"] = "solo una fuente disponible"

    m.setLogfile(None)  # cierra el archivo de log antes de parsearlo
    parsear_log(rutas["log_scip"], rutas["trayectoria_log"])
    escribir_json(rutas["auditoria"], {"instancia": nombre, "estado_scip": estado_scip,
                                      "checksol_scip": fila["checksol_scip"],
                                      "auditoria": aud,
                                      "motivo": None if aud else "sin incumbente"})
    m.freeProb()
    fila["tiempo_total_seg"] = time.perf_counter() - inicio_total
    escribir_solucion(rutas["solucion"], inst, {k: num(v) for k, v in fila.items()}, aud)

    for k, p in rutas.items():
        fila[k] = rel(p) if p is not None and p.exists() else None
    fila["artefactos_sha256"] = json.dumps({k: sha256(p) for k, p in rutas.items()
                                          if p is not None and p.is_file()}, sort_keys=True)
    fila["tiempo_total_seg"] = time.perf_counter() - inicio_total
    return fila


# ----------------------------------------------------------------------
# resumen de la familia
# ----------------------------------------------------------------------

def media_sd(valores):
    """Media y desviacion estandar muestral (n-1). None si no hay datos suficientes."""
    if not valores:
        return None, None
    return st.mean(valores), (st.stdev(valores) if len(valores) >= 2 else None)


def escribir_resumen_global(filas, a, modo, out, res):
    """Consolida resultados existentes; no construye ni ejecuta el solver."""
    validar_lambdas_oficiales(a, modo, filas)
    por_instancia = {r["instancia"]: r for r in filas}
    lineas = [f"RESUMEN GLOBAL FAMILIA L={a.L} P={a.P} C={a.C}",
              f"modo: {modo}",
              *lineas_lambdas(res["lambda_0"], res["lambda_1"]),
              "tiempos: segundos; gap relativo: fraccion (1.2 equivale a 120 %)",
              "Desviacion estandar muestral (n-1). NO DISPONIBLE no equivale a cero.",
              "Las replicas sin resultados se muestran como pendientes.", ""]
    campos = [("tiempo_scip_seg", "tiempo_scip_seg"),
              ("tiempo_total_seg", "tiempo_total_seg"),
              ("primal_bound", "primal_bound"), ("dual_bound", "dual_bound"),
              ("gap_relativo", "gap"), ("gap_absoluto", "gap_absoluto"),
              ("nodos", "nodos"), ("T", "T"), ("suma_z", "suma_z"),
              ("tiempo_primera_solucion_factible_seg", "tiempo_primera_solucion_factible")]
    mostrar = lambda v: "NO DISPONIBLE" if v is None or v == "" else str(num(v))
    for i in range(REPLICAS_ESPERADAS):
        nombre = nombre_instancia(a.L, a.P, a.C, i)
        r = por_instancia.get(nombre, {})
        lineas += [f"[i_{i}]", f"replica: i_{i}", f"instancia: {nombre}",
                   f"estado: {r.get('estado', 'pendiente')}"]
        lineas += [f"{etiqueta}: {mostrar(r.get(columna))}" for etiqueta, columna in campos]
        auditoria = r.get("solucion_auditada")
        resultado = ("APROBADA" if auditoria is True else "FALLIDA" if auditoria is False
                     else "NO APLICA (sin incumbente)" if r.get("tiene_incumbente") is False
                     else "NO DISPONIBLE")
        lineas += [f"auditoria: {resultado}", ""]

    lineas += ["[RESUMEN FINAL]", f"numero_replicas_esperadas: {REPLICAS_ESPERADAS}"]
    for clave in ("numero_replicas", "numero_optimas", "numero_time_limit_con_incumbente",
                  "numero_time_limit_sin_incumbente", "numero_infeasible_demostradas",
                  "numero_errores", "numero_otros_estados", "familia_completa",
                  "tiempo_scip_promedio_seg", "tiempo_scip_desviacion_estandar_seg",
                  "tiempo_total_promedio_seg", "tiempo_total_desviacion_estandar_seg",
                  "gap_promedio", "gap_desviacion_estandar", "n_tiempo", "n_gap",
                  "n_gap_infinito"):
        lineas.append(f"{clave}: {mostrar(res[clave])}")
    lineas += ["", "Tiempos: replicas terminadas (optimal, timelimit con/sin incumbente, infeasible).",
               "Gap: replicas terminadas con incumbente y gap finito; incluye optimas con gap 0.",
               "Los conteos y estadisticos son los mismos de resumen_familia.csv."]
    ruta = out / f"resumen_global_familia_L{a.L}_P{a.P}_C{a.C}.txt"
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def resumir(filas, a, modo, out):
    validar_lambdas_oficiales(a, modo, filas)
    validas = [r for r in filas if r["estado"] in ESTADOS_TERMINADOS]
    con_inc = [r for r in validas if r["tiene_incumbente"]]
    gap_finito = [r for r in con_inc if r["gap"] is not None and math.isfinite(r["gap"])]
    absoluto_finito = [r for r in con_inc if r["gap_absoluto"] is not None
                       and math.isfinite(r["gap_absoluto"])]
    gap_tl = [r for r in gap_finito if r["estado"] == "timelimit_with_incumbent"]
    primera = [r for r in validas if r["tiempo_primera_solucion_factible"] is not None]

    t_m, t_s = media_sd([r["tiempo_total_seg"] for r in validas])
    ts_m, ts_s = media_sd([r["tiempo_scip_seg"] for r in validas])
    g_m, g_s = media_sd([r["gap"] for r in gap_finito])
    gtl_m, gtl_s = media_sd([r["gap"] for r in gap_tl])
    ga_m, ga_s = media_sd([r["gap_absoluto"] for r in absoluto_finito])
    p_m, p_s = media_sd([r["tiempo_primera_solucion_factible"] for r in primera])
    b_m, b_s = media_sd([r["tiempo_mejor_incumbente_final"] for r in primera])
    n_m, n_s = media_sd([r["nodos"] for r in validas])
    pct = lambda x: None if x is None else 100 * x  # noqa: E731

    res = {
        "modo": modo, "L": a.L, "P": a.P, "C": a.C, "N": a.L * a.C,
        "limite_seg": a.tiempo, "hilos": a.hilos, "gap_objetivo": a.gap,
        "lambda_0": a.lambda_0, "lambda_1": a.lambda_1,
        "numero_replicas": len(filas),
        "numero_pendientes": len(a.replicas) - len(validas),
        "familia_completa": len(validas) == REPLICAS_ESPERADAS,
        "numero_optimas": sum(r["estado"] == "optimal" for r in filas),
        "numero_time_limit_con_incumbente": sum(r["estado"] == "timelimit_with_incumbent" for r in filas),
        "numero_time_limit_sin_incumbente": sum(r["estado"] == "timelimit_without_incumbent" for r in filas),
        "numero_infeasible_demostradas": sum(r["estado"] == "infeasible" for r in filas),
        "numero_errores": sum(r["estado"] == "error" for r in filas),
        "numero_otros_estados": sum(r["estado"] not in (
            "optimal", "timelimit_with_incumbent", "timelimit_without_incumbent",
            "infeasible", "error") for r in filas),
        "numero_soluciones_auditadas_ok": sum(r["solucion_auditada"] is True for r in filas),
        "numero_soluciones_auditoria_fallida": sum(r["solucion_auditada"] is False for r in filas),
        "tiempo_promedio_seg": t_m, "tiempo_desviacion_estandar_seg": t_s,
        "tiempo_total_promedio_seg": t_m, "tiempo_total_desviacion_estandar_seg": t_s,
        "tiempo_scip_promedio_seg": ts_m, "tiempo_scip_desviacion_estandar_seg": ts_s,
        "n_tiempo": len(validas),
        "gap_promedio": g_m, "gap_desviacion_estandar": g_s,
        "gap_promedio_pct": pct(g_m), "gap_desviacion_estandar_pct": pct(g_s),
        "n_gap": len(gap_finito),
        "n_gap_infinito": sum(1 for r in con_inc if r["gap"] is not None and math.isinf(r["gap"])),
        "gap_promedio_solo_timelimit_pct": pct(gtl_m),
        "gap_desviacion_estandar_solo_timelimit_pct": pct(gtl_s),
        "n_gap_solo_timelimit": len(gap_tl),
        "gap_absoluto_promedio": ga_m, "gap_absoluto_desviacion_estandar": ga_s,
        "n_gap_absoluto": len(absoluto_finito),
        "n_gap_absoluto_no_finito": len(con_inc) - len(absoluto_finito),
        "tiempo_primera_factible_promedio": p_m,
        "tiempo_primera_factible_desviacion_estandar": p_s,
        "n_primera_factible": len(primera),
        "tiempo_mejor_incumbente_promedio": b_m,
        "tiempo_mejor_incumbente_desviacion_estandar": b_s,
        "nodos_promedio": n_m, "nodos_desviacion_estandar": n_s, "n_nodos": len(validas),
    }
    with open(out / "resumen_familia.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(res))
        w.writeheader()
        w.writerow({k: num(v) for k, v in res.items()})

    nota = f"""# Resumen de la familia L={a.L}, P={a.P}, C={a.C} (modo: {modo})

Desviacion estandar = muestral (n-1). Un valor vacio significa "sin datos
suficientes"; nunca se reemplaza por cero.

| Estadistica | Subconjunto sobre el que se calcula | n |
|---|---|---|
| tiempo_total_promedio_seg / sd | lectura, construccion, optimizacion y exportacion por replica; estados terminados | {res['n_tiempo']} |
| tiempo_scip_promedio_seg / sd | getSolvingTime(), incluye presolve; mismos estados terminados | {res['n_tiempo']} |
| gap_promedio / sd (y _pct) | replicas con incumbente y gap SCIP finito, incluidas las optimas (gap 0) | {res['n_gap']} |
| gap_promedio_solo_timelimit_pct | solo timelimit con incumbente y gap finito | {res['n_gap_solo_timelimit']} |
| gap_absoluto (primal - dual) | replicas con incumbente y diferencia finita | {res['n_gap_absoluto']} |
| tiempo_primera_factible | replicas donde SCIP encontro al menos una solucion | {res['n_primera_factible']} |
| tiempo_mejor_incumbente | idem | {res['n_primera_factible']} |
| nodos | replicas sin error ni interrupcion | {res['n_nodos']} |

gap SCIP = |primal - dual| / min(|primal|, |dual|). Es infinito si la cota dual
es 0 (salvo ambas cotas iguales) o de distinto signo que la primal; esos casos se cuentan en
n_gap_infinito = {res['n_gap_infinito']} y se excluyen del promedio del gap
relativo. El resumen absoluto usa diferencias finitas y cuenta aparte las no finitas.

tiempo_promedio_seg y tiempo_desviacion_estandar_seg son alias del tiempo total.
Familia completa: {res['familia_completa']}. Pendientes: {res['numero_pendientes']}.

Tiempo de primera solucion: tiempo SCIP (reloj de pared, incluye presolve)
registrado por un manejador del evento BESTSOLFOUND y contrastado con la
linea 'First Solution' de las estadisticas SCIP (columna
fuente_tiempos_incumbente de resultados_familia.csv).
"""
    if modo != "oficial":
        nota += ("\n**ADVERTENCIA:** esta corrida NO cumple el protocolo oficial "
                 "(10 replicas, 3600 s, 1 hilo, gap 0, lambda 1/1). No usar como benchmark.\n")
    (out / "resumen_familia.md").write_text(nota, encoding="utf-8")
    lineas = ["RESUMEN DE FAMILIA - mismos datos que resumen_familia.csv",
              "NO DISPONIBLE corresponde a una celda vacia del CSV.", ""]
    lineas += [f"{k} = {valor_txt(k, v)}" for k, v in res.items()]
    lineas += ["", "Desviacion estandar muestral (n-1).",
               "Tiempos: replicas terminadas (optimal, timelimit con/sin incumbente, infeasible).",
               "Gap: replicas terminadas con incumbente y gap finito; incluye optimas con gap 0."]
    (out / "resumen_familia.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    escribir_resumen_global(filas, a, modo, out, res)
    return res


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--L", type=int, required=True, choices=L_VALORES)
    ap.add_argument("--P", type=int, required=True, choices=P_VALORES)
    ap.add_argument("--C", type=int, required=True, choices=C_VALORES)
    ap.add_argument("--tiempo", type=float, default=None)
    ap.add_argument("--hilos", type=int, default=1)
    ap.add_argument("--gap", type=float, default=0.0)
    ap.add_argument("--lambda-0", type=float, default=1.0)
    ap.add_argument("--lambda-1", type=float, default=1.0)
    ap.add_argument("--instancias", default=str(RAIZ / "instancias"))
    ap.add_argument("--salida", default=None,
                    help="carpeta de salida (default: corridas/prueba_familia_L*_P*_C*_T*s)")
    ap.add_argument("--replicas", type=int, nargs="+", default=None,
                    help="subconjunto de replicas a resolver (solo para preflight)")
    ap.add_argument("--preflight", action="store_true",
                    help="marca la corrida como prueba tecnica; se guarda en corridas/preflight/")
    ap.add_argument("--reanudar", action="store_true",
                    help="conserva replicas ya resueltas con el mismo protocolo en la carpeta")
    ap.add_argument("--comando", default=None, help="comando original (lo pasa correr_familia.ps1)")
    a = ap.parse_args()
    if a.tiempo is None:
        a.tiempo = 60.0 if a.preflight else 3600.0

    if (not all(math.isfinite(v) for v in (a.tiempo, a.gap, a.lambda_0, a.lambda_1))
            or a.tiempo <= 0 or a.hilos < 1 or not 0 <= a.gap <= 1
            or a.lambda_0 < 0 or a.lambda_1 < 0):
        ap.error("parametros invalidos de tiempo, hilos o gap")
    if a.replicas is None:
        a.replicas = [0] if a.preflight else list(range(REPLICAS_ESPERADAS))
    if sorted(set(a.replicas)) != sorted(a.replicas) or any(not 0 <= r < REPLICAS_ESPERADAS for r in a.replicas):
        ap.error("--replicas debe contener valores distintos entre 0 y 9")
    a.replicas = sorted(a.replicas)
    if not a.preflight and a.replicas != list(range(REPLICAS_ESPERADAS)):
        ap.error("una familia requiere exactamente i_0..i_9; subconjuntos solo con --preflight")

    modo = clasificar_modo(a)

    etiqueta = f"prueba_familia_L{a.L}_P{a.P}_C{a.C}_T{a.tiempo:g}s"
    if a.salida:
        out = Path(a.salida)
    elif modo == "preflight":
        reps = "".join(map(str, a.replicas))
        out = RAIZ / "corridas" / "preflight" / f"{etiqueta}_i{reps}"
    else:
        out = RAIZ / "corridas" / etiqueta
    out = out.resolve()

    # 1. verificar la familia completa ANTES de resolver
    archivos, lineas, errores = verificar_familia(Path(a.instancias), a.L, a.P, a.C)
    if errores:
        print("ERROR: la familia no supera la verificacion:")
        for e in errores:
            print("  -", e)
        sys.exit(2)
    print(f"Familia verificada: {len(archivos)} replicas distintas.")

    # Valida tambien el acceso directo por Python, antes de crear salidas.
    from pyscipopt import Model
    ref = Model("protocolo")
    ref.hideOutput(True)
    ref.setParam("limits/time", a.tiempo)
    ref.setParam("limits/gap", a.gap)
    configurar_scip(ref, a.hilos)
    try:
        manifiesto = manifiesto_corrida(a, modo, archivos, ref)
    except ValueError as exc:
        ap.error(str(exc))

    csv_res = out / "resultados_familia.csv"
    previas = {}
    if out.exists() and any(out.iterdir()):
        if not a.reanudar:
            print(f"ERROR: la carpeta de salida ya existe y no esta vacia:\n  {out}\n"
                  "Usa --reanudar para continuar o elige otra --salida. "
                  "No se sobrescriben corridas previas.")
            sys.exit(3)
        try:
            previas = cargar_previas(out, manifiesto)
        except (ValueError, KeyError, TypeError) as exc:
            ap.error(str(exc))
    out.mkdir(parents=True, exist_ok=True)
    if not (out / "manifiesto.json").exists():
        escribir_json(out / "manifiesto.json", manifiesto)
    (out / "verificacion_familia.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")

    comando = a.comando or " ".join([Path(sys.executable).name] + sys.argv)
    # al reanudar se conserva el entorno original y se agrega uno por reanudacion
    ruta_entorno = out / "entorno.txt"
    if ruta_entorno.exists():
        ruta_entorno = out / f"entorno_reanudacion_{dt.datetime.now():%Y%m%d_%H%M%S}.txt"
    escribir_entorno(ruta_entorno, a, modo, archivos, comando, ref)
    ref.freeProb()

    seleccion = [p for p in archivos if int(p.stem.rsplit("_", 1)[1]) in a.replicas]
    print(f"Modo: {modo}.  Replicas pendientes: {len(seleccion) - len(previas)}.  "
          f"Limite: {a.tiempo:g} s.  Salida: {out}\n")

    # Conserva TODAS las terminadas, incluso si se interrumpe una pendiente anterior.
    registros = dict(previas)
    filas = [registros[p.stem] for p in seleccion if p.stem in registros]
    interrumpido = False
    for k, ruta in enumerate(seleccion, 1):
        if ruta.stem in previas:
            print(f"[{k}/{len(seleccion)}] {ruta.stem}: ya resuelta, se conserva")
            continue
        print(f"[{k}/{len(seleccion)}] {ruta.stem}: resolviendo...", flush=True)
        try:
            fila = resolver_replica(ruta, out, a, modo)
        except KeyboardInterrupt:
            print("Interrumpido por el usuario. Las replicas terminadas quedan guardadas.")
            interrumpido = True
            break
        except Exception:
            fila = {c: None for c in COLUMNAS}
            fila.update({"instancia": ruta.stem, "modo": modo, "estado": "error",
                         "lambda_0": a.lambda_0, "lambda_1": a.lambda_1,
                         "error": traceback.format_exc(limit=3).replace("\n", " | ")})
            print(fila["error"])
        registros[ruta.stem] = fila
        filas = [registros[p.stem] for p in seleccion if p.stem in registros]
        escribir_resultados(csv_res, filas, a, modo)
        print(f"    estado={fila['estado']}  t={num(fila['tiempo_total_seg'], 2)} s  "
              f"primal={num(fila['objetivo_incumbente'])}  dual={num(fila['dual_bound'])}  "
              f"gap={num(fila['gap_pct'], 2)}%  1a_sol={num(fila['tiempo_primera_solucion_factible'], 2)} s  "
              f"auditada={num(fila['solucion_auditada'])}", flush=True)
        if fila["estado"] == "interrupted":
            print("SCIP fue interrumpido (Ctrl+C). Se detiene la familia.")
            interrumpido = True
            break

    escribir_resultados(csv_res, filas, a, modo)
    res = resumir(filas, a, modo, out)
    with open(ruta_entorno, "a", encoding="utf-8") as f:
        f.write(f"\nfecha_fin             : {dt.datetime.now().astimezone().isoformat(timespec='seconds')}\n")

    print("\nResumen de la familia:")
    for k in ("numero_replicas", "numero_optimas", "numero_time_limit_con_incumbente",
              "numero_time_limit_sin_incumbente", "numero_infeasible_demostradas",
              "numero_errores", "numero_soluciones_auditadas_ok",
              "tiempo_total_promedio_seg", "tiempo_total_desviacion_estandar_seg",
              "tiempo_scip_promedio_seg", "tiempo_scip_desviacion_estandar_seg",
              "gap_promedio_pct", "gap_desviacion_estandar_pct", "n_gap_infinito",
              "tiempo_primera_factible_promedio", "nodos_promedio"):
        print(f"  {k:40s} {num(res[k], 4)}")
    print(f"\nArchivos en: {out}")
    if interrumpido:
        sys.exit(130)
    if res["numero_soluciones_auditoria_fallida"] or res["numero_errores"]:
        sys.exit(1)
    if res["numero_pendientes"]:
        sys.exit(1)


def escribir_resultados(ruta, filas, a=None, modo=None):
    if a is not None:
        validar_lambdas_oficiales(a, modo, filas)
    temporal = ruta.with_suffix(".csv.tmp")
    with open(temporal, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        for r in filas:
            w.writerow({c: num(r.get(c)) for c in COLUMNAS})
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporal, ruta)
    lineas = ["RESULTADOS DE FAMILIA - mismos campos que resultados_familia.csv",
              "NO DISPONIBLE corresponde a una celda vacia del CSV."]
    if a is not None:
        lineas += [f"modo = {modo}", *lineas_lambdas(a.lambda_0, a.lambda_1)]
    for r in filas:
        lineas += ["", f"[{r.get('instancia', 'replica')}]"]
        lineas += [f"{c} = {valor_txt(c, r.get(c))}" for c in COLUMNAS]
    temporal_txt = ruta.with_suffix(".txt.tmp")
    temporal_txt.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    os.replace(temporal_txt, ruta.with_suffix(".txt"))


def convertir_previa(r):
    """Relee una fila del CSV con tipos numericos para el resumen."""
    out = dict(r)
    for c in ("tiempo_total_seg", "tiempo_scip_seg", "gap", "gap_absoluto", "tiempo_primera_solucion_factible",
              "tiempo_mejor_incumbente_final", "nodos"):
        v = r.get(c, "")
        out[c] = None if v == "" else (int(v) if c == "nodos" else float(v))
    for c in ("tiene_incumbente", "solucion_auditada"):
        out[c] = {"TRUE": True, "FALSE": False}.get(r.get(c, ""), None)
    return out


if __name__ == "__main__":
    main()
