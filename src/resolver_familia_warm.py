# -*- coding: utf-8 -*-
"""
Corre una familia con WARM START: la misma corrida que resolver_familia.py,
pero SCIP parte con la solucion del constructivo ya cargada.

Diseno (opcion A, acordada el 12-oct-2026):
  - Se ejecuta EXACTAMENTE el codigo del baseline (resolver_familia.py y
    modelo.py, sin modificarlos). Este archivo solo intercepta la llamada a
    construir_modelo para (1) entregar a SCIP la solucion constructiva y
    (2) descontar el tiempo del constructivo del limite de SCIP.
  - Todo lo demas es identico al baseline: reloj de pared, 1 hilo, gap 0,
    lambda_0 = lambda_1 = 1, semilla por defecto, logs, estadisticas,
    auditoria independiente y formato de resultados_familia.csv.
  - Por eso NO se vuelve a correr el baseline: con la misma version de SCIP y
    los mismos parametros es determinista (c_n_9_l_3_s_4_i_8 reprodujo sus
    6188 nodos). Lo que exige esta comparacion es correr en el MISMO PC donde
    se corrio el baseline de cada familia.

Presupuesto (--presupuesto):
  igual_total (default)  limite SCIP = tiempo - tiempo_constructivo
  igual_scip             limite SCIP = tiempo (diagnostico, no oficial)
El tiempo del constructivo se toma de resultados_constructivo.csv (columna
tiempo_total_s), medido cuando se generaron las soluciones. Si se quiere
medirlo en este PC hay que volver a correr el constructivo.

La solucion se entrega COMPLETA (x, y, w, z, dp, dm, F, T), se verifica con
checkSol(original=True) y se carga con addSol antes de optimize. Antes de
cargarla se audita desde los datos de la instancia; si es infactible o su
objetivo no calza con el archivo, la replica se aborta (no se corre sin warm
start en silencio).

Salida: la misma estructura de resolver_familia.py, mas
  warm_start.csv / warm_start.txt   una fila por replica: archivo, sha256, objetivo, tiempo del
                   constructivo, limite SCIP, checkSol y aceptacion.

Uso (desde la raiz del repositorio):
  python src/resolver_familia_warm.py --L 9 --P 3 --C 4 --tiempo 3600 \
      --soluciones-ws warm_start/constructivo/L9_P3_C4
"""
from pathlib import Path
import csv
import hashlib
import json
import sys

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import resolver_familia as rf  # noqa: E402
from modelo import construir_modelo as construir_modelo_original  # noqa: E402

# Versiones del codigo con que se corrio el baseline piloto (rama
# pipeline-familia-piloto, commit afcc03e). Si difieren, la comparacion con el
# baseline deja de ser limpia: se avisa y se exige --forzar.
SHA_BASELINE = {
    "modelo.py":
        "a79f8ec7df1cc63c64f9a588af5b9fb5169a1464355524abede25c16986c0bb6",
    "resolver_familia.py":
        "b284d5c6e8b211be479859651ab0856a73d47d55c9d47035630fd6611bc3cc3a",
    "auditar_solucion.py":
        "6e4140e489d5ecf346b05d633a4763fe2493967532d9cfc4d4b896ba7f921f37",
}

PROTOCOLO_PENDIENTE = {}

COLUMNAS_WS = [
    "instancia", "archivo_ws", "sha256_ws", "objetivo_archivo",
    "objetivo_recalculado", "T_recalculado", "satisfechos_recalculado",
    "factible_recalculado", "tiempo_constructivo_seg", "presupuesto",
    "limite_total_seg", "limite_scip_seg", "checksol_original", "aceptada",
]


