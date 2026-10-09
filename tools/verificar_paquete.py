# -*- coding: utf-8 -*-
from pathlib import Path
import hashlib, sys
ROOT=Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT/'src' if (ROOT/'src'/'modelo.py').exists() else ROOT/'src_referencia'
sys.path.insert(0,str(MODEL_DIR))
from modelo import leer_instancia
files=[]
for courses in (4, 5, 6):
    files.extend(sorted((ROOT/'instancias').glob(f'c_n_9_l_3_s_{courses}_i_*.txt')))
assert len(files)==30, f'Se esperaban 30 instancias, hay {len(files)}'
names=[]
for f in files:
    inst=leer_instancia(f)
    names.append(inst['nombre'])
assert len(set(names))==30, 'Hay nombres duplicados'
fams={}
for f in files:
    inst=leer_instancia(f)
    fams.setdefault((inst['L'],inst['P'],inst['C']),0)
    fams[(inst['L'],inst['P'],inst['C'])]+=1
expected={(9,3,4):10,(9,3,5):10,(9,3,6):10}
assert fams==expected, f'Familias inesperadas: {fams}'
print('OK: 30 instancias únicas y parseables')
print('OK: familias', fams)
print('NOTA: los testigos no están incluidos deliberadamente')
