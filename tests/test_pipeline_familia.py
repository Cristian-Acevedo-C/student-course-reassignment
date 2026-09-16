"""Regresiones del pipeline sin optimizar ninguna instancia ni leer testigos."""
import contextlib
import csv
import io
import json
import math
from pathlib import Path
import statistics
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import resolver_familia as rf
from auditar_solucion import auditar


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "corrida"
        self.llamadas = []

    def replica_simulada(self, ruta, out, a, modo):
        i = int(ruta.stem.rsplit("_", 1)[1])
        self.llamadas.append(i)
        r = {c: None for c in rf.COLUMNAS}
        tiene = i % 3 != 2
        r.update(instancia=ruta.stem, L=a.L, P=a.P, C=a.C, replica=i, N=a.L*a.C,
                 semilla=i, sha256_instancia=rf.sha256(ruta), modo=modo,
                 estado=("optimal" if i % 3 == 0 else "timelimit_with_incumbent"
                         if tiene else "timelimit_without_incumbent"),
                 estado_scip="optimal" if i % 3 == 0 else "timelimit",
                 limite_seg=a.tiempo, hilos=a.hilos, gap_objetivo=a.gap,
                 lambda_0=a.lambda_0, lambda_1=a.lambda_1,
                 tiempo_total_seg=10.+i, tiempo_scip_seg=9.+i,
                 tiene_incumbente=tiene, solucion_auditada=True if tiene else None,
                 gap=(0. if i % 3 == 0 else .5) if tiene else math.inf,
                 gap_absoluto=1. if tiene else None,
                 tiempo_primera_solucion_factible=1. if tiene else None,
                 tiempo_mejor_incumbente_final=2. if tiene else None, nodos=i+1)
        claves = ["log_scip", "stats_scip", "stats_json", "trayectoria_incumbentes",
                  "trayectoria_log", "solucion", "auditoria"]
        if tiene:
            claves.append("solucion_completa")
        hashes = {}
        for c in claves:
            archivo = out / f"{ruta.stem}_{c}.txt"
            archivo.write_text(f"SIMULACION {i} {c}", encoding="utf-8")
            r[c] = archivo.name
            hashes[c] = rf.sha256(archivo)
        r["artefactos_sha256"] = json.dumps(hashes)
        return r

    def ejecutar(self, *extra, resolver=None):
        args = ["resolver_familia.py", "--L", "9", "--P", "3", "--C", "4",
                "--salida", str(self.out), *extra]
        with patch.object(sys, "argv", args), \
             patch.object(rf, "resolver_replica", side_effect=resolver or self.replica_simulada), \
             patch.object(rf, "escribir_entorno"), contextlib.redirect_stdout(io.StringIO()):
            try:
                rf.main()
            except SystemExit as exc:
                return exc.code
        return 0

    def filas(self):
        with (self.out / "resultados_familia.csv").open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def test_diez_secuenciales_optimo_y_time_limit(self):
        self.assertEqual(self.ejecutar(), 0)
        self.assertEqual(self.llamadas, list(range(10)))
        self.assertEqual([int(r["replica"]) for r in self.filas()], list(range(10)))
        with (self.out / "resumen_familia.csv").open(encoding="utf-8") as f:
            resumen = next(csv.DictReader(f))
        self.assertEqual(resumen["familia_completa"], "TRUE")
        self.assertEqual(float(resumen["tiempo_scip_promedio_seg"]), 13.5)
        self.assertEqual(float(resumen["tiempo_total_promedio_seg"]), 14.5)
        self.assertAlmostEqual(float(resumen["tiempo_scip_desviacion_estandar_seg"]),
                               statistics.stdev(range(9, 19)), places=5)
        self.assertAlmostEqual(float(resumen["gap_promedio"]), 1.5 / 7, places=5)
        self.assertAlmostEqual(float(resumen["gap_desviacion_estandar"]),
                               statistics.stdev([0, .5, 0, .5, 0, .5, 0]), places=5)

    def test_reanudar_completa_no_resuelve(self):
        self.ejecutar()
        original = (self.out / "resultados_familia.csv").read_bytes()
        self.llamadas.clear()
        self.assertEqual(self.ejecutar("--reanudar"), 0)
        self.assertEqual(self.llamadas, [])
        self.assertEqual(original, (self.out / "resultados_familia.csv").read_bytes())

    def test_reanudacion_tras_interrupcion_solo_pendientes(self):
        def interrumpir(ruta, *args):
            if ruta.stem.endswith("_3"):
                raise KeyboardInterrupt
            return self.replica_simulada(ruta, *args)
        self.assertEqual(self.ejecutar(resolver=interrumpir), 130)
        self.assertEqual(len(self.filas()), 3)
        self.llamadas.clear()
        self.assertEqual(self.ejecutar("--reanudar"), 0)
        self.assertEqual(self.llamadas, list(range(3, 10)))

    def test_otra_interrupcion_no_pierde_terminadas_posteriores(self):
        self.ejecutar()
        filas = self.filas()
        (self.out / filas[2]["stats_json"]).unlink()
        self.assertEqual(self.ejecutar("--reanudar", resolver=lambda *args: (_ for _ in ()).throw(KeyboardInterrupt())), 130)
        self.assertEqual([int(r["replica"]) for r in self.filas()], [0, 1, 3, 4, 5, 6, 7, 8, 9])
        self.llamadas.clear()
        self.assertEqual(self.ejecutar("--reanudar"), 0)
        self.assertEqual(self.llamadas, [2])

    def test_fila_error_es_pendiente_no_error_conversion(self):
        def fallar(ruta, *args):
            if ruta.stem.endswith("_4"):
                raise RuntimeError("fallo simulado")
            return self.replica_simulada(ruta, *args)
        self.assertEqual(self.ejecutar(resolver=fallar), 1)
        self.llamadas.clear()
        self.assertEqual(self.ejecutar("--reanudar"), 0)
        self.assertEqual(self.llamadas, [4])

    def test_rechaza_protocolo_o_version_incompatibles_sin_sobrescribir(self):
        self.ejecutar()
        original = (self.out / "resultados_familia.csv").read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.ejecutar("--reanudar", "--tiempo", "123"), 2)
            with patch.object(rf, "versiones_solver", return_value={"pyscipopt": "6.2.1", "scip": "10.0.1"}):
                self.assertEqual(self.ejecutar("--reanudar"), 2)
        self.assertEqual(original, (self.out / "resultados_familia.csv").read_bytes())

    def test_preflight_python_default_solo_cero_y_60s(self):
        self.assertEqual(self.ejecutar("--preflight"), 0)
        self.assertEqual(self.llamadas, [0])
        self.assertEqual(float(self.filas()[0]["limite_seg"]), 60)
        self.assertEqual(self.filas()[0]["modo"], "preflight")

    def test_subconjunto_fuera_preflight_rechazado(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.ejecutar("--replicas", "0", "1"), 2)
        self.assertFalse(self.out.exists())

    def test_threads_efectivos_sin_optimizar(self):
        from pyscipopt import Model
        m = Model()
        rf.configurar_scip(m, 1)
        self.assertEqual(m.getParam("lp/threads"), 1)
        self.assertEqual(m.getParam("parallel/maxnthreads"), 1)
        self.assertEqual(m.getParam("timing/clocktype"), 2)
        self.assertEqual(rf.verificar_versiones(m, "oficial"), rf.VERSIONES_OFICIALES)
        m.freeProb()

    def test_csv_atomico_conserva_anterior_si_falla_replace(self):
        ruta = Path(self.tmp.name) / "resultados.csv"
        ruta.write_text("anterior", encoding="utf-8")
        with patch.object(rf.os, "replace", side_effect=OSError("fallo simulado")):
            with self.assertRaises(OSError):
                rf.escribir_resultados(ruta, [])
        self.assertEqual(ruta.read_text(), "anterior")


class AuditoriaTest(unittest.TestCase):
    def test_igualdad_exacta_rechaza_ambos_sentidos(self):
        inst = {"estudiantes": {i: {"origen": "A", "genero": "M"} for i in (1, 2)},
                "cursos": [1], "capacidad": {1: 2}, "separaciones": [],
                "grupos_genero": ["M"], "delta_genero": 0,
                "cursos_origen": ["A"], "alpha": {"A": 0},
                "preferencias": {1: [2], 2: [1]}, "criterios": [], "niveles": []}
        x = {(1, 1): 1., (2, 1): 1.}
        for suma_z in (1, 2, 3, 2.00000001):
            with self.subTest(suma_z=suma_z):
                resultado = auditar(inst, x, 1, 1, suma_z_solver=suma_z)
                self.assertEqual(resultado["solucion_auditada"], suma_z == 2)


if __name__ == "__main__":
    unittest.main()