def sha256(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def leer_asignacion(ruta):
    """Lee [ASIGNACION] de un heur_*.txt / sol_*.txt (columna curso_asignado
    o curso_nuevo). Devuelve (asignacion, objetivo declarado o None)."""
    asign, objetivo, en_tabla, idx = {}, None, False, None
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        s = linea.strip()
        if s.startswith("# objetivo="):
            objetivo = float(s.split("=", 1)[1])
        if s == "[ASIGNACION]":
            en_tabla = True
            continue
        if not en_tabla or not s:
            if en_tabla and not s and asign:
                break
            continue
        if s.startswith("["):
            break
        campos = s.split(";")
        if campos[0] == "estudiante":
            for nombre in ("curso_asignado", "curso_nuevo"):
                if nombre in campos:
                    idx = campos.index(nombre)
            if idx is None:
                raise ValueError(f"{ruta}: no hay columna de curso en {campos}")
            continue
        asign[int(campos[0])] = int(campos[idx])
    return asign, objetivo


def escribir_txt_ws(ruta, filas):
    """Gemelo .txt de warm_start.csv, en el formato de resultados_familia.txt."""
    lineas = ["WARM START - mismos campos que warm_start.csv",
              "NO DISPONIBLE corresponde a una celda vacia del CSV."]
    for r in filas:
        lineas += ["", f"[{r['instancia']}]"]
        lineas += [f"{c} = {rf.valor_txt(c, r.get(c))}" for c in COLUMNAS_WS]
    Path(ruta).write_text("\n".join(lineas) + "\n", encoding="utf-8")


def tiempos_constructivo(carpeta):
    ruta = Path(carpeta) / "resultados_constructivo.csv"
    if not ruta.exists():
        return {}
    with open(ruta, encoding="utf-8", newline="") as f:
        return {r["instancia"]: float(r["tiempo_total_s"])
                for r in csv.DictReader(f)}


def solucion_completa(m, inst, a):
    """Valores para TODAS las variables del modelo a partir de la asignacion."""
    S = sorted(inst["estudiantes"])
    C = inst["cursos"]
    est = inst["estudiantes"]
    P = inst["preferencias"]
    por_nombre = {v.name: v for v in m.getVars()}
    valores = {}

    for i in S:
        for c in C:
            valores[f"x_{i}_{c}"] = 1.0 if a[i] == c else 0.0
        sat = False
        for j in P.get(i, []):
            juntos = a[i] == a[j]
            sat = sat or juntos
            valores[f"w_{i}_{j}"] = 1.0 if juntos else 0.0
            for c in C:
                valores[f"y_{i}_{j}_{c}"] = 1.0 if (juntos and a[i] == c) else 0.0
        valores[f"z_{i}"] = 1.0 if sat else 0.0

    T = 0.0
    for k in inst["criterios"]:
        Fk = 0.0
        for l in inst["niveles"]:
            miembros = [i for i in S if est[i][k] == l]
            prom = len(miembros) / len(C)
            for c in C:
                dev = sum(1 for i in miembros if a[i] == c) - prom
                valores[f"dp_{c}_{k}_{l}"] = max(dev, 0.0)
                valores[f"dm_{c}_{k}_{l}"] = max(-dev, 0.0)
                Fk += abs(dev)
        valores[f"F_{k}"] = Fk
        T = max(T, Fk)
    valores["T"] = T

    faltan = set(por_nombre) - set(valores)
    sobran = set(valores) - set(por_nombre)
    if faltan or sobran:
        raise ValueError(f"warm start incompleto: faltan {sorted(faltan)[:5]} "
                         f"sobran {sorted(sobran)[:5]}")
    sol = m.createSol()
    for nombre, v in valores.items():
        m.setSolVal(sol, por_nombre[nombre], v)
    return sol


def instalar(args_ws):
    """Reemplaza rf.construir_modelo por una version que carga el warm start."""
    carpeta = Path(args_ws["soluciones"])
    tiempos = tiempos_constructivo(carpeta)
    registro = Path(args_ws["salida"]) / "warm_start.csv"

    def construir_modelo_con_ws(inst, lambda_0=1.0, lambda_1=1.0,
                                tiempo=3600.0, hilos=1, gap=0.0):
        nombre = inst["nombre"]
        ruta = carpeta / f"heur_{nombre}.txt"
        if not ruta.exists():
            raise FileNotFoundError(f"no hay solucion de warm start: {ruta}")
        a, obj_archivo = leer_asignacion(ruta)
        if sorted(a) != sorted(inst["estudiantes"]):
            raise ValueError(f"{ruta}: la asignacion no cubre a los {inst['N']} estudiantes")

        # auditoria propia ANTES de entregarla (mismo auditor del baseline)
        x = {(i, c): 1.0 if a[i] == c else 0.0
             for i in inst["estudiantes"] for c in inst["cursos"]}
        aud = rf.auditar(inst, x, lambda_0, lambda_1)
        obj_rec = aud["objetivo_recalculado"]
        factible = not aud["violaciones"]
        if not factible:
            raise ValueError(f"{ruta}: solucion infactible: {aud['violaciones']}")
        if obj_archivo is not None and abs(obj_rec - obj_archivo) > 1e-6:
            raise ValueError(f"{ruta}: objetivo declarado {obj_archivo} "
                             f"!= recalculado {obj_rec}")

        t_ws = tiempos.get(nombre)
        if args_ws["presupuesto"] == "igual_total":
            if t_ws is None:
                raise ValueError(f"falta tiempo_total_s de {nombre} en "
                                 "resultados_constructivo.csv")
            limite = tiempo - t_ws
        else:
            limite = tiempo

        m, vars_ = construir_modelo_original(
            inst, lambda_0=lambda_0, lambda_1=lambda_1,
            tiempo=limite, hilos=hilos, gap=gap)
        sol = solucion_completa(m, inst, a)
        ok_check = bool(m.checkSol(sol, printreason=True, completely=True,
                                   original=True))
        aceptada = bool(m.addSol(sol, free=True)) if ok_check else False
        if not aceptada:
            raise RuntimeError(f"SCIP no acepto el warm start de {nombre} "
                               f"(checkSol={ok_check})")

        fila = {
            "instancia": nombre, "archivo_ws": ruta.name,
            "sha256_ws": sha256(ruta), "objetivo_archivo": obj_archivo,
            "objetivo_recalculado": obj_rec,
            "T_recalculado": aud["T_recalculado"],
            "satisfechos_recalculado": aud["satisfechos_recalculado"],
            "factible_recalculado": factible,
            "tiempo_constructivo_seg": t_ws,
            "presupuesto": args_ws["presupuesto"],
            "limite_total_seg": tiempo, "limite_scip_seg": limite,
            "checksol_original": ok_check, "aceptada": aceptada,
        }
        registro.parent.mkdir(parents=True, exist_ok=True)
        ruta_prot = registro.parent / "warm_start_protocolo.json"
        if PROTOCOLO_PENDIENTE and not ruta_prot.exists():
            ruta_prot.write_text(json.dumps(PROTOCOLO_PENDIENTE, indent=2,
                                            ensure_ascii=False) + "\n",
                                 encoding="utf-8")
        previas = []
        if registro.exists():
            with open(registro, encoding="utf-8", newline="") as f:
                previas = [r for r in csv.DictReader(f) if r["instancia"] != nombre]
        with open(registro, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNAS_WS)
            w.writeheader()
            w.writerows(previas + [fila])
        escribir_txt_ws(registro.with_suffix(".txt"), previas + [fila])
        print(f"    warm start {ruta.name}: objetivo {obj_rec:g}, "
              f"constructivo {t_ws} s, limite SCIP {limite:.3f} s", flush=True)
        return m, vars_

    rf.construir_modelo = construir_modelo_con_ws


def sha256_texto(ruta):
    """Hash con fin de linea normalizado: en Windows git o una copia manual
    pueden dejar CRLF sin que cambie el codigo."""
    datos = Path(ruta).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(datos).hexdigest()


def verificar_codigo(forzar):
    distintos = [n for n, h in SHA_BASELINE.items() if sha256_texto(AQUI / n) != h]
    if distintos:
        print("AVISO: estos archivos no son la version con que se corrio el "
              f"baseline piloto: {distintos}")
        if not forzar:
            sys.exit("Se detiene para no comparar contra otro codigo. "
                     "Usa --forzar si el cambio es intencional y documentado.")


def main():
    # Se separan los argumentos propios; el resto va tal cual a resolver_familia.
    propios = {"--soluciones-ws": None, "--presupuesto": "igual_total"}
    forzar = "--forzar" in sys.argv
    argv = [x for x in sys.argv[1:] if x != "--forzar"]
    resto = []
    k = 0
    while k < len(argv):
        if argv[k] in propios:
            propios[argv[k]] = argv[k + 1]
            k += 2
        else:
            resto.append(argv[k])
            k += 1
    if not propios["--soluciones-ws"]:
        sys.exit("falta --soluciones-ws <carpeta con heur_<instancia>.txt>")
    if propios["--presupuesto"] not in ("igual_total", "igual_scip"):
        sys.exit("--presupuesto debe ser igual_total o igual_scip")
    if "--salida" not in resto:
        sys.exit("indica --salida (carpeta distinta a la del baseline)")
    salida = resto[resto.index("--salida") + 1]

    verificar_codigo(forzar)
    instalar({"soluciones": propios["--soluciones-ws"],
              "presupuesto": propios["--presupuesto"],
              "salida": salida})

    protocolo = {
        "condicion": "warm_start_constructivo",
        "soluciones_ws": str(Path(propios["--soluciones-ws"]).resolve()),
        "presupuesto": propios["--presupuesto"],
        "codigo_baseline_sha256": SHA_BASELINE,
        "codigo_baseline_verificado": not forzar,
        "nota": "Mismo codigo y parametros que el baseline; solo cambia la "
                "solucion inicial y el limite de SCIP (menos el constructivo).",
    }
    # Se escribe al resolver la primera replica: resolver_familia exige que
    # la carpeta de salida este vacia al partir (salvo --reanudar).
    PROTOCOLO_PENDIENTE.update(protocolo)

    sys.argv = [str(AQUI / "resolver_familia.py")] + resto
    rf.main()


if __name__ == "__main__":
    main()
