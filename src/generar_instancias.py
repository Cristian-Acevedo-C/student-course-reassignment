# -*- coding: utf-8 -*-
"""
Generador de instancias para el analisis de sensibilidad del modelo exacto
de reasignacion de estudiantes.

Grilla final (480 instancias):
    n (alumnos por curso) : 9, 18, 36, 72
    l (preferencias)      : 4, 5, 6, 7
    s (cursos)            : 4, 5, 6
    i (replica)           : 0..9

Nombre de archivo: c_n_[N]_l_[L]_s_[S]_i_[I].txt

Cada instancia se construye alrededor de una ASIGNACION TESTIGO que satisface
todas las restricciones duras, de modo que la instancia es factible por
construccion. El testigo NO se escribe en el archivo de instancia: solo se usa
para sortear las separaciones (siempre entre alumnos que el testigo deja en
cursos distintos) y se guarda aparte para auditoria.

Uso:
    python generar_instancias.py --caso 36 7 4 0        # un solo caso
    python generar_instancias.py --todas                # las 480
"""
from pathlib import Path
import argparse
import random

# ----------------------------------------------------------------------
# GRILLA EXPERIMENTAL
# ----------------------------------------------------------------------
N_VALORES = [9, 18, 36, 72]      # alumnos por curso
L_VALORES = [4, 5, 6, 7]         # preferencias por alumno
S_VALORES = [4, 5, 6]            # cantidad de cursos
REPLICAS = range(10)             # i = 0..9

DIFERENCIA_GENERO = 1            # Delta_g
NIVELES = [1, 2, 3]
CRITERIOS = ["academico", "socioemocional", "convivencia"]


def semilla_de(n, l, s, i):
    """Semilla reproducible y unica por combinacion de parametros."""
    return (n * 1_000_003 + l * 10_007 + s * 101 + i * 7) % 1_000_000


