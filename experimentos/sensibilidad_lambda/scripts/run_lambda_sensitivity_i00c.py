from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
from collections import Counter
from pathlib import Path

from pyscipopt import Model, quicksum


SCRIPT = Path(__file__).resolve()
EXPERIMENT_DIR = SCRIPT.parents[1]
INSTANCE_DIR = (
    EXPERIMENT_DIR
    / "instancia"
    / "I00C_DRAFT_ILUSTRATIVO_27"
)
RESULTS_DIR = EXPERIMENT_DIR / "resultados"
TABLES_DIR = EXPERIMENT_DIR / "latex"

WEIGHT_SCENARIOS = [
    ("BAL_10X", 0.10, 1.00),
    ("BAL_4X", 0.25, 1.00),
    ("BAL_2X", 0.50, 1.00),
    ("BASE_DRAFT", 1.00, 1.00),
    ("PREF_2X", 1.00, 0.50),
    ("PREF_4X", 1.00, 0.25),
    ("PREF_10X", 1.00, 0.10),
]
SCENARIO_LABELS = {
    "BAL_10X": "Balance 10:1",
    "BAL_4X": "Balance 4:1",
    "BAL_2X": "Balance 2:1",
    "BASE_DRAFT": "Base del draft",
    "PREF_2X": "Preferencias 2:1",
    "PREF_4X": "Preferencias 4:1",
    "PREF_10X": "Preferencias 10:1",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def load_instance():
    meta = json.loads((INSTANCE_DIR / "instance.json").read_text(encoding="utf-8"))
    students = read_csv(INSTANCE_DIR / "students.csv")
    separations = [
        (row["student_i"], row["student_j"])
        for row in read_csv(INSTANCE_DIR / "separations.csv")
    ]
    reference = {
        row["student_id"]: row["destination_course"]
        for row in read_csv(INSTANCE_DIR / "reference_solution.csv")
    }
    return meta, students, separations, reference


def academic_level(grade: str) -> int:
    value = float(grade)
    if value < 4.0:
        return 1
    if value < 5.5:
        return 2
    return 3


def prepare_data(meta, students):
    ids = [row["student_id"] for row in students]
    by_id = {row["student_id"]: row for row in students}
    if len(ids) != meta["n_students"] or len(ids) != len(set(ids)):
        raise ValueError("La cantidad o unicidad de estudiantes no coincide con instance.json")

    preferences = {}
    for student_id in ids:
        values = []
        for index in range(1, 6):
            value = by_id[student_id].get(f"pref_{index}", "").strip()
            if value:
                values.append(value)
        if len(values) != len(set(values)):
            raise ValueError(f"Preferencias duplicadas para {student_id}")
        if any(peer not in by_id or peer == student_id for peer in values):
            raise ValueError(f"Preferencia inválida para {student_id}")
        preferences[student_id] = values

    criteria = {
        "academic": {
            student_id: academic_level(by_id[student_id]["grade_average"])
            for student_id in ids
        },
        "socioemotional": {
            student_id: int(by_id[student_id]["socioemotional_level"])
            for student_id in ids
        },
        "convivencia": {
            student_id: int(by_id[student_id]["convivencia_level"])
            for student_id in ids
        },
    }
    return ids, by_id, preferences, criteria


def build_model(meta, students, separations, lambda_0, lambda_1, time_limit, threads):
    ids, by_id, preferences, criteria = prepare_data(meta, students)
    destinations = meta["destination_courses"]
    origins = meta["origin_courses"]
    capacity = int(meta["capacity"]["maximum"])
    delta = int(meta["gender_delta"])
    alpha = {key: int(value) for key, value in meta["origin_alpha"].items()}

    model = Model(f"I00C_lambda_{lambda_0:g}_{lambda_1:g}")
    model.hideOutput(True)
    model.setRealParam("limits/time", float(time_limit))
    model.setRealParam("limits/gap", 0.0)
    for name, value in (
        ("parallel/maxnthreads", int(threads)),
        ("lp/threads", 1),
        ("randomization/permutationseed", 0),
        ("randomization/randomseedshift", 0),
        ("randomization/lpseed", 0),
    ):
        try:
            model.setIntParam(name, value)
        except Exception:
            pass
    try:
        model.setBoolParam("randomization/permutevars", False)
    except Exception:
        pass

    x = {
        (student_id, course): model.addVar(vtype="B", name=f"x_{student_id}_{course}")
        for student_id in ids
        for course in destinations
    }

    for student_id in ids:
        model.addCons(quicksum(x[student_id, c] for c in destinations) == 1)
    for course in destinations:
        model.addCons(quicksum(x[i, course] for i in ids) <= capacity)
    for first, second in separations:
        for course in destinations:
            model.addCons(x[first, course] + x[second, course] <= 1)

    genders = sorted({by_id[i]["gender"] for i in ids})
    for gender in genders:
        members = [i for i in ids if by_id[i]["gender"] == gender]
        for first, second in itertools.combinations(destinations, 2):
            first_count = quicksum(x[i, first] for i in members)
            second_count = quicksum(x[i, second] for i in members)
            model.addCons(first_count - second_count <= delta)
            model.addCons(second_count - first_count <= delta)

    for origin in origins:
        members = [i for i in ids if by_id[i]["origin_course"] == origin]
        for course in destinations:
            model.addCons(quicksum(x[i, course] for i in members) >= alpha[origin])

    y = {}
    w = {}
    z = {i: model.addVar(vtype="B", name=f"z_{i}") for i in ids}
    for student_id in ids:
        for peer in preferences[student_id]:
            w[student_id, peer] = model.addVar(vtype="B", name=f"w_{student_id}_{peer}")
            for course in destinations:
                y[student_id, peer, course] = model.addVar(
                    vtype="B", name=f"y_{student_id}_{peer}_{course}"
                )
                model.addCons(y[student_id, peer, course] <= x[student_id, course])
                model.addCons(y[student_id, peer, course] <= x[peer, course])
                model.addCons(
                    y[student_id, peer, course]
                    >= x[student_id, course] + x[peer, course] - 1
                )
            model.addCons(
                w[student_id, peer]
                == quicksum(y[student_id, peer, c] for c in destinations)
            )

    for student_id in ids:
        if preferences[student_id]:
            model.addCons(
                z[student_id]
                <= quicksum(w[student_id, peer] for peer in preferences[student_id])
            )
            for peer in preferences[student_id]:
                model.addCons(z[student_id] >= w[student_id, peer])
        else:
            model.addCons(z[student_id] == 0)

    dplus = {}
    dminus = {}
    dispersion = {
        criterion: model.addVar(lb=0.0, vtype="C", name=f"F_{criterion}")
        for criterion in criteria
    }
    maximum_dispersion = model.addVar(lb=0.0, vtype="C", name="T")
    for course in destinations:
        for criterion in criteria:
            for level in (1, 2, 3):
                dplus[course, criterion, level] = model.addVar(
                    lb=0.0, vtype="C", name=f"dp_{course}_{criterion}_{level}"
                )
                dminus[course, criterion, level] = model.addVar(
                    lb=0.0, vtype="C", name=f"dm_{course}_{criterion}_{level}"
                )

    for criterion, values in criteria.items():
        for level in (1, 2, 3):
            members = [i for i in ids if values[i] == level]
            average = len(members) / len(destinations)
            for course in destinations:
                model.addCons(
                    quicksum(x[i, course] for i in members) - average
                    == dplus[course, criterion, level]
                    - dminus[course, criterion, level]
                )
        model.addCons(
            dispersion[criterion]
            == quicksum(
                dplus[course, criterion, level] + dminus[course, criterion, level]
                for course in destinations
                for level in (1, 2, 3)
            )
        )
        model.addCons(dispersion[criterion] <= maximum_dispersion)

    unsatisfied = len(ids) - quicksum(z[i] for i in ids)
    model.setObjective(lambda_0 * unsatisfied + lambda_1 * maximum_dispersion, "minimize")
    return model, x


def align_to_reference(assignment, reference, destinations):
    best = None
    for permutation in itertools.permutations(destinations):
        mapping = dict(zip(destinations, permutation))
        candidate = {student_id: mapping[course] for student_id, course in assignment.items()}
        signature = tuple(candidate[i] for i in sorted(candidate))
        distance = sum(candidate[i] != reference[i] for i in candidate)
        key = (distance, signature)
        if best is None or key < best[0]:
            best = (key, candidate, mapping)
    return best[1], best[2], best[0][0]


def audit_assignment(meta, students, separations, assignment, lambda_0, lambda_1):
    ids, by_id, preferences, criteria = prepare_data(meta, students)
    destinations = meta["destination_courses"]
    origins = meta["origin_courses"]
    problems = []

    if set(assignment) != set(ids):
        problems.append("La asignación no cubre exactamente a los estudiantes de la instancia")
    if any(course not in destinations for course in assignment.values()):
        problems.append("La asignación contiene un curso destino desconocido")

    capacity_counts = Counter(assignment.values())
    for course in destinations:
        if capacity_counts[course] > int(meta["capacity"]["maximum"]):
            problems.append(f"Capacidad excedida en {course}")

    for first, second in separations:
        if assignment[first] == assignment[second]:
            problems.append(f"Separación violada: {first}-{second}")

    for gender in sorted({by_id[i]["gender"] for i in ids}):
        counts = [
            sum(by_id[i]["gender"] == gender and assignment[i] == c for i in ids)
            for c in destinations
        ]
        if max(counts) - min(counts) > int(meta["gender_delta"]):
            problems.append(f"Balance de género violado para {gender}: {counts}")

    flows = {}
    for origin in origins:
        counts = []
        for course in destinations:
            value = sum(
                by_id[i]["origin_course"] == origin and assignment[i] == course
                for i in ids
            )
            counts.append(value)
            if value < int(meta["origin_alpha"][origin]):
                problems.append(f"Representación de origen violada: {origin}-{course}")
        flows[origin] = counts

    satisfied_by_student = {
        i: any(assignment[i] == assignment[peer] for peer in preferences[i])
        for i in ids
    }
    satisfied = sum(satisfied_by_student.values())
    unsatisfied = len(ids) - satisfied

    dispersions = {}
    profile_counts = {}
    for criterion, values in criteria.items():
        total = 0.0
        profile_counts[criterion] = {}
        for level in (1, 2, 3):
            members = [i for i in ids if values[i] == level]
            average = len(members) / len(destinations)
            counts = [sum(i in members and assignment[i] == c for i in ids) for c in destinations]
            profile_counts[criterion][str(level)] = counts
            total += sum(abs(value - average) for value in counts)
        dispersions[criterion] = total

    maximum_dispersion = max(dispersions.values())
    objective = lambda_0 * unsatisfied + lambda_1 * maximum_dispersion
    signature_text = "|".join(f"{i}:{assignment[i]}" for i in sorted(ids))
    solution_id = hashlib.sha256(signature_text.encode("utf-8")).hexdigest()[:10].upper()

    return {
        "valid": not problems,
        "problems": problems,
        "capacity_counts": dict(capacity_counts),
        "flows": flows,
        "satisfied": satisfied,
        "unsatisfied": unsatisfied,
        "satisfaction_percent": 100.0 * satisfied / len(ids),
        "satisfied_by_student": satisfied_by_student,
        "F": dispersions,
        "T": maximum_dispersion,
        "objective": objective,
        "profile_counts": profile_counts,
        "solution_id": solution_id,
    }


def solve_scenario(meta, students, separations, reference, scenario, lambda_0, lambda_1):
    model, x = build_model(
        meta,
        students,
        separations,
        lambda_0,
        lambda_1,
        time_limit=120.0,
        threads=1,
    )
    model.optimize()
    status = str(model.getStatus()).lower()
    if status != "optimal" or model.getNSols() < 1:
        raise RuntimeError(f"{scenario}: se exigía optimalidad y SCIP terminó con {status}")

    solution = model.getBestSol()
    raw_assignment = {}
    for student_id in [row["student_id"] for row in students]:
        selected = [
            course
            for course in meta["destination_courses"]
            if model.getSolVal(solution, x[student_id, course]) > 0.5
        ]
        if len(selected) != 1:
            raise RuntimeError(f"{scenario}: asignación no única para {student_id}")
        raw_assignment[student_id] = selected[0]

    solver_objective = float(model.getObjVal())
    solver_audit = audit_assignment(
        meta, students, separations, raw_assignment, lambda_0, lambda_1
    )
    if not solver_audit["valid"]:
        raise RuntimeError(
            f"{scenario}: la solución bruta de SCIP no es factible: "
            f"{solver_audit['problems']}"
        )

    if scenario == "BASE_DRAFT":
        reference_audit = audit_assignment(
            meta, students, separations, reference, lambda_0, lambda_1
        )
        if not reference_audit["valid"] or not math.isclose(
            solver_objective,
            reference_audit["objective"],
            rel_tol=1e-7,
            abs_tol=1e-7,
        ):
            raise RuntimeError(
                "La solución de referencia del draft no alcanza el óptimo certificado"
            )
        assignment = dict(reference)
        relabeling = None
        reference_distance = 0
        representative_policy = "draft_reference_verified_at_certified_optimum"
    else:
        assignment, relabeling, reference_distance = align_to_reference(
            raw_assignment, reference, meta["destination_courses"]
        )
        representative_policy = "solver_solution_with_destination_relabeling"

    audit = audit_assignment(
        meta, students, separations, assignment, lambda_0, lambda_1
    )
    if not audit["valid"]:
        raise RuntimeError(f"{scenario}: auditoría fallida: {audit['problems']}")
    if not math.isclose(solver_objective, audit["objective"], rel_tol=1e-7, abs_tol=1e-7):
        raise RuntimeError(
            f"{scenario}: objetivo SCIP={solver_objective} y reconstruido={audit['objective']}"
        )

    return {
        "scenario": scenario,
        "lambda_0": lambda_0,
        "lambda_1": lambda_1,
        "lambda_ratio": lambda_0 / lambda_1,
        "status": status,
        "optimal": True,
        "objective": audit["objective"],
        "satisfied": audit["satisfied"],
        "unsatisfied": audit["unsatisfied"],
        "satisfaction_percent": audit["satisfaction_percent"],
        "T": audit["T"],
        "F_academic": audit["F"]["academic"],
        "F_socioemotional": audit["F"]["socioemotional"],
        "F_convivencia": audit["F"]["convivencia"],
        "flow_8A": "/".join(map(str, audit["flows"]["8A"])),
        "flow_8B": "/".join(map(str, audit["flows"]["8B"])),
        "flow_8C": "/".join(map(str, audit["flows"]["8C"])),
        "solution_id": audit["solution_id"],
        "solve_time_s": float(model.getSolvingTime()),
        "nodes": int(model.getNTotalNodes()),
        "gap": float(model.getGap()),
        "dual_bound": float(model.getDualbound()),
        "reporting_relabeling": relabeling,
        "representative_policy": representative_policy,
        "solver_selected_components": {
            "satisfied": solver_audit["satisfied"],
            "unsatisfied": solver_audit["unsatisfied"],
            "T": solver_audit["T"],
            "F": solver_audit["F"],
            "objective": solver_audit["objective"],
        },
        "hamming_distance_to_reference": reference_distance,
        "raw_assignment": raw_assignment,
        "assignment": assignment,
        "satisfied_by_student": audit["satisfied_by_student"],
        "profile_counts": audit["profile_counts"],
    }


def write_outputs(meta, results, reference_audit):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    compact_fields = [
        "scenario",
        "lambda_0",
        "lambda_1",
        "lambda_ratio",
        "status",
        "optimal",
        "objective",
        "satisfied",
        "unsatisfied",
        "satisfaction_percent",
        "T",
        "F_academic",
        "F_socioemotional",
        "F_convivencia",
        "flow_8A",
        "flow_8B",
        "flow_8C",
        "solution_id",
        "solve_time_s",
        "nodes",
        "gap",
        "dual_bound",
        "hamming_distance_to_reference",
        "representative_policy",
    ]
    with (RESULTS_DIR / "sensibilidad_lambda_i00c.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=compact_fields)
        writer.writeheader()
        for result in results:
            writer.writerow({field: result[field] for field in compact_fields})

    with (RESULTS_DIR / "asignaciones_sensibilidad_i00c.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        fields = [
            "scenario",
            "lambda_0",
            "lambda_1",
            "student_id",
            "raw_destination_course",
            "reported_destination_course",
            "preference_satisfied",
            "representative_policy",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for result in results:
            for student_id in sorted(result["assignment"]):
                writer.writerow(
                    {
                        "scenario": result["scenario"],
                        "lambda_0": result["lambda_0"],
                        "lambda_1": result["lambda_1"],
                        "student_id": student_id,
                        "raw_destination_course": result["raw_assignment"][student_id],
                        "reported_destination_course": result["assignment"][student_id],
                        "preference_satisfied": result["satisfied_by_student"][student_id],
                        "representative_policy": result["representative_policy"],
                    }
                )

    payload = {
        "instance_id": meta["instance_id"],
        "formulation": "weighted_sum_equation_6",
        "objective": "lambda_0*(|S|-sum(z_i)) + lambda_1*T",
        "solver_requirement": "SCIP status optimal for every scenario",
        "representative_reporting": (
            "En escenarios no base, las etiquetas simétricas de cursos se permutan solo para "
            "facilitar la comparación. En BASE_DRAFT se reporta reference_solution.csv después "
            "de verificar que es factible y alcanza el mismo objetivo óptimo certificado; la "
            "solución bruta de SCIP permanece en raw_assignment."
        ),
        "reference_solution_audit": reference_audit,
        "results": results,
    }
    (RESULTS_DIR / "sensibilidad_lambda_i00c.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    def decimal_es(value, digits):
        return f"{value:.{digits}f}".replace(".", ",")

    table_lines = [
        r"\begingroup",
        r"\renewcommand{\tablename}{Tabla}",
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Sensibilidad del ejemplo ilustrativo respecto de los pesos de la función objetivo.}",
        r"\label{tab:i00c-sensibilidad-lambda}",
        r"\small",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{lrrrrrrrrl}",
        r"\toprule",
        r"Escenario & $\lambda_0$ & $\lambda_1$ & $\lambda_0/\lambda_1$ & Satisfechos & $U$ & $T$ & $(F_{ac},F_{se},F_{cv})$ & $Z$ & Flujos 8A; 8B; 8C \\",
        r"\midrule",
    ]
    for result in results:
        scenario_label = SCENARIO_LABELS[result["scenario"]]
        dispersions = "; ".join(
            decimal_es(value, 4)
            for value in (
                result["F_academic"],
                result["F_socioemotional"],
                result["F_convivencia"],
            )
        )
        dispersions = f"({dispersions})"
        flows = f"{result['flow_8A']}; {result['flow_8B']}; {result['flow_8C']}"
        table_lines.append(
            f"{scenario_label} & "
            f"{decimal_es(result['lambda_0'], 2)} & "
            f"{decimal_es(result['lambda_1'], 2)} & "
            f"{decimal_es(result['lambda_ratio'], 2)} & {result['satisfied']}/27 & "
            f"{result['unsatisfied']} & {decimal_es(result['T'], 4)} & "
            f"{dispersions} & {decimal_es(result['objective'], 4)} & {flows} \\\\"
        )
    table_lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}%",
            r"}",
            r"\vspace{2pt}",
            r"\begin{minipage}{\textwidth}",
            r"\footnotesize\textit{Nota:} $U=|S|-\sum_i z_i$ es el número de estudiantes sin una preferencia satisfecha. Las dispersiones se presentan como $(F_{ac};F_{se};F_{cv})$ y los flujos, en el orden 1M-A/1M-B/1M-C.",
            r"\end{minipage}",
            r"\end{table}",
            r"\endgroup",
            "",
        ]
    )
    (TABLES_DIR / "tabla_sensibilidad_lambda_i00c.tex").write_text(
        "\n".join(table_lines), encoding="utf-8"
    )


