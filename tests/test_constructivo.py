from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "src" if (ROOT / "src" / "modelo.py").exists() else ROOT / "src_referencia"
sys.path[:0] = [
    str(MODEL_DIR),
    str(ROOT / "tools"),
    str(ROOT / "experimento_constructivo"),
]

from modelo import leer_instancia, construir_modelo  # noqa: E402
from evaluar_asignacion import evaluar as evaluar_independiente  # noqa: E402
from constructivo import construct_solution, violations_by_constraint  # noqa: E402
from comparar_warm_start import complete_solution_values  # noqa: E402


INSTANCE = ROOT / "instancias" / "c_n_9_l_3_s_4_i_0.txt"


class ConstructiveTests(unittest.TestCase):
    def test_constructive_is_feasible_and_independently_validated(self):
        inst = leer_instancia(INSTANCE)
        assignment, _ = construct_solution(
            inst, seed=12345, attempts=2, node_limit_per_attempt=20000, improve=False
        )
        self.assertIsNotNone(assignment)
        self.assertTrue(violations_by_constraint(inst, assignment)["factible"])
        self.assertTrue(evaluar_independiente(inst, assignment)["factible"])

    def test_warm_start_values_cover_every_model_variable_and_are_accepted(self):
        inst = leer_instancia(INSTANCE)
        assignment, _ = construct_solution(
            inst, seed=54321, attempts=2, node_limit_per_attempt=20000, improve=False
        )
        model, _ = construir_modelo(inst, tiempo=0.2, hilos=1, gap=0.0)
        values = complete_solution_values(inst, assignment)
        by_name = {var.name: var for var in model.getVars()}
        self.assertEqual(set(values), set(by_name))

        solution = model.createSol()
        for name, var in by_name.items():
            model.setSolVal(solution, var, values[name])
        self.assertTrue(model.checkSol(solution, printreason=True, completely=True, original=True))
        self.assertTrue(model.addSol(solution, free=True))

    def test_no_testigo_dependency_in_implementation(self):
        implementation = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "experimento_constructivo").glob("*.py")
        ).lower()
        self.assertNotIn("testigos/", implementation)
        self.assertNotIn("testigo_", implementation)


if __name__ == "__main__":
    unittest.main()
