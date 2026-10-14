#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entrega 120 TXT de asignaciones de SCRP: 30 x GREEDY, BASE, WARM, REPLAY.

Solo lee resultados existentes en NLHPC. Nunca inicia SCIP ni altera el modelo.
Rechaza entregas incompletas y audita las 120 asignaciones independientemente.
Uso: python3 exportar_120_txt_nlhpc.py [--raiz /ruta/repositorio]
"""
from __future__ import annotations
import argparse
import csv
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sys

METHODS = ("GREEDY", "BASE", "WARM", "REPLAY")
CS = (4, 5, 6)
IDX = range(10)
LINE_RE = re.compile(r"^x_(\d+)_(\d+)\s+([^\s]+)(?:\s|$)")


def digest(p: Path) -> str:
    return sha256(p.read_bytes()).hexdigest()


def read_one_row(path: Path, expected: str) -> dict:
    if not path.is_file():
        raise ValueError(f"Falta archivo de métricas: {path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1 or rows[0].get("instancia") != expected:
        raise ValueError(f"CSV de corrida no coincide con {expected}: {path}")
    return rows[0]


def true_value(v) -> bool:
    return str(v).lower().strip() in {"true", "1", "si", "yes"}


def parse_assignment_txt(path: Path, course_field: str, expected: str) -> dict[int, int]:
    if not path.is_file():
        raise ValueError(f"No existe asignación: {path}")
    data = path.read_text(encoding="utf-8-sig")
    if "[ASIGNACION]" not in data:
        raise ValueError(f"No contiene [ASIGNACION]: {path}")
    if expected not in data:
        raise ValueError(f"TXT no identifica instancia {expected}: {path}")
    section = data.split("[ASIGNACION]", 1)[1]
    section = re.split(r"(?m)^\[\w+\]", section)[0]
    rows = [x.strip() for x in section.splitlines() if x.strip() and not x.lstrip().startswith("#")]
    if not rows:
        raise ValueError(f"Sección de asignación vacía: {path}")
    hdr = rows[0].split(";")
    if "estudiante" not in hdr or course_field not in hdr:
        raise ValueError(f"Columnas requeridas ausentes {course_field}: {path} ({hdr})")
    ai, ci = hdr.index("estudiante"), hdr.index(course_field)
    assignment: dict[int, int] = {}
    for r in rows[1:]:
        f = r.split(";")
        if len(f) != len(hdr):
            raise ValueError(f"Fila con columnas incorrectas en {path}: {r}")
        i, c = int(f[ai]), int(f[ci])
        if i in assignment:
            raise ValueError(f"Estudiante duplicado {i} en {path}")
        assignment[i] = c
    return assignment


def parse_replay_sol(path: Path) -> tuple[dict[int, int], float | None]:
    if not path.is_file():
        raise ValueError(f"Falta .sol de REPLAY: {path}")
    assignment: dict[int, int] = {}
    objective: float | None = None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        mobj = re.match(r"^objective value:\s*([^\s]+)", line.strip(), flags=re.I)
        if mobj:
            objective = float(mobj[1])
        m = LINE_RE.match(line.strip())
        if not m:
            continue
        i, c, sval = int(m[1]), int(m[2]), float(m[3])
        if not math.isfinite(sval) or min(abs(sval), abs(sval - 1)) > 1e-6:
            raise ValueError(f"Variable de asignación no binaria: {m[0]} ({path})")
        if sval > 0.5:
            if i in assignment:
                raise ValueError(f"Dos cursos para estudiante {i}: {path}")
            assignment[i] = c
    if not assignment:
        raise ValueError(f"No se encontraron x_i_c = 1: {path}")
    return assignment, objective


def almost(a: float, b: float, tol: float = 1e-5) -> bool:
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


def load_method(root: Path, method: str, inst: dict, name: str, c: int, i: int):
    if method == "GREEDY":
        source = root / "warm_start" / "constructivo" / f"L9_P3_C{c}" / f"heur_{name}.txt"
        assignment = parse_assignment_txt(source, "curso_asignado", name)
        content = source.read_text(encoding="utf-8-sig")
        m = re.search(r"(?mi)^#\s*factible\s*=\s*(\w+)", content)
        if not m or not true_value(m[1]):
            raise ValueError(f"Greedy no declara factibilidad: {source}")
        reported = re.search(r"(?mi)^#\s*objetivo\s*=\s*([0-9.eE+-]+)", content)
        return assignment, source, float(reported[1]) if reported else None, {"metodo": method, "validacion_origen": "factible=True"}

    base = root / "corridas_nlhpc"
    if method in ("BASE", "WARM"):
        folder = base / ("base_5cpu_v1" if method == "BASE" else "warm_5cpu_v2") / "T3600" / f"C{c}" / f"i{i}"
        source = folder / "soluciones" / f"sol_{name}.txt"
        record = read_one_row(folder / "resultados_familia.csv", name)
        if not true_value(record.get("solucion_auditada")) or not true_value(record.get("checksol_scip")):
            raise ValueError(f"Auditoría original no aprobada en {folder}")
        if record.get("sha256_instancia") != digest(root / "instancias" / (name + ".txt")):
            raise ValueError(f"Hash de instancia no coincide: {folder}")
        assignment = parse_assignment_txt(source, "curso_nuevo", name)
        recorded_source = Path(record.get("solucion", "")).name
        if recorded_source and recorded_source != source.name:
            raise ValueError(f"Nombre de solución difiere del registro CSV: {folder}")
        reported = record.get("objetivo_incumbente") or record.get("primal_bound")
        return assignment, source, float(reported) if reported else None, {"metodo": method, "validacion_origen": "SCIP checkSol y auditoría independientes originales: TRUE"}

    if method == "REPLAY":
        folder = base / "replay_scip_base_5cpu_v1" / "T3600" / f"C{c}" / f"i{i}"
        source = folder / "final.sol"
        meta_file = folder / "replay_metadata.json"
        if not meta_file.is_file():
            raise ValueError(f"Falta metadata REPLAY: {meta_file}")
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if meta.get("instancia") != name:
            raise ValueError(f"Instancia REPLAY incorrecta en {meta_file}")
        if not true_value(meta.get("checksol_final")) or not true_value(meta.get("auditoria_final")):
            raise ValueError(f"Auditoría final REPLAY no aprobada: {meta_file}")
        if meta.get("sha256_instancia") != digest(root / "instancias" / (name + ".txt")):
            raise ValueError(f"Hash de instancia REPLAY no coincide: {meta_file}")
        assignment, sol_obj = parse_replay_sol(source)
        reported = meta.get("primal_final")
        if reported is None:
            raise ValueError(f"Sin objetivo primal REPLAY: {meta_file}")
        if sol_obj is not None and not almost(float(sol_obj), float(reported)):
            raise ValueError(f"Objetivo del .sol no coincide con metadata: {source}")
        return assignment, source, float(reported), {"metodo": method, "validacion_origen": "SCIP checkSol y auditoría final REPLAY: TRUE", "meta_sha256": digest(meta_file)}
    raise ValueError(f"Método inválido: {method}")


def make_text(method, inst, name, assignment, source, reported, audit, root, extra):
    est, courses = inst["estudiantes"], inst["cursos"]
    prefs = inst["preferencias"]
    together = audit["preferidos_juntos"]
    f = [
        "ASIGNACION FINAL DE ESTUDIANTES POR CURSO",
        "========================================================",
        f"metodo = {method}", f"instancia = {name}",
        f"L = {inst['L']}", f"P = {inst['P']}", f"C = {inst['C']}", f"N = {inst['N']}",
        "lambda_0 = 1", "lambda_1 = 1",
        f"archivo_original = {source.relative_to(root).as_posix()}",
        f"sha256_original = {digest(source)}",
        f"verificacion_origen = {extra['validacion_origen']}",
        f"objetivo_scip_o_greedy_reportado = {reported if reported is not None else 'NO_DISPONIBLE'}",
        f"objetivo_recalculado_con_T_minimo = {audit['objetivo_recalculado']:.10g}",
        f"no_satisfechos = {inst['N'] - audit['satisfechos_recalculado']}",
        f"satisfechos = {audit['satisfechos_recalculado']}",
        f"T_recalculado = {audit['T_recalculado']:.10g}",
        "violaciones_recalculadas = 0", "auditoria_independiente = TRUE",
        "", "[ASIGNACION]",
        "estudiante;curso_origen;genero;academico;socioemocional;convivencia;curso_nuevo;preferencias;preferidos_en_mismo_curso;satisfecho"
    ]
    for i in sorted(est):
        e = est[i]
        f.append(";".join(map(str, [i, e['origen'], e['genero'], e['academico'], e['socioemocional'], e['convivencia'],
                                   assignment[i], ",".join(map(str,prefs.get(i,[]))), ",".join(map(str,together.get(i,[]))),
                                   int(bool(together.get(i)))])))
    f.extend(["", "[COMPOSICION_POR_CURSO]",
              "curso;total;capacidad;" + ";".join("genero_"+g for g in inst["grupos_genero"]) + ";"+
              ";".join("origen_"+o for o in inst["cursos_origen"]) + ";" +
              ";".join(f"{k}_{l}" for k in inst["criterios"] for l in inst["niveles"]) + ";satisfechos"])
    for c in courses:
        members = [i for i in sorted(est) if assignment[i] == c]
        cgender = [sum(est[i]["genero"] == g for i in members) for g in inst["grupos_genero"]]
        corigin = [sum(est[i]["origen"] == o for i in members) for o in inst["cursos_origen"]]
        cprof = [sum(est[i][k] == l for i in members) for k in inst["criterios"] for l in inst["niveles"]]
        csat = sum(bool(together.get(i)) for i in members)
        f.append(";".join(map(str,[c,len(members),inst["capacidad"][c],*cgender,*corigin,*cprof,csat])))
    f.append("")
    f.append("[ESTUDIANTES_POR_CURSO]")
    for c in courses:
        f.append(f"curso_{c} = " + ",".join(str(i) for i in sorted(est) if assignment[i]==c))
    f.extend(["", "[BALANCE_PERFILES]"])
    for k, v in audit["F_recalculado"].items():
        f.append(f"{k} = {v:.10g}")
    f.extend(["", "[AUDITORIA]", "solucion_auditada = TRUE", "violaciones = 0",
              f"instancia_sha256 = {digest(root / 'instancias' / (name+'.txt'))}",
              "nota = El objetivo recalculado usa T minimo. Un incumbente de SCIP puede tener T con holgura."])
    if method == "REPLAY":
        f.append("nota_replay = El costo previo de obtener el incumbente BASE no se incluye en el tiempo REPLAY.")
    return "\n".join(f) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raiz", type=Path, default=Path.cwd())
    ap.add_argument("--salida", type=Path, default=Path("entregables_txt/soluciones_L9_P3_C456"))
    args = ap.parse_args()
    root = args.raiz.expanduser().resolve()
    out = args.salida if args.salida.is_absolute() else root / args.salida
    out = out.resolve()
    if out.exists() and any(out.iterdir()):
        ap.error(f"La salida ya contiene archivos; no se sobrescribe: {out}")
    sys.path.insert(0, str(root / "src"))
    try:
        from modelo import leer_instancia
        from auditar_solucion import auditar
    except ImportError as e:
        ap.error(f"Faltan módulos del modelo y auditor en {root / 'src'}: {e}")
    outputs: dict[str, str] = {}
    errors = []
    counts = Counter()
    for c in CS:
        for i in IDX:
            name = f"c_n_9_l_3_s_{c}_i_{i}"
            ipath = root / "instancias" / (name+".txt")
            if not ipath.is_file():
                errors.append(f"{name}: falta instancia original {ipath}")
                continue
            inst = leer_instancia(ipath)
            if (inst["nombre"],inst["N"],inst["L"],inst["P"],inst["C"]) != (name,9*c,9,3,c):
                errors.append(f"{name}: identidad de instancia inconsistente")
                continue
            for method in METHODS:
                try:
                    assignment, source, reported, extra = load_method(root,method,inst,name,c,i)
                    if set(assignment)!=set(inst["estudiantes"]) or set(assignment.values())-set(inst["cursos"]):
                        raise ValueError(f"Asignación incompleta o cursos inválidos: {source}")
                    x = {(j,course):float(assignment[j]==course) for j in inst["estudiantes"] for course in inst["cursos"]}
                    audit=auditar(inst,x,1.0,1.0)
                    if audit["violaciones"] or audit["inconsistencias_objetivo"]:
                        raise ValueError(f"Auditoría independiente falló: {audit['violaciones']}, {audit['inconsistencias_objetivo']}")
                    if reported is None or not math.isfinite(reported):
                        raise ValueError(f"Objetivo reportado ausente/inválido: {source}")
                    if method=="GREEDY" and not almost(reported,audit["objetivo_recalculado"]):
                        raise ValueError(f"Greedy: objetivo reportado {reported} distinto del recalculado {audit['objetivo_recalculado']} en {source}")
                    if reported < audit["objetivo_recalculado"] - 1e-4:
                        raise ValueError(f"Objetivo reportado {reported} menor que el mínimo recalculado {audit['objetivo_recalculado']}: {source}")
                    text = make_text(method,inst,name,assignment,source,reported,audit,root,extra)
                    dest=f"{method}/sol_{name}.txt"
                    outputs[dest]=text
                    counts[method]+=1
                except Exception as e:
                    errors.append(f"{method} {name}: {e}")
    print("Resumen: " + ", ".join(f"{m}={counts[m]}/30" for m in METHODS))
    if errors or len(outputs)!=120:
        for error in errors:
            print("ERROR:",error,file=sys.stderr)
        print("ABORTADO: no se generó una entrega parcial (requiere 120 TXT válidos).", file=sys.stderr)
        return 2
    listing=["INVENTARIO DE ENTREGA - SCRP L9 P3 C4,5,6", "",
            "4 métodos por cada una de 30 instancias: GREEDY, BASE, WARM, REPLAY.",
            "120 soluciones individuales auditadas, todas en archivos .txt.",
            "Las fuentes originales permanecen intactas en NLHPC.",
            "",
            "REPLAY: generado desde final.sol; no equivale a una heurística constructiva independiente.",
            "Las auditorías previas de SCIP se verificaron y la asignación se auditó de nuevo.",
            "", "ARCHIVOS:"] + sorted(outputs)
    outputs["INVENTARIO_120.txt"]="\n".join(listing)+"\n"
    out.mkdir(parents=True,exist_ok=True)
    for filename, content in sorted(outputs.items()):
        dst=out/filename
        dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_text(content,encoding="utf-8")
    print("OK: 120 TXT de asignaciones + 1 inventario TXT.")
    print(f"Ruta de salida: {out}")
    print("No se ha realizado commit ni push automáticamente.")
    return 0

if __name__=="__main__":
    sys.exit(main())