def main():
    meta, students, separations, reference = load_instance()
    reference_audit = audit_assignment(meta, students, separations, reference, 1.0, 1.0)
    if not reference_audit["valid"]:
        raise RuntimeError(f"La solución de referencia no es factible: {reference_audit['problems']}")
    if reference_audit["unsatisfied"] != 1 or not math.isclose(reference_audit["T"], 14 / 3):
        raise RuntimeError("La solución de referencia no reproduce U=1 y T=14/3 del draft")

    results = [
        solve_scenario(meta, students, separations, reference, *scenario)
        for scenario in WEIGHT_SCENARIOS
    ]
    baseline = next(result for result in results if result["scenario"] == "BASE_DRAFT")
    if not math.isclose(baseline["objective"], 17 / 3, rel_tol=1e-7, abs_tol=1e-7):
        raise RuntimeError("El caso base no reproduce Z=17/3 del draft")
    if baseline["unsatisfied"] != 1 or not math.isclose(baseline["T"], 14 / 3):
        raise RuntimeError("El representante base no reproduce U=1 y T=14/3 del draft")

    write_outputs(meta, results, reference_audit)

    scip_probe = Model()
    scip_version = f"{scip_probe.getMajorVersion()}.{scip_probe.getMinorVersion()}.{scip_probe.getTechVersion()}"
    print(f"SCIP {scip_version}: {len(results)} escenarios óptimos certificados")
    for result in results:
        print(
            f"{result['scenario']:>10}  lambda=({result['lambda_0']:.2f},"
            f"{result['lambda_1']:.2f})  sat={result['satisfied']}/27  "
            f"T={result['T']:.4f}  Z={result['objective']:.4f}  "
            f"sol={result['solution_id']}"
        )


if __name__ == "__main__":
    main()
