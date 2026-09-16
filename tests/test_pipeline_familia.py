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
from types import SimpleNamespace
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


class ResumenGlobalTest(unittest.TestCase):
    """Postproceso puro: no importa PySCIPOpt ni construye modelos SCIP."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.a = SimpleNamespace(L=9, P=3, C=4, tiempo=3600., hilos=1,
                                 gap=0., lambda_0=1., lambda_1=1., replicas=list(range(10)))
        self.ruta = self.out / "resumen_global_familia_L9_P3_C4.txt"
        self.filas = []
        for i in range(10):
            r = {c: None for c in rf.COLUMNAS}
            r.update(instancia=f"c_n_9_l_3_s_4_i_{i}", replica=i,
                     estado="optimal" if i % 2 == 0 else "timelimit_with_incumbent",
                     tiempo_scip_seg=10.+i, tiempo_total_seg=20.+i,
                     primal_bound=10. if i % 2 == 0 else 15., dual_bound=10.,
                     gap=0. if i % 2 == 0 else .5, gap_absoluto=0. if i % 2 == 0 else 5.,
                     nodos=100+i, T=5., suma_z=31 if i % 2 == 0 else 26,
                     tiempo_primera_solucion_factible=1.+i,
                     tiempo_mejor_incumbente_final=2.+i,
                     tiene_incumbente=True, solucion_auditada=True)
            self.filas.append(r)

    def generar(self, filas):
        # Cualquier import accidental del solver haria fallar estas pruebas.
        with patch.dict(sys.modules, {"pyscipopt": None}):
            rf.resumir(filas, self.a, "simulacion_test", self.out)
        return self.ruta.read_text(encoding="utf-8")

    def test_txt_global_familia_completa_diez_replicas(self):
        contenido = self.generar(list(reversed(self.filas)))
        self.assertEqual([s for s in contenido.splitlines() if s.startswith("[i_")],
                         [f"[i_{i}]" for i in range(10)])
        for i in range(10):
            bloque = contenido.split(f"[i_{i}]\n", 1)[1].split("\n\n", 1)[0]
            campos = dict(line.split(": ", 1) for line in bloque.splitlines())
            self.assertEqual(campos, {
                "replica": f"i_{i}", "instancia": f"c_n_9_l_3_s_4_i_{i}",
                "estado": "optimal" if i % 2 == 0 else "timelimit_with_incumbent",
                "tiempo_scip_seg": str(10.+i), "tiempo_total_seg": str(20.+i),
                "primal_bound": "10.0" if i % 2 == 0 else "15.0", "dual_bound": "10.0",
                "gap_relativo": "0.0" if i % 2 == 0 else "0.5",
                "gap_absoluto": "0.0" if i % 2 == 0 else "5.0", "nodos": str(100+i),
                "T": "5.0", "suma_z": "31" if i % 2 == 0 else "26",
                "tiempo_primera_solucion_factible_seg": str(1.+i), "auditoria": "APROBADA"})
        with (self.out / "resumen_familia.csv").open(encoding="utf-8") as f:
            resumen = next(csv.DictReader(f))
        for clave in ("numero_replicas", "numero_optimas", "numero_time_limit_con_incumbente",
                      "numero_time_limit_sin_incumbente", "numero_infeasible_demostradas",
                      "numero_errores", "tiempo_scip_promedio_seg", "tiempo_scip_desviacion_estandar_seg",
                      "tiempo_total_promedio_seg", "tiempo_total_desviacion_estandar_seg",
                      "gap_promedio", "gap_desviacion_estandar"):
            self.assertIn(f"{clave}: {resumen[clave]}\n", contenido)
        self.assertIn("numero_replicas: 10\n", contenido)
        self.assertIn("numero_optimas: 5\n", contenido)
        self.assertIn("numero_time_limit_con_incumbente: 5\n", contenido)
        self.assertIn("tiempo_scip_promedio_seg: 14.5\n", contenido)
        self.assertIn("tiempo_total_promedio_seg: 24.5\n", contenido)
        self.assertIn("gap_promedio: 0.25\n", contenido)
        self.assertIn(f"gap_desviacion_estandar: {statistics.stdev([0., .5]*5):.6f}\n", contenido)
        self.assertTrue((self.out / "resumen_familia.md").is_file())

    def test_txt_parcial_y_sin_incumbente_no_inventa_ceros(self):
        r = self.filas[0]
        r.update(estado="timelimit_without_incumbent", tiene_incumbente=False,
                 solucion_auditada=None, primal_bound=math.inf, gap=math.inf,
                 gap_absoluto=None, T=None, suma_z=None,
                 tiempo_primera_solucion_factible=None, tiempo_mejor_incumbente_final=None)
        contenido = self.generar([r])
        self.assertEqual(contenido.count("estado: pendiente\n"), 9)
        self.assertIn("auditoria: NO APLICA (sin incumbente)\n", contenido)
        self.assertIn("primal_bound: inf\n", contenido)
        self.assertIn("T: NO DISPONIBLE\n", contenido)
        self.assertIn("numero_replicas: 1\n", contenido)
        self.assertIn("numero_time_limit_sin_incumbente: 1\n", contenido)
        self.assertIn("tiempo_scip_desviacion_estandar_seg: NO DISPONIBLE\n", contenido)
        self.assertIn("gap_promedio: NO DISPONIBLE\n", contenido)

    def test_txt_conteos_infeasible_error_y_auditoria_fallida(self):
        self.filas[0].update(estado="infeasible", tiene_incumbente=False,
                             solucion_auditada=None)
        self.filas[1].update(estado="error", tiene_incumbente=None,
                             solucion_auditada=None)
        self.filas[2]["solucion_auditada"] = False
        contenido = self.generar(self.filas)
        self.assertIn("numero_infeasible_demostradas: 1\n", contenido)
        self.assertIn("numero_errores: 1\n", contenido)
        self.assertIn("auditoria: FALLIDA\n", contenido)


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
