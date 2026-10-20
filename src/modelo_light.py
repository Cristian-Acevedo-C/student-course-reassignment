# -*- coding: utf-8 -*-
"""
Formulacion compacta ("Light") del SCRP, equivalente a la de modelo.py.

Resuelve el MISMO problema que modelo.construir_modelo: mismas variables de
decision x_ic, mismas restricciones duras (7)-(12) y el mismo valor objetivo
lambda_0 (N - sum z) + lambda_1 T para cada asignacion entera. Lo que cambia
es la representacion de los bloques auxiliares:

  Preferencias (13)-(19)
    baseline: y_ijc, w_ij binarias (N*P*C + N*P variables, 3NPC + ... filas)
    light   : z_i continua en [0, 1] con
                z_i >= x_ic + x_jc - 1          para j en P_i, c en C
                z_i <= 1 - x_ic + sum_{j en P_i} x_jc   para c en C
              Con x entero, z_i vale exactamente 1 si algun preferido comparte
              curso con i y 0 si no; z queda exacta tambien en incumbentes no
              optimos (la auditoria exige suma_z exacta).

  Balance de perfiles (20)-(22), escalado por |C| para trabajar con enteros
    e_ckl >= |C| q_ckl - n_kl ,  e_ckl >= n_kl - |C| q_ckl ,  e_ckl >= 0
    |C| T >= sum_{c,l} e_ckl                    para cada criterio k
    (equivale a d+ + d- con d = q - n/|C|, multiplicado por |C|)

  Cotas analiticas (validas para cualquier asignacion entera)
    r_kl = n_kl mod |C|,  b_kl = 2 r_kl (|C| - r_kl)
    sum_c e_ckl >= b_kl  para cada (k, l)    y   |C| T >= max_k sum_l b_kl

  Ruptura de simetria por precedencia (solo si los cursos son intercambiables)
    Con estudiantes ordenados s_0 < s_1 < ...: x_{s_0, c_0} = 1,
    x_{s_p, c} = 0 si c > p, y  x_{s_p, c} <= sum_{q < p} x_{s_q, c-1}.
    Cada particion conserva exactamente un etiquetado (orden de primera
    aparicion), por lo que el optimo no cambia; si cambia QUE solucion optima
    se reporta.

  Preferencias imposibles: si (i, j) es un par de separacion, j se elimina de
  P_i (nunca puede compartir curso). No cambia el valor de ninguna asignacion.

El objetivo se mantiene en las unidades originales (no se multiplica por |C|)
para que primal_bound, dual_bound, gap y la auditoria del pipeline sean
directamente comparables con la formulacion baseline.
"""


import math


def cursos_intercambiables(inst):
    """True si permutar cursos destino no altera ninguna restriccion.

    En el modelo vigente lo unico especifico de cada curso destino es su
    capacidad (alpha y delta de genero son comunes a todos los cursos).
    """
    caps = {inst["capacidad"][c] for c in inst["cursos"]}
    return len(caps) == 1


def cotas_dispersion(inst):
    """b_kl = 2 r (|C| - r): cota de sum_c |C q_ckl - n_kl| (en unidades x|C|)."""
    nC = len(inst["cursos"])
    est = inst["estudiantes"]
    b = {}
    for k in inst["criterios"]:
        for l in inst["niveles"]:
            n = sum(1 for e in est.values() if e[k] == l)
            r = n % nC
            b[k, l] = 2 * r * (nC - r)
    lb_tau = max(sum(b[k, l] for l in inst["niveles"]) for k in inst["criterios"])
    return b, lb_tau


def orden_canonico(inst, asignacion):
    """Renombra los cursos por orden de primera aparicion (cumple la precedencia).

    Util para cargar warm starts o soluciones de referencia en la formulacion
    light: una solucion del baseline puede violar la precedencia solo por la
    numeracion de los cursos.
    """
    C = inst["cursos"]
    mapa = {}
    for i in sorted(inst["estudiantes"]):
        c = asignacion[i]
        if c not in mapa:
            mapa[c] = C[len(mapa)]
    return {i: mapa[c] for i, c in asignacion.items()}


