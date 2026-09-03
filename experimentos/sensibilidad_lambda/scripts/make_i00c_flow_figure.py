from __future__ import annotations

import csv
import math
from collections import Counter
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas


SCRIPT = Path(__file__).resolve()
EXPERIMENT_DIR = SCRIPT.parents[1]
INSTANCE_DIR = (
    EXPERIMENT_DIR
    / "instancia"
    / "I00C_DRAFT_ILUSTRATIVO_27"
)
OUTPUT = EXPERIMENT_DIR / "figuras" / "fig_i00c_flujos_origen_destino.pdf"

ORIGINS = ["8A", "8B", "8C"]
DESTINATIONS = ["1M-A", "1M-B", "1M-C"]
INK = HexColor("#111111")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def load_flow_matrix() -> list[list[int]]:
    students = {
        row["student_id"]: row
        for row in read_csv(INSTANCE_DIR / "students.csv")
    }
    assignment = {
        row["student_id"]: row["destination_course"]
        for row in read_csv(INSTANCE_DIR / "reference_solution.csv")
    }
    if set(students) != set(assignment):
        raise ValueError("La solución de referencia no cubre los 27 estudiantes")

    matrix = []
    for origin in ORIGINS:
        row_counts = Counter(
            assignment[student_id]
            for student_id, row in students.items()
            if row["origin_course"] == origin
        )
        matrix.append([row_counts[destination] for destination in DESTINATIONS])
    if matrix != [[3, 3, 3], [4, 2, 3], [2, 4, 3]]:
        raise ValueError(f"Flujos inesperados: {matrix}")
    return matrix


def node_box(pdf, x, y, width, height, title, subtitle, rounded=False):
    pdf.setFillColor(white)
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(1.15)
    if rounded:
        pdf.roundRect(x, y - height / 2, width, height, 7, fill=1, stroke=1)
    else:
        pdf.rect(x, y - height / 2, width, height, fill=1, stroke=1)
    pdf.setFillColor(INK)
    pdf.setFont("Times-Bold", 12)
    pdf.drawCentredString(x + width / 2, y + 3.5, title)
    pdf.setFont("Times-Roman", 9.3)
    pdf.drawCentredString(x + width / 2, y - 10, subtitle)


def cubic_point(p0, p1, p2, p3, t):
    one_minus = 1.0 - t
    return (
        one_minus**3 * p0[0]
        + 3 * one_minus**2 * t * p1[0]
        + 3 * one_minus * t**2 * p2[0]
        + t**3 * p3[0],
        one_minus**3 * p0[1]
        + 3 * one_minus**2 * t * p1[1]
        + 3 * one_minus * t**2 * p2[1]
        + t**3 * p3[1],
    )


def draw_arrowhead(pdf, p2, p3, color):
    dx = p3[0] - p2[0]
    dy = p3[1] - p2[1]
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    tip = p3
    base_x = tip[0] - 8 * ux
    base_y = tip[1] - 8 * uy
    path = pdf.beginPath()
    path.moveTo(*tip)
    path.lineTo(base_x + 3.4 * nx, base_y + 3.4 * ny)
    path.lineTo(base_x - 3.4 * nx, base_y - 3.4 * ny)
    path.close()
    pdf.setFillColor(color)
    pdf.setStrokeColor(color)
    pdf.drawPath(path, fill=1, stroke=0)


def apply_line_style(pdf, origin_index):
    if origin_index == 0:
        pdf.setDash()
    elif origin_index == 1:
        pdf.setDash(7, 3.5)
    else:
        pdf.setDash(1.2, 3.0)


def draw_figure(matrix):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    width, height = 610, 270
    pdf = canvas.Canvas(str(OUTPUT), pagesize=(width, height), pageCompression=1)
    pdf.setTitle("Flujos origen-destino de I00C_DRAFT_ILUSTRATIVO_27")
    pdf.setAuthor("Proyecto de reasignación de estudiantes")

    source_x, destination_x = 20, 465
    source_width, destination_width, box_height = 112, 125, 42
    y_values = [215, 140, 65]
    destination_subtitles = [
        "9 estudiantes (4F/5M)",
        "9 estudiantes (5F/4M)",
        "9 estudiantes (5F/4M)",
    ]

    pdf.setFillColor(INK)
    pdf.setFont("Times-Bold", 9.5)
    pdf.drawCentredString(source_x + source_width / 2, 252, "Cursos de origen")
    pdf.drawCentredString(
        destination_x + destination_width / 2, 252, "Cursos de destino"
    )

    for origin, y in zip(ORIGINS, y_values):
        node_box(
            pdf,
            source_x,
            y,
            source_width,
            box_height,
            origin,
            "9 estudiantes",
            rounded=False,
        )
    for destination, subtitle, y in zip(
        DESTINATIONS, destination_subtitles, y_values
    ):
        node_box(
            pdf,
            destination_x,
            y,
            destination_width,
            box_height,
            destination,
            subtitle,
            rounded=True,
        )

    count_labels = []
    for i, source_y in enumerate(y_values):
        for j, destination_y in enumerate(y_values):
            count = matrix[i][j]
            p0 = (source_x + source_width, source_y)
            p1 = (p0[0] + 112, source_y)
            p3 = (destination_x, destination_y)
            p2 = (p3[0] - 112, destination_y)
            pdf.setStrokeColor(INK)
            pdf.setLineWidth(1.0 + 0.48 * (count - 2))
            pdf.setLineCap(1)
            apply_line_style(pdf, i)
            path = pdf.beginPath()
            path.moveTo(*p0)
            path.curveTo(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
            pdf.drawPath(path, fill=0, stroke=1)
            pdf.setDash()
            draw_arrowhead(pdf, p2, p3, INK)

            label_t = [0.29, 0.50, 0.71][i]
            label_x, label_y = cubic_point(p0, p1, p2, p3, label_t)
            count_labels.append((label_x, label_y, count))

    # Los números se dibujan sobre fondo blanco para que las intersecciones
    # entre arcos no dificulten su lectura en pantalla ni en impresión.
    for label_x, label_y, count in count_labels:
        pdf.setFillColor(white)
        pdf.roundRect(label_x - 8, label_y - 7, 16, 14, 2.5, fill=1, stroke=0)
        pdf.setFillColor(INK)
        pdf.setFont("Times-Bold", 10.5)
        pdf.drawCentredString(label_x, label_y - 3.4, str(count))

    legend_y = 15
    pdf.setFillColor(INK)
    pdf.setFont("Times-Roman", 9.5)
    pdf.drawString(155, legend_y - 3, "Curso de origen:")
    legend_items = [(0, "8A", 260), (1, "8B", 360), (2, "8C", 460)]
    for origin_index, label, x in legend_items:
        pdf.setStrokeColor(INK)
        pdf.setLineWidth(1.35)
        apply_line_style(pdf, origin_index)
        pdf.line(x, legend_y, x + 42, legend_y)
        pdf.setDash()
        pdf.setFillColor(INK)
        pdf.setFont("Times-Roman", 9.5)
        pdf.drawString(x + 49, legend_y - 3, label)

    pdf.save()


def main():
    matrix = load_flow_matrix()
    draw_figure(matrix)
    print(f"Figura generada: {OUTPUT}")


if __name__ == "__main__":
    main()
