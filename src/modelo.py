# -*- coding: utf-8 -*-
"""
Lector del formato .txt de instancia y construccion del modelo exacto (MILP).

El modelo reproduce la formulacion del manuscrito:
  (7)      asignacion unica
  (8)      capacidad
  (9)      separaciones
  (10-11)  balance de genero
  (12)     representacion por curso de origen
  (13-19)  satisfaccion blanda de preferencias  (y, w, z)
  (20-22)  balance de perfiles                  (d+, d-, F_k, T)
  objetivo  lambda_0 * (|S| - sum z_i) + lambda_1 * T
"""
from pathlib import Path


# ----------------------------------------------------------------------
# LECTURA DEL FORMATO .txt
# ----------------------------------------------------------------------

def leer_instancia(ruta):
    ruta = Path(ruta)
    secciones = {}
    actual = None

    for linea in ruta.read_text(encoding="utf-8").splitlines():
        s = linea.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("[") and s.endswith("]"):
            actual = s[1:-1]
            secciones[actual] = []
            continue
        if actual is not None:
            secciones[actual].append(s)

    def pares(nombre):
        d = {}
        for s in secciones.get(nombre, []):
            if "=" in s:
                k, v = s.split("=", 1)
                d[k.strip()] = v.strip()
        return d

    cab = pares("INSTANCIA")

    inst = {
        "nombre": cab["nombre"],
        "semilla": int(cab["semilla"]),
        "N": int(cab["N"]),
        "C": int(cab["C"]),
        "L": int(cab["L"]),
        "P": int(cab["P"]),
    }

    # cursos destino y capacidades
    capacidad = {}
    for s in secciones["CURSOS_NUEVOS"][1:]:      # se salta el encabezado
        c, cap = s.split(";")
        capacidad[int(c)] = int(cap)
    inst["cursos"] = sorted(capacidad)
    inst["capacidad"] = capacidad

    # balance de genero
    g = pares("BALANCE_GENERO")
    inst["grupos_genero"] = [x.strip() for x in g["grupos"].split(",")]
    inst["delta_genero"] = int(g["diferencia_maxima"])

    # cursos de origen y minimos
    o = pares("CURSOS_ORIGEN")
    inst["cursos_origen"] = [x.strip() for x in o["cursos_origen"].split(",")]
    inst["alpha"] = {
        curso: int(o[f"minimo_{curso}"]) for curso in inst["cursos_origen"]
    }

    # criterios de balance
    cb = pares("CRITERIOS_BALANCE")
    inst["criterios"] = [x.strip() for x in cb["criterios"].split(",")]
    inst["niveles"] = [int(x) for x in cb["niveles"].split(",")]

    # estudiantes
    estudiantes = {}
    for s in secciones["ESTUDIANTES"][1:]:
        eid, origen, genero, ac, se, cv = s.split(";")
        estudiantes[int(eid)] = {
            "origen": origen,
            "genero": genero,
            "academico": int(ac),
            "socioemocional": int(se),
            "convivencia": int(cv),
        }
    inst["estudiantes"] = estudiantes

    # preferencias
    preferencias = {}
    for s in secciones["PREFERENCIAS"][1:]:
        campos = s.split(";")
        preferencias[int(campos[0])] = [int(x) for x in campos[1:] if x]
    inst["preferencias"] = preferencias

    # separaciones
    separaciones = []
    for s in secciones.get("SEPARACIONES", [])[1:]:
        a, b = s.split(";")
        separaciones.append((int(a), int(b)))
    inst["separaciones"] = separaciones

    return inst


# ----------------------------------------------------------------------
# CONSTRUCCION DEL MILP
# ----------------------------------------------------------------------

