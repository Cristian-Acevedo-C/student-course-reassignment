# -*- coding: utf-8 -*-
"""
Auditoria independiente de una solucion entregada por el solver.

No usa SCIP: recalcula desde los datos de la instancia y los valores de x_ic
todas las restricciones duras y las componentes del objetivo. Sirve para no
confiar solo en que el solver declare una solucion factible.

Restricciones duras auditadas (numeracion del manuscrito):
  (7)      asignacion unica          sum_c x_ic = 1, x binario
  (8)      capacidad                 sum_i x_ic <= U_c
  (9)      separaciones              x_ac + x_bc <= 1
  (10-11)  balance de genero         |n_gc - n_gc'| <= Delta_g
  (12)     representacion de origen  sum_{i en o} x_ic >= alpha_o

Consistencia con el objetivo reportado por el solver:
  - satisfechos_recalculado == suma_z_solver   (igualdad exacta de conteos)
  - T_recalculado <= T_solver + tol            (T solo esta acotado abajo)
  - objetivo_solver == lambda_0 (N - suma_z) + lambda_1 T_solver
El modelo impone z_i >= w_ij y z_i <= sum_j w_ij: z representa exactamente
la disyuncion de preferencias satisfechas, incluso sin optimalidad. T solo
esta acotada abajo y puede tener holgura en un incumbente no optimo.
"""
TOL = 1e-6


def perfiles_por_curso(inst, asignacion):
    """F_k recalculado = sum_c sum_l |n_{c,k,l} - n_{k,l}/|C||, y T = max_k F_k."""
    est = inst["estudiantes"]
    C = inst["cursos"]
    F = {}
    for k in inst["criterios"]:
        total = 0.0
        for l in inst["niveles"]:
            miembros = [i for i in est if est[i][k] == l]
            promedio = len(miembros) / len(C)
            for c in C:
                cuenta = sum(1 for i in miembros if asignacion.get(i) == c)
                total += abs(cuenta - promedio)
        F[k] = total
    return F, (max(F.values()) if F else 0.0)


def preferencias_satisfechas(inst, asignacion):
    """Devuelve {i: [preferidos que quedaron en el mismo curso]}."""
    out = {}
    for i, prefs in inst["preferencias"].items():
        out[i] = [j for j in prefs if asignacion.get(j) == asignacion.get(i)]
    return out


def auditar(inst, valores_x, lambda_0, lambda_1,
            objetivo_solver=None, suma_z_solver=None, T_solver=None):
    """
    valores_x: {(i, c): valor} con TODOS los x_ic de la solucion (no solo los 1).
    Devuelve un dict con la asignacion, las violaciones y los valores recalculados.
    """
    S = sorted(inst["estudiantes"])
    C = inst["cursos"]
    est = inst["estudiantes"]
    viol = []

    # (7) integralidad y asignacion unica
    asignacion = {}
    for i in S:
        unos = []
        for c in C:
            v = valores_x.get((i, c))
            if v is None:
                viol.append(f"(7) falta x_{i}_{c}")
                continue
            if min(abs(v), abs(v - 1)) > TOL:
                viol.append(f"(7) x_{i}_{c}={v} no es binario")
            if v > 0.5:
                unos.append(c)
        if len(unos) != 1:
            viol.append(f"(7) estudiante {i} asignado a {len(unos)} cursos: {unos}")
        if unos:
            asignacion[i] = unos[0]

    # (8) capacidad
    for c in C:
        n = sum(1 for i in asignacion if asignacion[i] == c)
        if n > inst["capacidad"][c]:
            viol.append(f"(8) curso {c}: {n} > capacidad {inst['capacidad'][c]}")

    # (9) separaciones
    for a, b in inst["separaciones"]:
        if a in asignacion and asignacion.get(a) == asignacion.get(b):
            viol.append(f"(9) separacion {a}-{b} violada en curso {asignacion[a]}")

    # (10)-(11) genero
    for g in inst["grupos_genero"]:
        cuentas = [sum(1 for i in asignacion
                       if asignacion[i] == c and est[i]["genero"] == g) for c in C]
        if max(cuentas) - min(cuentas) > inst["delta_genero"]:
            viol.append(f"(10-11) genero {g}: {cuentas} excede Delta={inst['delta_genero']}")

    # (12) origen
    for o in inst["cursos_origen"]:
        for c in C:
            n = sum(1 for i in asignacion
                    if asignacion[i] == c and est[i]["origen"] == o)
            if n < inst["alpha"][o]:
                viol.append(f"(12) origen {o} en curso {c}: {n} < alpha={inst['alpha'][o]}")

    # componentes del objetivo recalculadas
    sat = preferencias_satisfechas(inst, asignacion)
    satisfechos = sum(1 for i in S if sat.get(i))
    F, T = perfiles_por_curso(inst, asignacion)
    objetivo_recalc = lambda_0 * (len(S) - satisfechos) + lambda_1 * T

    consistencia = []
    if suma_z_solver is not None and satisfechos != suma_z_solver:
        consistencia.append(
            f"suma_z_solver={suma_z_solver} != satisfechos_recalculado={satisfechos}")
    if T_solver is not None and T > T_solver + TOL:
        consistencia.append(f"T_recalculado={T} > T_solver={T_solver}")
    if None not in (objetivo_solver, suma_z_solver, T_solver):
        esperado = lambda_0 * (len(S) - suma_z_solver) + lambda_1 * T_solver
        if abs(esperado - objetivo_solver) > 1e-4:
            consistencia.append(
                f"objetivo_solver={objetivo_solver} != lambda0(N-sum z)+lambda1 T={esperado}")

    return {
        "asignacion": asignacion,
        "violaciones": viol,
        "inconsistencias_objetivo": consistencia,
        "solucion_auditada": not viol and not consistencia,
        "satisfechos_recalculado": satisfechos,
        "T_recalculado": T,
        "F_recalculado": F,
        "objetivo_recalculado": objetivo_recalc,
        "preferidos_juntos": sat,
    }
