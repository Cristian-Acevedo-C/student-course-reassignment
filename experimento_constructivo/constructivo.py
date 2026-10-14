# -*- coding: utf-8 -*-
"""Heuristica constructiva de dominio para el SCRP.

Este modulo no usa SCIP ni los testigos. Construye una asignacion estudiante->curso
respetando las restricciones duras del modelo de referencia y usa preferencias y
balance de perfiles solamente para guiar/mejorar la solucion.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from itertools import combinations, product
import math
import random
import time
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple


Assignment = Dict[int, int]


@dataclass
class ConstructiveStats:
    seed: int
    attempts: int = 0
    search_nodes: int = 0
    backtracks: int = 0
    blocked_states: int = 0
    repair_restarts: int = 0
    repair_swaps: int = 0
    local_search_swaps: int = 0
    local_search_relocations: int = 0
    construction_seconds: float = 0.0
    improvement_seconds: float = 0.0
    first_feasible_seconds: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _inverse_preferences(inst: Mapping) -> Dict[int, List[int]]:
    inv = {i: [] for i in inst["estudiantes"]}
    for i, peers in inst["preferencias"].items():
        for j in peers:
            inv[j].append(i)
    return inv


def objective_components(inst: Mapping, assignment: Mapping[int, int],
                         lambda_0: float = 1.0, lambda_1: float = 1.0) -> dict:
    """Calcula exactamente los componentes de (6), (20)-(22) para una asignacion."""
    students = sorted(inst["estudiantes"])
    courses = list(inst["cursos"])
    est = inst["estudiantes"]

    preferred_same = {}
    z = {}
    for i in students:
        preferred_same[i] = sum(
            1 for j in inst["preferencias"].get(i, [])
            if assignment.get(j) == assignment.get(i)
        )
        z[i] = int(preferred_same[i] >= 1)
    sum_z = sum(z.values())

    F = {}
    detail = {}
    for criterion in inst["criterios"]:
        total_dispersion = 0.0
        detail[criterion] = {}
        for level in inst["niveles"]:
            members = [i for i in students if est[i][criterion] == level]
            average = len(members) / len(courses)
            counts = [sum(assignment.get(i) == c for i in members) for c in courses]
            deviations = [abs(value - average) for value in counts]
            total_dispersion += sum(deviations)
            detail[criterion][str(level)] = {
                "promedio": average,
                "cuentas": counts,
                "desv_abs": deviations,
            }
        F[criterion] = total_dispersion
    T = max(F.values()) if F else 0.0
    unsatisfied = len(students) - sum_z
    objective = lambda_0 * unsatisfied + lambda_1 * T
    return {
        "suma_z": sum_z,
        "no_satisfechos": unsatisfied,
        "T": T,
        "F": F,
        "objetivo": objective,
        "preferidos_mismo_curso": preferred_same,
        "detalle_balance": detail,
    }


def violations_by_constraint(inst: Mapping, assignment: Mapping[int, int]) -> dict:
    """Auditoria desagregada de todas las restricciones duras (7)-(12)."""
    students = set(inst["estudiantes"])
    courses = set(inst["cursos"])
    assigned = set(assignment)
    missing = sorted(students - assigned)
    extra = sorted(assigned - students)
    invalid_courses = sorted((i, c) for i, c in assignment.items() if c not in courses)

    capacity_details = []
    for c in inst["cursos"]:
        count = sum(assignment.get(i) == c for i in students)
        excess = max(0, count - inst["capacidad"][c])
        if excess:
            capacity_details.append({"curso": c, "cuenta": count,
                                     "capacidad": inst["capacidad"][c], "exceso": excess})

    separation_details = []
    for i, j in inst["separaciones"]:
        if i in assignment and j in assignment and assignment[i] == assignment[j]:
            separation_details.append({"i": i, "j": j, "curso": assignment[i]})

    est = inst["estudiantes"]
    gender_details = []
    for gender in inst["grupos_genero"]:
        counts = [
            sum(assignment.get(i) == c and est[i]["genero"] == gender for i in students)
            for c in inst["cursos"]
        ]
        excess = max(0, max(counts, default=0) - min(counts, default=0)
                     - inst["delta_genero"])
        if excess:
            gender_details.append({"genero": gender, "cuentas": counts,
                                   "delta": inst["delta_genero"], "exceso": excess})

    origin_details = []
    for origin in inst["cursos_origen"]:
        for c in inst["cursos"]:
            count = sum(
                assignment.get(i) == c and est[i]["origen"] == origin for i in students
            )
            deficit = max(0, inst["alpha"][origin] - count)
            if deficit:
                origin_details.append({"origen": origin, "curso": c, "cuenta": count,
                                       "minimo": inst["alpha"][origin], "deficit": deficit})

    result = {
        "asignacion_unica": {
            "violaciones": len(missing) + len(extra) + len(invalid_courses),
            "faltantes": missing,
            "extras": extra,
            "cursos_invalidos": invalid_courses,
        },
        "capacidad": {
            "violaciones": len(capacity_details),
            "magnitud": sum(x["exceso"] for x in capacity_details),
            "detalle": capacity_details,
        },
        "separaciones": {
            "violaciones": len(separation_details),
            "magnitud": len(separation_details),
            "detalle": separation_details,
        },
        "genero": {
            "violaciones": len(gender_details),
            "magnitud": sum(x["exceso"] for x in gender_details),
            "detalle": gender_details,
        },
        "origen": {
            "violaciones": len(origin_details),
            "magnitud": sum(x["deficit"] for x in origin_details),
            "detalle": origin_details,
        },
    }
    result["total_violaciones"] = sum(
        result[k]["violaciones"]
        for k in ("asignacion_unica", "capacidad", "separaciones", "genero", "origen")
    )
    result["factible"] = result["total_violaciones"] == 0
    return result


def _balanced_vectors(total: int, capacities: Sequence[int], delta: int) -> List[Tuple[int, ...]]:
    """Vectores enteros con suma total y diferencia maxima <= delta."""
    n_courses = len(capacities)
    if n_courses == 0:
        return []
    avg = total / n_courses
    lo = max(0, math.floor(avg) - delta)
    hi = min(max(capacities), math.ceil(avg) + delta)
    vectors: List[Tuple[int, ...]] = []

    def rec(pos: int, remaining: int, values: List[int]) -> None:
        if pos == n_courses:
            if remaining == 0 and (not values or max(values) - min(values) <= delta):
                vectors.append(tuple(values))
            return
        remaining_slots = n_courses - pos - 1
        lower = max(lo, remaining - sum(capacities[pos + 1:]))
        upper = min(hi, capacities[pos], remaining)
        for value in range(lower, upper + 1):
            new_values = values + [value]
            if max(new_values) - min(new_values) > delta:
                continue
            rem = remaining - value
            if rem < remaining_slots * lo or rem > sum(capacities[pos + 1:]):
                continue
            rec(pos + 1, rem, new_values)

    rec(0, total, [])
    return vectors


def _joint_gender_plans(inst: Mapping) -> List[Dict[str, Tuple[int, ...]]]:
    courses = list(inst["cursos"])
    capacities = [inst["capacidad"][c] for c in courses]
    groups = list(inst["grupos_genero"])
    est = inst["estudiantes"]
    per_group = {}
    for group in groups:
        total = sum(est[i]["genero"] == group for i in est)
        per_group[group] = _balanced_vectors(total, capacities, inst["delta_genero"])
        if not per_group[group]:
            return []

    plans = []

    def combine(pos: int, used: List[int], chosen: Dict[str, Tuple[int, ...]]) -> None:
        if pos == len(groups):
            plans.append(dict(chosen))
            return
        group = groups[pos]
        for vector in per_group[group]:
            new_used = [used[k] + vector[k] for k in range(len(courses))]
            if any(new_used[k] > capacities[k] for k in range(len(courses))):
                continue
            chosen[group] = vector
            combine(pos + 1, new_used, chosen)
        chosen.pop(group, None)

    combine(0, [0] * len(courses), {})
    return plans


class _GreedyBuilder:
    def __init__(self, inst: Mapping, seed: int, randomized: bool,
                 node_limit: int, stats: ConstructiveStats):
        self.inst = inst
        self.rng = random.Random(seed)
        self.randomized = randomized
        self.node_limit = node_limit
        self.stats = stats
        self.students = sorted(inst["estudiantes"])
        self.courses = list(inst["cursos"])
        self.course_index = {c: k for k, c in enumerate(self.courses)}
        self.est = inst["estudiantes"]
        self.inv_pref = _inverse_preferences(inst)
        self.sep = {i: set() for i in self.students}
        for i, j in inst["separaciones"]:
            self.sep[i].add(j)
            self.sep[j].add(i)
        self.gender_plans = _joint_gender_plans(inst)
        if not self.gender_plans:
            raise ValueError("No existe ningun patron de genero compatible con capacidades y delta")

        self.assignment: Assignment = {}
        self.members = {c: set() for c in self.courses}
        self.course_count = Counter()
        self.origin_count = Counter()
        self.gender_count = Counter()
        self.profile_count = Counter()
        self.unassigned = set(self.students)

        self.total_origin = Counter(self.est[i]["origen"] for i in self.students)
        self.total_profile = Counter(
            (criterion, level)
            for i in self.students
            for criterion in inst["criterios"]
            for level in [self.est[i][criterion]]
        )
        self.difficulty = {
            i: 3 * len(self.sep[i]) + 2 * len(self.inv_pref[i])
               + len(inst["preferencias"].get(i, []))
            for i in self.students
        }

    def _assign(self, i: int, c: int) -> None:
        self.assignment[i] = c
        self.unassigned.remove(i)
        self.members[c].add(i)
        self.course_count[c] += 1
        origin = self.est[i]["origen"]
        gender = self.est[i]["genero"]
        self.origin_count[origin, c] += 1
        self.gender_count[gender, c] += 1
        for criterion in self.inst["criterios"]:
            self.profile_count[criterion, self.est[i][criterion], c] += 1

    def _unassign(self, i: int, c: int) -> None:
        del self.assignment[i]
        self.unassigned.add(i)
        self.members[c].remove(i)
        self.course_count[c] -= 1
        origin = self.est[i]["origen"]
        gender = self.est[i]["genero"]
        self.origin_count[origin, c] -= 1
        self.gender_count[gender, c] -= 1
        for criterion in self.inst["criterios"]:
            self.profile_count[criterion, self.est[i][criterion], c] -= 1

    def _compatible_gender_plans(self, extra: Optional[Tuple[int, int]] = None) -> int:
        extra_i, extra_c = extra if extra is not None else (None, None)
        compatible = 0
        for plan in self.gender_plans:
            ok = True
            for group in self.inst["grupos_genero"]:
                for c in self.courses:
                    count = self.gender_count[group, c]
                    if extra_i is not None and self.est[extra_i]["genero"] == group and c == extra_c:
                        count += 1
                    if count > plan[group][self.course_index[c]]:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                compatible += 1
        return compatible

    def _origin_lookahead(self, i: int, c: int) -> bool:
        origin_i = self.est[i]["origen"]
        # Cada curso debe conservar espacio para todas sus cuotas de origen pendientes.
        for course in self.courses:
            used = self.course_count[course] + int(course == c)
            free = self.inst["capacidad"][course] - used
            deficits = 0
            for origin in self.inst["cursos_origen"]:
                count = self.origin_count[origin, course]
                if origin == origin_i and course == c:
                    count += 1
                deficits += max(0, self.inst["alpha"][origin] - count)
            if deficits > free:
                return False

        # Los estudiantes restantes de cada origen deben cubrir todos los deficit.
        for origin in self.inst["cursos_origen"]:
            assigned_origin = sum(self.origin_count[origin, course] for course in self.courses)
            if origin == origin_i:
                assigned_origin += 1
            remaining = self.total_origin[origin] - assigned_origin
            deficits = 0
            for course in self.courses:
                count = self.origin_count[origin, course]
                if origin == origin_i and course == c:
                    count += 1
                deficits += max(0, self.inst["alpha"][origin] - count)
            if deficits > remaining:
                return False
        return True

    def feasible_courses(self, i: int) -> List[int]:
        result = []
        for c in self.courses:
            if self.course_count[c] >= self.inst["capacidad"][c]:
                continue
            if any(j in self.members[c] for j in self.sep[i]):
                continue
            if not self._origin_lookahead(i, c):
                continue
            if self._compatible_gender_plans((i, c)) == 0:
                continue
            result.append(c)
        return result

    def _course_score(self, i: int, c: int) -> float:
        origin = self.est[i]["origen"]
        own_pref = sum(j in self.members[c] for j in self.inst["preferencias"].get(i, []))
        incoming_pref = sum(j in self.members[c] for j in self.inv_pref[i])
        origin_need = int(self.origin_count[origin, c] < self.inst["alpha"][origin])

        profile_delta = 0.0
        for criterion in self.inst["criterios"]:
            level = self.est[i][criterion]
            target = self.total_profile[criterion, level] / len(self.courses)
            before = abs(self.profile_count[criterion, level, c] - target)
            after = abs(self.profile_count[criterion, level, c] + 1 - target)
            profile_delta += after - before

        plan_flexibility = self._compatible_gender_plans((i, c))
        fill_ratio = (self.course_count[c] + 1) / self.inst["capacidad"][c]
        score = (
            2.0 * profile_delta
            - 20.0 * origin_need
            - 12.0 * int(own_pref > 0)
            - 10.0 * incoming_pref
            + 0.25 * fill_ratio
            - 0.01 * math.log1p(plan_flexibility)
        )
        if self.randomized:
            score += self.rng.uniform(-2.0, 2.0)
        return score

    def search(self) -> Optional[Assignment]:
        if not self.unassigned:
            return dict(self.assignment)
        if self.stats.search_nodes >= self.node_limit:
            return None
        self.stats.search_nodes += 1

        candidates_by_student = []
        for i in self.unassigned:
            courses = self.feasible_courses(i)
            if not courses:
                self.stats.blocked_states += 1
                return None
            tie_noise = self.rng.random() if self.randomized else 0.0
            candidates_by_student.append((len(courses), -self.difficulty[i], tie_noise, i, courses))

        _, _, _, student, courses = min(candidates_by_student)
        ordered = sorted(courses, key=lambda c: (self._course_score(student, c), c))
        for course in ordered:
            self._assign(student, course)
            solution = self.search()
            if solution is not None:
                return solution
            self._unassign(student, course)
            self.stats.backtracks += 1
            if self.stats.search_nodes >= self.node_limit:
                break
        return None


def _auxiliary_key(inst: Mapping, assignment: Mapping[int, int],
                   lambda_0: float, lambda_1: float) -> Tuple[float, int, float, float, int]:
    comp = objective_components(inst, assignment, lambda_0, lambda_1)
    total_f = sum(comp["F"].values())
    preferred_multiplicity = sum(comp["preferidos_mismo_curso"].values())
    return (round(comp["objetivo"], 9), comp["no_satisfechos"],
            round(comp["T"], 9), round(total_f, 9), -preferred_multiplicity)


def _local_improvement(inst: Mapping, assignment: Assignment, stats: ConstructiveStats,
                       lambda_0: float, lambda_1: float,
                       max_iterations: int = 60,
                       max_cycle_evaluations: int = 20000) -> Assignment:
    """Best-improvement con swaps/reubicaciones que preservan factibilidad dura."""
    if len(assignment) > 40:
        max_iterations = min(max_iterations, 30)
        max_cycle_evaluations = min(max_cycle_evaluations, 4000)
    current = dict(assignment)
    students = sorted(current)
    best_key = _auxiliary_key(inst, current, lambda_0, lambda_1)

    for _ in range(max_iterations):
        best_move = None
        best_candidate_key = best_key

        # Swaps: preservan capacidad; se auditan las otras restricciones duras.
        for pos, i in enumerate(students):
            for j in students[pos + 1:]:
                if current[i] == current[j]:
                    continue
                candidate = dict(current)
                candidate[i], candidate[j] = candidate[j], candidate[i]
                if not violations_by_constraint(inst, candidate)["factible"]:
                    continue
                key = _auxiliary_key(inst, candidate, lambda_0, lambda_1)
                if key < best_candidate_key:
                    best_candidate_key = key
                    best_move = ("swap", i, j, candidate)

        # Reubicaciones: relevantes cuando existe holgura de capacidad.
        counts = Counter(current.values())
        for i in students:
            for c in inst["cursos"]:
                if c == current[i] or counts[c] >= inst["capacidad"][c]:
                    continue
                candidate = dict(current)
                candidate[i] = c
                if not violations_by_constraint(inst, candidate)["factible"]:
                    continue
                key = _auxiliary_key(inst, candidate, lambda_0, lambda_1)
                if key < best_candidate_key:
                    best_candidate_key = key
                    best_move = ("relocate", i, c, candidate)

        # Si el swap se estanca, probar cadenas ciclicas de tres estudiantes.
        if best_move is None:
            evaluated = 0
            for i, j, k in combinations(students, 3):
                ci, cj, ck = current[i], current[j], current[k]
                if len({ci, cj, ck}) < 3:
                    continue
                for new_i, new_j, new_k in ((cj, ck, ci), (ck, ci, cj)):
                    candidate = dict(current)
                    candidate[i], candidate[j], candidate[k] = new_i, new_j, new_k
                    evaluated += 1
                    if not violations_by_constraint(inst, candidate)["factible"]:
                        if evaluated >= max_cycle_evaluations:
                            break
                        continue
                    key = _auxiliary_key(inst, candidate, lambda_0, lambda_1)
                    if key < best_candidate_key:
                        best_candidate_key = key
                        best_move = ("cycle3", i, j, candidate)
                    if evaluated >= max_cycle_evaluations:
                        break
                if evaluated >= max_cycle_evaluations:
                    break
        if best_move is None:
            break
        current = best_move[3]
        best_key = best_candidate_key
        if best_move[0] in ("swap", "cycle3"):
            stats.local_search_swaps += 1
        else:
            stats.local_search_relocations += 1
    return current


def _hard_penalty(inst: Mapping, assignment: Mapping[int, int]) -> Tuple[int, int, int, int, int]:
    audit = violations_by_constraint(inst, assignment)
    unique = audit["asignacion_unica"]["violaciones"]
    capacity = audit["capacidad"]["magnitud"]
    separation = audit["separaciones"]["magnitud"]
    gender = audit["genero"]["magnitud"]
    origin = audit["origen"]["magnitud"]
    weighted = 10000 * unique + 1000 * capacity + 100 * separation + 50 * gender + 50 * origin
    return weighted, unique + capacity, separation, gender, origin


def _repair_fallback(inst: Mapping, seed: int, stats: ConstructiveStats,
                     restarts: int = 30, max_steps: int = 300) -> Optional[Assignment]:
    """Reparacion min-conflicts por swaps; no consulta testigos ni SCIP."""
    rng = random.Random(seed)
    students = sorted(inst["estudiantes"])
    slots = [c for c in inst["cursos"] for _ in range(inst["capacidad"][c])]
    if len(slots) < len(students):
        return None
    slots = slots[:len(students)]

    best_global = None
    best_global_penalty = None
    for _ in range(restarts):
        stats.repair_restarts += 1
        rng.shuffle(slots)
        assignment = dict(zip(students, slots))
        penalty = _hard_penalty(inst, assignment)
        for _step in range(max_steps):
            if penalty[0] == 0:
                return assignment
            best = None
            best_penalty = penalty
            for p, i in enumerate(students):
                for j in students[p + 1:]:
                    if assignment[i] == assignment[j]:
                        continue
                    assignment[i], assignment[j] = assignment[j], assignment[i]
                    candidate_penalty = _hard_penalty(inst, assignment)
                    if candidate_penalty < best_penalty:
                        best_penalty = candidate_penalty
                        best = (i, j)
                    assignment[i], assignment[j] = assignment[j], assignment[i]
            if best is None:
                # Perturbacion conservando capacidades para escapar de minimos locales.
                i, j = rng.sample(students, 2)
                assignment[i], assignment[j] = assignment[j], assignment[i]
                penalty = _hard_penalty(inst, assignment)
                stats.repair_swaps += 1
                continue
            i, j = best
            assignment[i], assignment[j] = assignment[j], assignment[i]
            penalty = best_penalty
            stats.repair_swaps += 1
        if best_global_penalty is None or penalty < best_global_penalty:
            best_global = dict(assignment)
            best_global_penalty = penalty
    if best_global is not None and _hard_penalty(inst, best_global)[0] == 0:
        return best_global
    return None


def construct_solution(inst: Mapping, seed: int = 20261001, attempts: int = 20,
                       node_limit_per_attempt: int = 100_000,
                       lambda_0: float = 1.0, lambda_1: float = 1.0,
                       improve: bool = True) -> Tuple[Optional[Assignment], ConstructiveStats]:
    """Construye la mejor solucion factible encontrada en varios intentos reproducibles."""
    stats = ConstructiveStats(seed=seed)
    started = time.perf_counter()
    best = None
    best_key = None
    candidate_pool: Dict[Tuple[int, ...], Assignment] = {}

    for attempt in range(max(1, attempts)):
        stats.attempts += 1
        builder = _GreedyBuilder(
            inst=inst,
            seed=seed + 104729 * attempt,
            randomized=(attempt > 0),
            node_limit=node_limit_per_attempt,
            stats=stats,
        )
        candidate = builder.search()
        if candidate is None:
            continue
        if not violations_by_constraint(inst, candidate)["factible"]:
            continue
        if stats.first_feasible_seconds is None:
            stats.first_feasible_seconds = time.perf_counter() - started
        key = _auxiliary_key(inst, candidate, lambda_0, lambda_1)
        signature = tuple(candidate[i] for i in sorted(candidate))
        candidate_pool[signature] = candidate
        if best_key is None or key < best_key:
            best, best_key = candidate, key

    stats.construction_seconds = time.perf_counter() - started

    if best is None:
        best = _repair_fallback(inst, seed + 999983, stats)
        if best is not None and stats.first_feasible_seconds is None:
            stats.first_feasible_seconds = time.perf_counter() - started

    if best is not None and improve:
        improve_started = time.perf_counter()
        pool_size = 5 if len(best) <= 40 else 3
        ranked = sorted(
            candidate_pool.values(),
            key=lambda a: _auxiliary_key(inst, a, lambda_0, lambda_1),
        )[:pool_size]
        if not ranked:
            ranked = [best]
        for candidate in ranked:
            improved = _local_improvement(inst, candidate, stats, lambda_0, lambda_1)
            key = _auxiliary_key(inst, improved, lambda_0, lambda_1)
            if best_key is None or key < best_key:
                best, best_key = improved, key
        stats.improvement_seconds = time.perf_counter() - improve_started

    return best, stats