def alpha_de(n, s):
    """Minimo de alumnos de cada curso de origen en cada curso destino.

    Reparto proporcional floor(n/s) relajado en una unidad, misma convencion
    que el ejemplo ilustrativo del manuscrito.
    """
    return max(0, n // s - 1)


# ----------------------------------------------------------------------
# TESTIGO FACTIBLE
# ----------------------------------------------------------------------

def construir_testigo(estudiantes, s):
    """Reparte los alumnos en s cursos destino.

    Los alumnos se agrupan por (curso_origen, genero) y se reparten con un
    puntero ROTATORIO CONTINUO que no se reinicia entre grupos. Como el total
    N = n*s es divisible por s, cada curso recibe exactamente n alumnos, lo que
    hace que la capacidad sea exacta por construccion para cualquier n (par o
    impar). El equilibrio de genero y de origen se afina despues con
    intercambios, que preservan el tamano de los cursos.
    """
    buckets = {}
    for e in estudiantes:
        buckets.setdefault((e["origen"], e["genero"]), []).append(e["id"])

    testigo = {}
    puntero = 0
    for clave in sorted(buckets):
        for eid in buckets[clave]:
            testigo[eid] = puntero % s + 1
            puntero += 1
    return testigo


def verificar_testigo(estudiantes, testigo, n, s, alpha):
    """Devuelve la lista de violaciones del testigo (vacia si es factible)."""
    fallas = []
    cursos = list(range(1, s + 1))
    por_id = {e["id"]: e for e in estudiantes}

    for c in cursos:
        cuenta = sum(1 for e in estudiantes if testigo[e["id"]] == c)
        if cuenta != n:
            fallas.append(f"capacidad curso {c}: {cuenta} != {n}")

    for g in ("F", "M"):
        cuentas = [
            sum(1 for e in estudiantes
                if testigo[e["id"]] == c and e["genero"] == g)
            for c in cursos
        ]
        if cuentas and max(cuentas) - min(cuentas) > DIFERENCIA_GENERO:
            fallas.append(f"genero {g}: {cuentas} excede delta={DIFERENCIA_GENERO}")

    origenes = sorted({e["origen"] for e in estudiantes})
    for o in origenes:
        for c in cursos:
            cuenta = sum(1 for e in estudiantes
                         if testigo[e["id"]] == c and e["origen"] == o)
            if cuenta < alpha:
                fallas.append(f"origen {o} -> curso {c}: {cuenta} < alpha={alpha}")

    del por_id
    return fallas


def reparar_testigo(estudiantes, testigo, n, s, alpha, rng, intentos=60000):
    """Afina el testigo con intercambios entre cursos.

    Un intercambio mueve dos alumnos de cursos distintos, de modo que el
    tamano de cada curso no cambia: la capacidad exacta que garantiza
    construir_testigo() se conserva durante todo el proceso. Solo se corrigen
    genero y representacion por origen.
    """
    def costo():
        c_total = 0
        cursos = list(range(1, s + 1))
        for g in ("F", "M"):
            cuentas = [
                sum(1 for e in estudiantes
                    if testigo[e["id"]] == c and e["genero"] == g)
                for c in cursos
            ]
            exceso = max(cuentas) - min(cuentas) - DIFERENCIA_GENERO
            c_total += max(0, exceso) * 10
        for o in sorted({e["origen"] for e in estudiantes}):
            for c in cursos:
                cuenta = sum(1 for e in estudiantes
                             if testigo[e["id"]] == c and e["origen"] == o)
                c_total += max(0, alpha - cuenta) * 10
        return c_total

    actual = costo()
    ids = [e["id"] for e in estudiantes]
    for _ in range(intentos):
        if actual == 0:
            break
        a, b = rng.sample(ids, 2)
        if testigo[a] == testigo[b]:
            continue
        testigo[a], testigo[b] = testigo[b], testigo[a]
        nuevo = costo()
        if nuevo <= actual:
            actual = nuevo
        else:
            testigo[a], testigo[b] = testigo[b], testigo[a]
    return actual == 0


# ----------------------------------------------------------------------
# GENERACION DE UNA INSTANCIA
# ----------------------------------------------------------------------

def generar(n, l, s, i, destino: Path, dir_testigos: Path = None):
    semilla = semilla_de(n, l, s, i)
    rng = random.Random(semilla)

    N = n * s
    alpha = alpha_de(n, s)
    nombre = f"c_n_{n}_l_{l}_s_{s}_i_{i}"

    # ---------- estudiantes ----------
    estudiantes = []
    eid = 1
    for k in range(1, s + 1):
        origen = f"O{k}"
        # genero balanceado dentro de cada curso de origen
        generos = ["F"] * (n // 2) + ["M"] * (n - n // 2)
        rng.shuffle(generos)
        for g in generos:
            estudiantes.append({
                "id": eid,
                "origen": origen,
                "genero": g,
                # los tres criterios se sortean de forma independiente
                "academico": rng.choice(NIVELES),
                "socioemocional": rng.choice(NIVELES),
                "convivencia": rng.choice(NIVELES),
            })
            eid += 1

    # ---------- testigo factible ----------
    testigo = construir_testigo(estudiantes, s)
    fallas = verificar_testigo(estudiantes, testigo, n, s, alpha)
    if fallas:
        if not reparar_testigo(estudiantes, testigo, n, s, alpha, rng):
            raise RuntimeError(
                f"{nombre}: no se pudo construir un testigo factible.\n"
                + "\n".join(fallas)
            )

    # ---------- preferencias ----------
    ids = [e["id"] for e in estudiantes]
    preferencias = {}
    for e in estudiantes:
        otros = [x for x in ids if x != e["id"]]
        preferencias[e["id"]] = rng.sample(otros, l)

    # ---------- separaciones ----------
    # Siempre entre alumnos que el testigo deja en cursos distintos:
    # asi la instancia es factible por construccion.
    objetivo_pares = round(N / 4)
    pares = set()
    intentos = 0
    while len(pares) < objetivo_pares and intentos < objetivo_pares * 500:
        intentos += 1
        a, b = rng.sample(ids, 2)
        if testigo[a] == testigo[b]:
            continue
        pares.add((min(a, b), max(a, b)))
    pares = sorted(pares)

    # ---------- escritura ----------
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / f"{nombre}.txt"

    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        w = f.write
        w("# ------------------------------------------------------------\n")
        w("# Instancia sintetica para pruebas del modelo exacto\n")
        w(f"# L = {n} estudiantes por curso\n")
        w(f"# P = {l} preferencias por estudiante\n")
        w(f"# C = {s} cursos nuevos\n")
        w(f"# Total = {N} estudiantes\n")
        w("# ------------------------------------------------------------\n\n")
        w("# INSTANCIA DE REASIGNACION DE ESTUDIANTES\n")
        w("# Este archivo contiene los datos de entrada de la instancia. "
          "La solucion se guarda aparte.\n\n")

        w("[INSTANCIA]\n")
        w(f"nombre={nombre}\n")
        w(f"semilla={semilla}\n")
        w(f"N={N}\n")
        w(f"C={s}\n")
        w(f"L={n}\n")
        w(f"P={l}\n\n")

        w("[CURSOS_NUEVOS]\n")
        w("curso;capacidad\n")
        for c in range(1, s + 1):
            w(f"{c};{n}\n")
        w("\n")

        w("[BALANCE_GENERO]\n")
        w("grupos=F,M\n")
        w(f"diferencia_maxima={DIFERENCIA_GENERO}\n\n")

        w("[CURSOS_ORIGEN]\n")
        w("cursos_origen=" + ",".join(f"O{k}" for k in range(1, s + 1)) + "\n")
        for k in range(1, s + 1):
            w(f"minimo_O{k}={alpha}\n")
        w("\n")

        w("[CRITERIOS_BALANCE]\n")
        w("criterios=" + ",".join(CRITERIOS) + "\n")
        w("niveles=" + ",".join(str(x) for x in NIVELES) + "\n\n")

        w("[ESTUDIANTES]\n")
        w("estudiante;curso_origen;genero;academico;socioemocional;convivencia\n")
        for e in estudiantes:
            w(f"{e['id']};{e['origen']};{e['genero']};"
              f"{e['academico']};{e['socioemocional']};{e['convivencia']}\n")
        w("\n")

        w("[PREFERENCIAS]\n")
        w(f"# En esta familia P={l}, por lo que cada estudiante tiene "
          f"{l} preferencias\n")
        w("estudiante;" + ";".join(f"preferencia_{k}" for k in range(1, l + 1)) + "\n")
        for e in estudiantes:
            w(f"{e['id']};" + ";".join(str(p) for p in preferencias[e["id"]]) + "\n")
        w("\n")

        w("[SEPARACIONES]\n")
        w("estudiante_i;estudiante_j\n")
        for a, b in pares:
            w(f"{a};{b}\n")
        w("\n")

        w("[NOTAS]\n")
        w("generacion=aleatoria_controlada\n")
        w("preferencias_por_estudiante=P_fijo\n")
        w("genero=balanceado_dentro_de_cada_curso_de_origen\n")
        w("criterios_perfil=sorteados_de_forma_independiente\n")
        w("separaciones=aprox_N_div_4\n")
        w("estado=instancia_de_experimento\n")
        w("pesos_funcion_objetivo=no_incluidos_en_la_instancia\n")
        w("factibilidad=se_uso_una_asignacion_testigo_solo_para_generar_la_instancia\n")

    # ---------- testigo aparte (auditoria, NO warm start) ----------
    if dir_testigos is not None:
        dir_testigos.mkdir(parents=True, exist_ok=True)
        with open(dir_testigos / f"testigo_{nombre}.txt", "w",
                  encoding="utf-8", newline="\n") as f:
            f.write("# Testigo factible usado SOLO para generar la instancia.\n")
            f.write("# No debe usarse como warm start en el benchmark.\n")
            f.write("estudiante;curso_testigo\n")
            for e in estudiantes:
                f.write(f"{e['id']};{testigo[e['id']]}\n")

    return ruta, {
        "nombre": nombre, "N": N, "C": s, "L": n, "P": l,
        "alpha": alpha, "separaciones": len(pares), "semilla": semilla,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--caso", nargs=4, type=int, metavar=("N", "L", "S", "I"),
                    help="genera un solo caso: n l s i")
    ap.add_argument(
        "--todas",
        action="store_true",
        help="reemplaza la grilla generada y crea las 480 instancias finales",
    )
    ap.add_argument("--destino", default="instancias")
    ap.add_argument("--testigos", default="testigos")
    a = ap.parse_args()

    destino = Path(a.destino)
    testigos = Path(a.testigos)

    if a.caso:
        n, l, s, i = a.caso
        ruta, info = generar(n, l, s, i, destino, testigos)
        print("Generada:", ruta)
        for k, v in info.items():
            print(f"  {k:14s}: {v}")
        return

    if a.todas:
        # Evita mezclar archivos de una grilla anterior con el protocolo vigente.
        # Los patrones son deliberadamente específicos para no borrar otros datos.
        anteriores = list(destino.glob("c_n_*_l_*_s_*_i_*.txt"))
        testigos_anteriores = list(
            testigos.glob("testigo_c_n_*_l_*_s_*_i_*.txt")
        )
        for ruta in anteriores + testigos_anteriores:
            ruta.unlink()

        total = 0
        for n in N_VALORES:
            for l in L_VALORES:
                for s in S_VALORES:
                    for i in REPLICAS:
                        generar(n, l, s, i, destino, testigos)
                        total += 1
        print(
            f"Reemplazados {len(anteriores)} archivos de instancia y "
            f"{len(testigos_anteriores)} testigos anteriores."
        )
        print(f"Generadas {total} instancias en {destino}")
        return

    ap.error("indica --caso N L S I o --todas")


if __name__ == "__main__":
    main()