def construir_modelo_light(inst, lambda_0=1.0, lambda_1=1.0,
                           tiempo=3600.0, hilos=1, gap=0.0,
                           cotas=True, precedencia=True, depurar_preferencias=True,
                           absgap_grilla=False, conteos_enteros=False, z_exacta=True,
                           cotas_celda=False, simetria_scip=False):
    """Opciones experimentales (todas apagadas = Light original):

    absgap_grilla   : detiene cuando primal - dual < paso de la grilla del objetivo
                      (paso = mcd(lambda_0, 2 lambda_1 / |C|); solo lambdas enteras).
    conteos_enteros : variables enteras q_ckl = conteo por curso/criterio/nivel con
                      prioridad de ramificacion (ramifica sobre conteos, no sobre x).
    z_exacta        : False elimina las filas z_i >= x_ic + x_jc - 1 (z solo acotada
                      arriba; exacta en el optimo, no en incumbentes intermedios).
    cotas_celda     : e_ckl >= min(r, |C| - r) (cada celda tiene desviacion minima).
    simetria_scip   : sin precedencia; deja que SCIP detecte la simetria antes del
                      presolve (orbitopes). Ignora 'precedencia'.
    """
    from pyscipopt import Model, quicksum

    S = sorted(inst["estudiantes"])
    C = inst["cursos"]
    nC = len(C)
    est = inst["estudiantes"]

    separados = {frozenset(p) for p in inst["separaciones"]}
    P = {}
    eliminadas = 0
    for i in S:
        prefs = list(inst["preferencias"].get(i, []))
        if depurar_preferencias:
            n0 = len(prefs)
            prefs = [j for j in prefs if frozenset((i, j)) not in separados]
            eliminadas += n0 - len(prefs)
        P[i] = prefs

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
        m.addCons(quicksum(x[i, c] for c in C) == 1, name=f"asig_{i}")

    # (8) capacidad
    for c in C:
        m.addCons(quicksum(x[i, c] for i in S) <= inst["capacidad"][c], name=f"cap_{c}")

    # (9) separaciones
    for a, b in inst["separaciones"]:
        for c in C:
            m.addCons(x[a, c] + x[b, c] <= 1, name=f"sep_{a}_{b}_{c}")

    # (10)-(11) balance de genero (identico al baseline)
    delta = inst["delta_genero"]
    for g in inst["grupos_genero"]:
        miembros = [i for i in S if est[i]["genero"] == g]
        for p in range(nC):
            for q in range(p + 1, nC):
                n1 = quicksum(x[i, C[p]] for i in miembros)
                n2 = quicksum(x[i, C[q]] for i in miembros)
                m.addCons(n1 - n2 <= delta, name=f"gen_{g}_{C[p]}_{C[q]}_a")
                m.addCons(n2 - n1 <= delta, name=f"gen_{g}_{C[p]}_{C[q]}_b")

    # (12) representacion por curso de origen
    for o in inst["cursos_origen"]:
        miembros = [i for i in S if est[i]["origen"] == o]
        for c in C:
            m.addCons(quicksum(x[i, c] for i in miembros) >= inst["alpha"][o],
                      name=f"orig_{o}_{c}")

    # preferencias: z continua y exacta
    z = {}
    for i in S:
        if not P[i]:
            z[i] = m.addVar(lb=0.0, ub=0.0, name=f"z_{i}")
            continue
        z[i] = m.addVar(lb=0.0, ub=1.0, name=f"z_{i}")
        for c in C:
            amigos_c = quicksum(x[j, c] for j in P[i])
            m.addCons(z[i] <= 1 - x[i, c] + amigos_c, name=f"zsup_{i}_{c}")
            if z_exacta:
                for j in P[i]:
                    m.addCons(z[i] >= x[i, c] + x[j, c] - 1, name=f"zinf_{i}_{j}_{c}")

    # balance de perfiles, escalado por |C|
    T = m.addVar(lb=0.0, name="T")
    e = {}
    b, lb_tau = cotas_dispersion(inst)
    F = {}
    for k in inst["criterios"]:
        for l in inst["niveles"]:
            miembros = [i for i in S if est[i][k] == l]
            n = len(miembros)
            r = n % nC
            for c in C:
                e[c, k, l] = m.addVar(lb=float(min(r, nC - r)) if cotas_celda else 0.0,
                                      name=f"e_{c}_{k}_{l}")
                q = quicksum(x[i, c] for i in miembros)
                if conteos_enteros:
                    qv = m.addVar(vtype="I", lb=0, ub=min(n, inst["capacidad"][c]),
                                  name=f"q_{c}_{k}_{l}")
                    m.addCons(qv == q, name=f"q_{c}_{k}_{l}")
                    m.chgVarBranchPriority(qv, 10)
                    q = qv
                m.addCons(e[c, k, l] >= nC * q - n, name=f"dev_{c}_{k}_{l}_a")
                m.addCons(e[c, k, l] >= n - nC * q, name=f"dev_{c}_{k}_{l}_b")
            if cotas and b[k, l] > 0:
                m.addCons(quicksum(e[c, k, l] for c in C) >= b[k, l], name=f"lb_{k}_{l}")
        F[k] = quicksum(e[c, k, l] for c in C for l in inst["niveles"])
        m.addCons(nC * T >= F[k], name=f"T_{k}")
    if cotas:
        m.addCons(nC * T >= lb_tau, name="lb_T")

    # ruptura de simetria por precedencia
    if simetria_scip:
        precedencia = False
        m.setParam("propagating/symmetry/symtiming", 0)
    if absgap_grilla:
        from fractions import Fraction
        l0, l1 = Fraction(lambda_0).limit_denominator(1000), Fraction(lambda_1).limit_denominator(1000)
        paso_T = l1 * Fraction(2, nC)
        paso = paso_T if l0 == 0 else Fraction(math.gcd(l0.numerator * paso_T.denominator,
                                                         paso_T.numerator * l0.denominator),
                                               l0.denominator * paso_T.denominator)
        m.setParam("limits/absgap", float(paso) - 1e-6)
    aplica_precedencia = precedencia and cursos_intercambiables(inst)
    n_prec = 0
    if aplica_precedencia:
        for p, i in enumerate(S):
            for ci in range(nC):
                if ci > p:
                    m.chgVarUb(x[i, C[ci]], 0.0)
                    n_prec += 1
                elif ci >= 1 and p >= 1:
                    m.addCons(x[i, C[ci]] <= quicksum(x[S[q], C[ci - 1]] for q in range(p)),
                              name=f"prec_{i}_{C[ci]}")
                    n_prec += 1
        m.chgVarLb(x[S[0], C[0]], 1.0)

    m.setObjective(
        lambda_0 * (len(S) - quicksum(z[i] for i in S)) + lambda_1 * T,
        "minimize",
    )

    info = {"formulacion": "light", "cotas": cotas, "precedencia": aplica_precedencia,
            "filas_precedencia": n_prec, "preferencias_imposibles": eliminadas,
            "lb_T": lb_tau / nC}
    # F se entrega en unidades originales (sum de |q - n/|C||) para extraer_solucion
    return m, {"x": x, "z": z, "T": T, "F": F, "e": e, "escala_F": nC, "info": info}


def extraer_solucion(m, vars_, inst):
    """Misma salida que modelo.extraer_solucion: (asignacion, suma_z, T, F)."""
    if m.getNSols() == 0:
        return None, None, None, None
    sol = m.getBestSol()
    asignacion = {i: c for (i, c), v in vars_["x"].items() if m.getSolVal(sol, v) > 0.5}
    suma_z = int(round(sum(m.getSolVal(sol, v) for v in vars_["z"].values())))
    valor_T = m.getSolVal(sol, vars_["T"])
    nC = vars_["escala_F"]
    valores_F = {k: sum(m.getSolVal(sol, vars_["e"][c, kk, l])
                        for (c, kk, l) in vars_["e"] if kk == k) / nC
                 for k in inst["criterios"]}
    return asignacion, suma_z, valor_T, valores_F
