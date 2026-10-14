# -*- coding: utf-8 -*-
"""Evalúa una asignación heurística contra la instancia SCRP SIN usar SCIP.

Uso:
  python tools/evaluar_asignacion.py --instancia instancias/c_n_9_l_3_s_4_i_0.txt --asignacion salida.csv

Formato de asignación: dos columnas separadas por ; o ,: estudiante;curso
Se permiten líneas de comentario iniciadas con #.
"""
from pathlib import Path
import argparse, csv, json, sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src_referencia'))
from modelo import leer_instancia


def leer_asignacion(ruta):
    d = {}
    for raw in Path(ruta).read_text(encoding='utf-8').splitlines():
        s = raw.strip()
        if not s or s.startswith('#'):
            continue
        if ';' in s:
            parts = [x.strip() for x in s.split(';')]
        else:
            parts = [x.strip() for x in s.split(',')]
        if len(parts) < 2:
            continue
        try:
            i, c = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        d[i] = c
    return d


def evaluar(inst, a, lambda_0=1.0, lambda_1=1.0):
    S = sorted(inst['estudiantes'])
    C = list(inst['cursos'])
    est = inst['estudiantes']
    errores = []

    faltan = sorted(set(S)-set(a))
    extras = sorted(set(a)-set(S))
    if faltan: errores.append(f'faltan estudiantes: {faltan[:20]}')
    if extras: errores.append(f'estudiantes desconocidos: {extras[:20]}')
    invalidos = [(i,c) for i,c in a.items() if c not in C]
    if invalidos: errores.append(f'cursos inválidos: {invalidos[:20]}')

    if errores:
        return {'factible': False, 'violaciones': errores}

    # capacidad
    for c in C:
        n = sum(1 for i in S if a[i] == c)
        if n > inst['capacidad'][c]:
            errores.append(f'capacidad curso {c}: {n}>{inst["capacidad"][c]}')

    # separaciones
    for i,j in inst['separaciones']:
        if a[i] == a[j]:
            errores.append(f'separación violada: {i}-{j} en curso {a[i]}')

    # balance de género
    for g in inst['grupos_genero']:
        cuentas = [sum(1 for i in S if a[i]==c and est[i]['genero']==g) for c in C]
        if max(cuentas)-min(cuentas) > inst['delta_genero']:
            errores.append(f'balance género {g}: {cuentas}, delta={inst["delta_genero"]}')

    # representación de origen
    for o in inst['cursos_origen']:
        for c in C:
            n = sum(1 for i in S if a[i]==c and est[i]['origen']==o)
            if n < inst['alpha'][o]:
                errores.append(f'origen {o}->curso {c}: {n}<{inst["alpha"][o]}')

    # preferencias z_i
    n_pref_mismo = {}
    z = {}
    for i in S:
        n_pref_mismo[i] = sum(1 for j in inst['preferencias'].get(i,[]) if a[j]==a[i])
        z[i] = 1 if n_pref_mismo[i] >= 1 else 0
    suma_z = sum(z.values())

    # F_k mínimo compatible con x: suma de desviaciones absolutas respecto del promedio
    F = {}
    detalle = {}
    for k in inst['criterios']:
        total = 0.0
        detalle[k] = {}
        for l in inst['niveles']:
            miembros = [i for i in S if est[i][k] == l]
            promedio = len(miembros)/len(C)
            cuentas = [sum(1 for i in miembros if a[i]==c) for c in C]
            desv = [abs(v-promedio) for v in cuentas]
            total += sum(desv)
            detalle[k][str(l)] = {'promedio': promedio, 'cuentas': cuentas, 'desv_abs': desv}
        F[k] = total
    T = max(F.values()) if F else 0.0
    obj = lambda_0*(inst['N']-suma_z) + lambda_1*T

    return {
        'factible': len(errores)==0,
        'violaciones': errores,
        'N': inst['N'], 'C': inst['C'], 'L': inst['L'], 'P': inst['P'],
        'suma_z': suma_z,
        'no_satisfechos': inst['N']-suma_z,
        'T': T,
        'F': F,
        'objetivo': obj,
        'lambda_0': lambda_0,
        'lambda_1': lambda_1,
        'preferidos_mismo_curso': n_pref_mismo,
        'detalle_balance': detalle,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--instancia', required=True)
    ap.add_argument('--asignacion', required=True)
    ap.add_argument('--lambda-0', type=float, default=1.0)
    ap.add_argument('--lambda-1', type=float, default=1.0)
    ap.add_argument('--json', action='store_true')
    args=ap.parse_args()
    inst=leer_instancia(args.instancia)
    a=leer_asignacion(args.asignacion)
    r=evaluar(inst,a,args.lambda_0,args.lambda_1)
    if args.json:
        print(json.dumps(r,ensure_ascii=False,indent=2))
    else:
        print('instancia       :', inst['nombre'])
        print('factible        :', r['factible'])
        if 'objetivo' in r:
            print('objetivo        :', r['objetivo'])
            print('T               :', r['T'])
            print('suma_z          :', r['suma_z'])
            print('no_satisfechos  :', r['no_satisfechos'])
            print('F               :', r['F'])
        print('violaciones     :', len(r['violaciones']))
        for x in r['violaciones'][:30]: print('  !', x)
    raise SystemExit(0 if r['factible'] else 2)

if __name__=='__main__': main()
