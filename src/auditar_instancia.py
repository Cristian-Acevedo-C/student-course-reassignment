# -*- coding: utf-8 -*-
"""Verifica que una instancia es coherente y que su testigo es factible."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from modelo import leer_instancia

ap = argparse.ArgumentParser()
ap.add_argument("--instancia", required=True)
ap.add_argument("--testigo", required=True)
a = ap.parse_args()

inst = leer_instancia(a.instancia)
testigo = {}
for linea in Path(a.testigo).read_text(encoding="utf-8").splitlines():
    s = linea.strip()
    if not s or s.startswith("#") or s.startswith("estudiante;"):
        continue
    i, c = s.split(";")
    testigo[int(i)] = int(c)

S = sorted(inst["estudiantes"]); est = inst["estudiantes"]; C = inst["cursos"]
ok, fallas = 0, []
def chk(cond, msg):
    global ok
    if cond: ok += 1
    else: fallas.append(msg)

# coherencia del archivo
chk(len(S) == inst["N"], "N no calza con la cantidad de estudiantes")
chk(len(C) == inst["C"], "C no calza con la cantidad de cursos")
chk(sum(inst["capacidad"].values()) == inst["N"], "capacidad total != N")
for i in S:
    p = inst["preferencias"][i]
    chk(len(p) == inst["P"], f"estudiante {i}: {len(p)} preferencias != P")
    chk(i not in p, f"estudiante {i} se nombra a si mismo")
    chk(len(set(p)) == len(p), f"estudiante {i} tiene preferencias repetidas")
    chk(all(1 <= j <= inst["N"] for j in p), f"estudiante {i}: preferencia fuera de rango")
sep = inst["separaciones"]
chk(len(set(tuple(sorted(t)) for t in sep)) == len(sep), "separaciones repetidas")
chk(all(a2 != b2 for a2, b2 in sep), "separacion de un alumno consigo mismo")

# factibilidad del testigo
chk(set(testigo) == set(S), "el testigo no cubre a todos los estudiantes")
for c in C:
    chk(sum(1 for i in S if testigo[i] == c) <= inst["capacidad"][c], f"capacidad curso {c}")
for a2, b2 in sep:
    chk(testigo[a2] != testigo[b2], f"separacion violada {a2}-{b2}")
for g in inst["grupos_genero"]:
    cu = [sum(1 for i in S if testigo[i] == c and est[i]["genero"] == g) for c in C]
    chk(max(cu)-min(cu) <= inst["delta_genero"], f"genero {g}: {cu}")
for o in inst["cursos_origen"]:
    for c in C:
        n = sum(1 for i in S if testigo[i] == c and est[i]["origen"] == o)
        chk(n >= inst["alpha"][o], f"origen {o}->{c}: {n} < {inst['alpha'][o]}")

print(f"instancia      : {inst['nombre']}")
print(f"N={inst['N']}  C={inst['C']}  L={inst['L']}  P={inst['P']}  alpha={list(inst['alpha'].values())[0]}")
print(f"separaciones   : {len(sep)}")
print(f"arcos pref.    : {sum(len(v) for v in inst['preferencias'].values())}")
print(f"comprobaciones : {ok}")
print(f"violaciones    : {len(fallas)}")
for f in fallas[:15]: print("   !", f)

# reparto observado
print("\nreparto del testigo:")
for c in C:
    mi = [i for i in S if testigo[i] == c]
    gen = "/".join(f"{sum(1 for i in mi if est[i]['genero']==g)}{g}" for g in inst["grupos_genero"])
    org = "/".join(str(sum(1 for i in mi if est[i]["origen"]==o)) for o in inst["cursos_origen"])
    print(f"  curso {c}: n={len(mi)}  genero {gen}  origen {org}")

if fallas:
    sys.exit(1)
