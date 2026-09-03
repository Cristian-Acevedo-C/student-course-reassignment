# -*- coding: utf-8 -*-
"""Validación estructural del repositorio sin ejecutar el solver.

Comprueba la grilla vigente de 480 instancias, sus testigos de factibilidad y
la coherencia interna de los resultados versionados del ejemplo I00C.
"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modelo import leer_instancia  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
INSTANCES_DIR = ROOT / "instancias"
WITNESSES_DIR = ROOT / "testigos"
L_VALUES = (9, 18, 27, 36)
P_VALUES = (3, 5, 7)
C_VALUES = (4, 5, 6, 7)
REPLICAS = tuple(range(10))

I00C_DIR = ROOT / "experimentos" / "sensibilidad_lambda"
I00C_INSTANCE_DIR = I00C_DIR / "instancia" / "I00C_DRAFT_ILUSTRATIVO_27"
I00C_RESULTS_DIR = I00C_DIR / "resultados"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_witness(path: Path) -> dict[int, int]:
    witness: dict[int, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#") or value.startswith("estudiante;"):
            continue
        student, course = value.split(";")
        witness[int(student)] = int(course)
    return witness


def validate_grid(errors: list[str]) -> None:
    expected = {
        f"c_n_{length}_l_{preferences}_s_{courses}_i_{replica}.txt"
        for length, preferences, courses, replica in itertools.product(
            L_VALUES, P_VALUES, C_VALUES, REPLICAS
        )
    }
    expected_witnesses = {f"testigo_{name}" for name in expected}
    actual = {path.name for path in INSTANCES_DIR.glob("*.txt")}
    actual_witnesses = {path.name for path in WITNESSES_DIR.glob("*.txt")}

    for name in sorted(expected - actual):
        errors.append(f"Falta la instancia {name}")
    for name in sorted(actual - expected):
        errors.append(f"Instancia fuera de la grilla vigente: {name}")
    for name in sorted(expected_witnesses - actual_witnesses):
        errors.append(f"Falta el testigo {name}")
    for name in sorted(actual_witnesses - expected_witnesses):
        errors.append(f"Testigo fuera de la grilla vigente: {name}")

    seeds: set[int] = set()
    hashes: set[str] = set()
    by_courses: Counter[int] = Counter()

    for length, preferences, courses, replica in itertools.product(
        L_VALUES, P_VALUES, C_VALUES, REPLICAS
    ):
        name = f"c_n_{length}_l_{preferences}_s_{courses}_i_{replica}.txt"
        instance_path = INSTANCES_DIR / name
        witness_path = WITNESSES_DIR / f"testigo_{name}"
        if not instance_path.is_file() or not witness_path.is_file():
            continue

        try:
            instance = leer_instancia(instance_path)
            witness = read_witness(witness_path)
        except Exception as exc:  # continúa para informar todos los archivos defectuosos
            errors.append(f"{name}: no se pudo leer ({exc})")
            continue

        prefix = f"{name}:"
        students = sorted(instance["estudiantes"])
        course_ids = instance["cursos"]
        expected_n = length * courses
        by_courses[courses] += 1

        if instance["nombre"] != name.removesuffix(".txt"):
            errors.append(f"{prefix} nombre interno inconsistente")
        if (instance["L"], instance["P"], instance["C"], instance["N"]) != (
            length,
            preferences,
            courses,
            expected_n,
        ):
            errors.append(f"{prefix} parámetros internos inconsistentes")
        if len(students) != expected_n or len(course_ids) != courses:
            errors.append(f"{prefix} dimensiones inconsistentes")
        if sum(instance["capacidad"].values()) != expected_n:
            errors.append(f"{prefix} capacidad total distinta de N")

        for student in students:
            selected = instance["preferencias"].get(student, [])
            if len(selected) != preferences:
                errors.append(f"{prefix} estudiante {student} no tiene P preferencias")
            if student in selected or len(selected) != len(set(selected)):
                errors.append(f"{prefix} preferencias inválidas para {student}")
            if any(peer not in instance["estudiantes"] for peer in selected):
                errors.append(f"{prefix} preferencia fuera del conjunto de estudiantes")

        separations = instance["separaciones"]
        normalized = [tuple(sorted(pair)) for pair in separations]
        if len(normalized) != len(set(normalized)) or any(a == b for a, b in normalized):
            errors.append(f"{prefix} pares de separación inválidos")

        if set(witness) != set(students):
            errors.append(f"{prefix} el testigo no cubre exactamente a los estudiantes")
            continue
        if any(course not in course_ids for course in witness.values()):
            errors.append(f"{prefix} el testigo usa un curso inexistente")
            continue

        for course in course_ids:
            assigned = sum(witness[student] == course for student in students)
            if assigned > instance["capacidad"][course]:
                errors.append(f"{prefix} el testigo excede la capacidad del curso {course}")
        for student_a, student_b in separations:
            if witness[student_a] == witness[student_b]:
                errors.append(f"{prefix} el testigo viola separación {student_a}-{student_b}")
        for gender in instance["grupos_genero"]:
            counts = [
                sum(
                    witness[student] == course
                    and instance["estudiantes"][student]["genero"] == gender
                    for student in students
                )
                for course in course_ids
            ]
            if max(counts) - min(counts) > instance["delta_genero"]:
                errors.append(f"{prefix} el testigo viola el balance de género {gender}")
        for origin in instance["cursos_origen"]:
            for course in course_ids:
                count = sum(
                    witness[student] == course
                    and instance["estudiantes"][student]["origen"] == origin
                    for student in students
                )
                if count < instance["alpha"][origin]:
                    errors.append(f"{prefix} el testigo viola representación {origin}->{course}")

        seed = instance["semilla"]
        if seed in seeds:
            errors.append(f"{prefix} semilla repetida {seed}")
        seeds.add(seed)
        digest = hashlib.sha256(instance_path.read_bytes()).hexdigest()
        if digest in hashes:
            errors.append(f"{prefix} contenido duplicado")
        hashes.add(digest)

    if len(seeds) != 480:
        errors.append(f"Se esperaban 480 semillas únicas y se encontraron {len(seeds)}")
    if len(hashes) != 480:
        errors.append(f"Se esperaban 480 contenidos únicos y se encontraron {len(hashes)}")
    if by_courses != Counter({4: 120, 5: 120, 6: 120, 7: 120}):
        errors.append(f"Distribución por C incorrecta: {dict(by_courses)}")


def academic_level(value: str) -> int:
    grade = float(value)
    if grade < 4.0:
        return 1
    if grade < 5.5:
        return 2
    return 3


def validate_i00c_assignment(
    meta: dict,
    students: list[dict[str, str]],
    separations: list[tuple[str, str]],
    assignment: dict[str, str],
) -> dict:
    ids = [row["student_id"] for row in students]
    by_id = {row["student_id"]: row for row in students}
    destinations = meta["destination_courses"]
    problems: list[str] = []

    if set(assignment) != set(ids):
        problems.append("la asignación no cubre exactamente los 27 estudiantes")
        return {"problems": problems}
    if any(course not in destinations for course in assignment.values()):
        problems.append("la asignación contiene un curso destino desconocido")
        return {"problems": problems}

    counts = Counter(assignment.values())
    if any(counts[course] > int(meta["capacity"]["maximum"]) for course in destinations):
        problems.append("se excede la capacidad")
    for student_a, student_b in separations:
        if assignment[student_a] == assignment[student_b]:
            problems.append(f"se viola la separación {student_a}-{student_b}")
    for gender in sorted({row["gender"] for row in students}):
        values = [
            sum(row["gender"] == gender and assignment[row["student_id"]] == course for row in students)
            for course in destinations
        ]
        if max(values) - min(values) > int(meta["gender_delta"]):
            problems.append(f"se viola el balance de género {gender}")
    for origin, minimum in meta["origin_alpha"].items():
        for course in destinations:
            value = sum(
                row["origin_course"] == origin and assignment[row["student_id"]] == course
                for row in students
            )
            if value < int(minimum):
                problems.append(f"se viola representación {origin}->{course}")

    preferences: dict[str, list[str]] = {}
    for student in ids:
        preferences[student] = [
            by_id[student][f"pref_{index}"].strip()
            for index in range(1, 6)
            if by_id[student][f"pref_{index}"].strip()
        ]
    satisfied_by_student = {
        student: any(assignment[student] == assignment[peer] for peer in preferences[student])
        for student in ids
    }
    satisfied = sum(satisfied_by_student.values())

    criteria = {
        "academic": {student: academic_level(by_id[student]["grade_average"]) for student in ids},
        "socioemotional": {
            student: int(by_id[student]["socioemotional_level"]) for student in ids
        },
        "convivencia": {
            student: int(by_id[student]["convivencia_level"]) for student in ids
        },
    }
    dispersions: dict[str, float] = {}
    for criterion, values in criteria.items():
        total = 0.0
        for level in (1, 2, 3):
            members = [student for student in ids if values[student] == level]
            average = len(members) / len(destinations)
            total += sum(
                abs(sum(assignment[student] == course for student in members) - average)
                for course in destinations
            )
        dispersions[criterion] = total

    flows = {
        origin: "/".join(
            str(
                sum(
                    row["origin_course"] == origin
                    and assignment[row["student_id"]] == destination
                    for row in students
                )
            )
            for destination in destinations
        )
        for origin in meta["origin_courses"]
    }
    return {
        "problems": problems,
        "satisfied": satisfied,
        "unsatisfied": len(ids) - satisfied,
        "satisfied_by_student": satisfied_by_student,
        "F": dispersions,
        "T": max(dispersions.values()),
        "flows": flows,
    }


def validate_i00c(errors: list[str]) -> None:
    required = [
        I00C_INSTANCE_DIR / "instance.json",
        I00C_INSTANCE_DIR / "students.csv",
        I00C_INSTANCE_DIR / "separations.csv",
        I00C_INSTANCE_DIR / "reference_solution.csv",
        I00C_RESULTS_DIR / "sensibilidad_lambda_i00c.csv",
        I00C_RESULTS_DIR / "asignaciones_sensibilidad_i00c.csv",
        I00C_RESULTS_DIR / "sensibilidad_lambda_i00c.json",
        I00C_DIR / "figuras" / "fig_i00c_flujos_origen_destino.pdf",
        I00C_DIR / "figuras" / "fig_i00c_flujos_origen_destino.png",
        I00C_DIR / "latex" / "DRAFT_UPDATE_I00C_LAMBDA_SENSITIVITY.tex",
        I00C_DIR / "latex" / "tabla_sensibilidad_lambda_i00c.tex",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        errors.extend(f"Falta el archivo I00C {path}" for path in missing)
        return

    meta = json.loads((I00C_INSTANCE_DIR / "instance.json").read_text(encoding="utf-8"))
    students = read_csv(I00C_INSTANCE_DIR / "students.csv")
    separations = [
        (row["student_i"], row["student_j"])
        for row in read_csv(I00C_INSTANCE_DIR / "separations.csv")
    ]
    reference = {
        row["student_id"]: row["destination_course"]
        for row in read_csv(I00C_INSTANCE_DIR / "reference_solution.csv")
    }
    if meta["instance_id"] != "I00C_DRAFT_ILUSTRATIVO_27" or len(students) != 27:
        errors.append("La instancia I00C no coincide con su identidad o tamaño documentado")
    if len(separations) != 8:
        errors.append("I00C no contiene los 8 pares de separación documentados")

    reference_audit = validate_i00c_assignment(meta, students, separations, reference)
    if reference_audit["problems"]:
        errors.extend(f"I00C referencia: {problem}" for problem in reference_audit["problems"])
    if (
        reference_audit.get("unsatisfied") != 1
        or not math.isclose(reference_audit.get("T", -1), 14 / 3, abs_tol=1e-9)
        or reference_audit.get("flows") != {"8A": "3/3/3", "8B": "4/2/3", "8C": "2/4/3"}
    ):
        errors.append("La solución de referencia no reproduce U=1, T=14/3 y los flujos del draft")

    summaries = read_csv(I00C_RESULTS_DIR / "sensibilidad_lambda_i00c.csv")
    assignments_rows = read_csv(I00C_RESULTS_DIR / "asignaciones_sensibilidad_i00c.csv")
    json_payload = json.loads(
        (I00C_RESULTS_DIR / "sensibilidad_lambda_i00c.json").read_text(encoding="utf-8")
    )
    expected = {
        "BAL_10X": (0.10, 1.00, 24, 3, 8 / 3),
        "BAL_4X": (0.25, 1.00, 24, 3, 8 / 3),
        "BAL_2X": (0.50, 1.00, 24, 3, 8 / 3),
        "BASE_DRAFT": (1.00, 1.00, 26, 1, 14 / 3),
        "PREF_2X": (1.00, 0.50, 27, 0, 20 / 3),
        "PREF_4X": (1.00, 0.25, 27, 0, 20 / 3),
        "PREF_10X": (1.00, 0.10, 27, 0, 20 / 3),
    }
    if len(summaries) != 7 or {row["scenario"] for row in summaries} != set(expected):
        errors.append("El resumen I00C no contiene exactamente los siete escenarios esperados")
        return
    json_results = json_payload.get("results", [])
    if (
        json_payload.get("instance_id") != "I00C_DRAFT_ILUSTRATIVO_27"
        or len(json_results) != 7
        or {row.get("scenario") for row in json_results} != set(expected)
    ):
        errors.append("El JSON I00C no coincide con la instancia y los siete escenarios")

    rows_by_scenario: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in assignments_rows:
        rows_by_scenario[row["scenario"]].append(row)

    for summary in summaries:
        scenario = summary["scenario"]
        lambda_0, lambda_1, satisfied, unsatisfied, expected_t = expected[scenario]
        if summary["status"].lower() != "optimal" or summary["optimal"].lower() != "true":
            errors.append(f"{scenario}: no está documentado como óptimo")
        if not math.isclose(float(summary["gap"]), 0.0, abs_tol=1e-12):
            errors.append(f"{scenario}: la brecha documentada no es cero")
        if not (
            math.isclose(float(summary["lambda_0"]), lambda_0)
            and math.isclose(float(summary["lambda_1"]), lambda_1)
            and int(summary["satisfied"]) == satisfied
            and int(summary["unsatisfied"]) == unsatisfied
            and math.isclose(float(summary["T"]), expected_t, abs_tol=1e-9)
        ):
            errors.append(f"{scenario}: el resumen no reproduce los valores verificados")

        scenario_rows = rows_by_scenario.get(scenario, [])
        assignment = {
            row["student_id"]: row["reported_destination_course"]
            for row in scenario_rows
        }
        if len(scenario_rows) != 27 or len(assignment) != 27:
            errors.append(f"{scenario}: no contiene 27 asignaciones únicas")
            continue
        audit = validate_i00c_assignment(meta, students, separations, assignment)
        if audit["problems"]:
            errors.extend(f"{scenario}: {problem}" for problem in audit["problems"])
        objective = lambda_0 * audit["unsatisfied"] + lambda_1 * audit["T"]
        if not (
            audit["satisfied"] == satisfied
            and audit["unsatisfied"] == unsatisfied
            and math.isclose(audit["T"], expected_t, abs_tol=1e-9)
            and math.isclose(audit["F"]["academic"], float(summary["F_academic"]), abs_tol=1e-9)
            and math.isclose(
                audit["F"]["socioemotional"],
                float(summary["F_socioemotional"]),
                abs_tol=1e-9,
            )
            and math.isclose(
                audit["F"]["convivencia"],
                float(summary["F_convivencia"]),
                abs_tol=1e-9,
            )
            and math.isclose(objective, float(summary["objective"]), abs_tol=1e-9)
            and audit["flows"]["8A"] == summary["flow_8A"]
            and audit["flows"]["8B"] == summary["flow_8B"]
            and audit["flows"]["8C"] == summary["flow_8C"]
        ):
            errors.append(f"{scenario}: asignaciones y resumen no son consistentes")
        for row in scenario_rows:
            documented = row["preference_satisfied"].strip().lower() == "true"
            if documented != audit["satisfied_by_student"][row["student_id"]]:
                errors.append(f"{scenario}: indicador de preferencia inconsistente")
                break

        json_row = next(
            (row for row in json_results if row.get("scenario") == scenario), None
        )
        if json_row is None or not (
            int(json_row["satisfied"]) == satisfied
            and int(json_row["unsatisfied"]) == unsatisfied
            and math.isclose(float(json_row["T"]), expected_t, abs_tol=1e-9)
            and math.isclose(float(json_row["objective"]), objective, abs_tol=1e-9)
        ):
            errors.append(f"{scenario}: JSON y CSV no son consistentes")

    pdf = (I00C_DIR / "figuras" / "fig_i00c_flujos_origen_destino.pdf").read_bytes()
    png = (I00C_DIR / "figuras" / "fig_i00c_flujos_origen_destino.png").read_bytes()
    if not pdf.startswith(b"%PDF") or not png.startswith(b"\x89PNG\r\n\x1a\n"):
        errors.append("La figura I00C no tiene un formato PDF/PNG válido")

    table_text = (
        I00C_DIR / "latex" / "tabla_sensibilidad_lambda_i00c.tex"
    ).read_text(encoding="utf-8")
    if table_text.count(" \\\\") != 8 or any(
        label not in table_text
        for label in (
            "Balance 10:1",
            "Balance 4:1",
            "Balance 2:1",
            "Base del draft",
            "Preferencias 2:1",
            "Preferencias 4:1",
            "Preferencias 10:1",
        )
    ):
        errors.append("La tabla LaTeX no contiene las siete filas esperadas")


def main() -> int:
    errors: list[str] = []
    validate_grid(errors)
    validate_i00c(errors)

    if errors:
        print(f"VALIDACIÓN FALLIDA: {len(errors)} inconsistencia(s)")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("OK: 480 instancias únicas y 480 testigos factibles")
    print("OK: 120 instancias para cada C en {4,5,6,7}")
    print("OK: I00C contiene 27 estudiantes y 7 escenarios consistentes")
    print("OK: la validación no ejecutó SCIP ni resolvió el benchmark")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