def construir_modelo(inst, lambda_0=1.0, lambda_1=1.0,
                     tiempo=3600.0, hilos=1, gap=0.0):
    # La importación se difiere para que leer y auditar instancias no requiera
    # tener instalado el solver. PySCIPOpt solo es necesario al resolver.
    from pyscipopt import Model, quicksum

    S = sorted(inst["estudiantes"])
    C = inst["cursos"]
    est = inst["estudiantes"]
    P = inst["preferencias"]

    m = Model(inst["nombre"])
    m.hideOutput(True)
    m.setParam("limits/time", float(tiempo))
    m.setParam("limits/gap", float(gap))
    try:
        m.setParam("parallel/maxnthreads", int(hilos))
    except Exception:
        pass

    # x_ic
    x = {(i, c): m.addVar(vtype="B", name=f"x_{i}_{c}") for i in S for c in C}

    # (7) asignacion unica
    for i in S:
        m.addCons(quicksum(x[i, c] for c in C) == 1)

    # (8) capacidad
    for c in C:
        m.addCons(quicksum(x[i, c] for i in S) <= inst["capacidad"][c])

    # (9) separaciones
    for a, b in inst["separaciones"]:
        for c in C:
            m.addCons(x[a, c] + x[b, c] <= 1)

    # (10)-(11) balance de genero
    delta = inst["delta_genero"]
    for g in inst["grupos_genero"]:
        miembros = [i for i in S if est[i]["genero"] == g]
        for p in range(len(C)):
            for q in range(p + 1, len(C)):
                n1 = quicksum(x[i, C[p]] for i in miembros)
                n2 = quicksum(x[i, C[q]] for i in miembros)
                m.addCons(n1 - n2 <= delta)
                m.addCons(n2 - n1 <= delta)

    # (12) representacion por curso de origen
    for o in inst["cursos_origen"]:
        miembros = [i for i in S if est[i]["origen"] == o]
        for c in C:
            m.addCons(quicksum(x[i, c] for i in miembros) >= inst["alpha"][o])

    # (13)-(19) preferencias blandas
    z, y, w = {}, {}, {}
    for i in S:
        z[i] = m.addVar(vtype="B", name=f"z_{i}")
    for i in S:
        for j in P.get(i, []):
            w[i, j] = m.addVar(vtype="B", name=f"w_{i}_{j}")
            for c in C:
                y[i, j, c] = m.addVar(vtype="B", name=f"y_{i}_{j}_{c}")
                m.addCons(y[i, j, c] <= x[i, c])
                m.addCons(y[i, j, c] <= x[j, c])
                m.addCons(y[i, j, c] >= x[i, c] + x[j, c] - 1)
            m.addCons(w[i, j] == quicksum(y[i, j, c] for c in C))
    for i in S:
        if P.get(i):
            m.addCons(z[i] <= quicksum(w[i, j] for j in P[i]))
            for j in P[i]:
                m.addCons(z[i] >= w[i, j])
        else:
            m.addCons(z[i] == 0)

    # (20)-(22) balance de perfiles
    T = m.addVar(lb=0.0, name="T")
    F = {k: m.addVar(lb=0.0, name=f"F_{k}") for k in inst["criterios"]}
    dp, dm = {}, {}
    for k in inst["criterios"]:
        for l in inst["niveles"]:
            miembros = [i for i in S if est[i][k] == l]
            promedio = len(miembros) / len(C)
            for c in C:
                dp[c, k, l] = m.addVar(lb=0.0, name=f"dp_{c}_{k}_{l}")
                dm[c, k, l] = m.addVar(lb=0.0, name=f"dm_{c}_{k}_{l}")
                cuenta = quicksum(x[i, c] for i in miembros)
                m.addCons(cuenta - promedio == dp[c, k, l] - dm[c, k, l])
        m.addCons(F[k] == quicksum(
            dp[c, k, l] + dm[c, k, l]
            for c in C for l in inst["niveles"]
        ))
        m.addCons(F[k] <= T)

    # objetivo
    m.setObjective(
        lambda_0 * (len(S) - quicksum(z[i] for i in S)) + lambda_1 * T,
        "minimize",
    )

    return m, {"x": x, "z": z, "T": T, "F": F}


def extraer_solucion(m, vars_, inst):
    """Devuelve (asignacion, suma_z, T, F) de la mejor solucion encontrada."""
    if m.getNSols() == 0:
        return None, None, None, None
    sol = m.getBestSol()
    x, z, T, F = vars_["x"], vars_["z"], vars_["T"], vars_["F"]

    asignacion = {}
    for (i, c), v in x.items():
        if m.getSolVal(sol, v) > 0.5:
            asignacion[i] = c

    suma_z = int(round(sum(m.getSolVal(sol, v) for v in z.values())))
    valor_T = m.getSolVal(sol, T)
    valores_F = {k: m.getSolVal(sol, v) for k, v in F.items()}
    return asignacion, suma_z, valor_T, valores_F
