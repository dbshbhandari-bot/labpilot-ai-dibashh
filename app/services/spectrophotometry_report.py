
import math
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether
)


# ============================================================
# 1. CALIBRATION CURVE GRAPH
# ============================================================

def create_calibration_graph(experiment, standards):

    points = [
        (
            float(standard["concentration"]),
            float(standard["absorbance"])
        )
        for standard in standards
    ]

    if len(points) < 2:
        raise ValueError(
            "At least two calibration standards are required."
        )

    slope = float(experiment["slope"])
    intercept = float(experiment["intercept"])

    values = [
        value
        for point in points
        for value in point
    ]

    if not all(math.isfinite(value) for value in values):
        raise ValueError("Calibration data must be finite.")

    if not all(
        math.isfinite(value)
        for value in (slope, intercept)
    ):
        raise ValueError(
            "Regression coefficients must be finite."
        )

    x_values = [point[0] for point in points]
    x_min = min(x_values)
    x_max = max(x_values)

    if x_min == x_max:
        raise ValueError(
            "Calibration concentrations must not all be equal."
        )

    fitted_line = [
        (x_min, slope * x_min + intercept),
        (x_max, slope * x_max + intercept)
    ]

    all_y = [point[1] for point in points]
    all_y.extend(point[1] for point in fitted_line)

    y_min = min(all_y)
    y_max = max(all_y)

    x_padding = (x_max - x_min) * 0.08
    y_padding = (y_max - y_min) * 0.10 or 0.05

    drawing = Drawing(480, 285)

    chart = LinePlot()
    chart.x = 55
    chart.y = 45
    chart.width = 390
    chart.height = 190

    chart.data = [
        points,
        fitted_line
    ]

    chart.xValueAxis.valueMin = x_min - x_padding
    chart.xValueAxis.valueMax = x_max + x_padding
    chart.yValueAxis.valueMin = y_min - y_padding
    chart.yValueAxis.valueMax = y_max + y_padding

    chart.lines[0].strokeColor = colors.HexColor(
        "#2563EB"
    )
    chart.lines[0].strokeWidth = 0
    chart.lines[0].symbol = makeMarker("Circle")
    chart.lines[0].symbol.size = 6

    chart.lines[1].strokeColor = colors.HexColor(
        "#DC2626"
    )
    chart.lines[1].strokeWidth = 2

    drawing.add(chart)

    drawing.add(String(
        240,
        265,
        "Calibration Curve",
        textAnchor="middle",
        fontSize=13,
        fillColor=colors.HexColor("#17365D")
    ))

    unit = (
        experiment["concentration_unit"]
        or "unit not recorded"
    )

    drawing.add(String(
        240,
        12,
        f"Concentration ({unit})",
        textAnchor="middle",
        fontSize=10
    ))

    drawing.add(String(
        12,
        145,
        "Absorbance (AU)",
        fontSize=10,
        textAnchor="middle",
        angle=90
    ))

    return drawing


# ============================================================
# 2. SCIENTIFIC WARNINGS
# ============================================================

def validate_calibration_report(experiment, standards):

    warnings = []

    concentrations = [
        float(standard["concentration"])
        for standard in standards
    ]

    if not concentrations:
        return ["No calibration standards are available."]

    minimum = min(concentrations)
    maximum = max(concentrations)

    unknown = float(
        experiment["unknown_concentration"]
    )

    r_squared = float(
        experiment["r_squared"]
    )

    if not math.isfinite(unknown):
        warnings.append(
            "INVALID RESULT: Estimated unknown "
            "concentration is not finite."
        )

    elif unknown < minimum or unknown > maximum:
        warnings.append(
            "EXTRAPOLATION WARNING: The estimated unknown "
            "concentration falls outside the recorded "
            "calibration range. The estimate may be "
            "unreliable and requires further validation."
        )

    if not math.isfinite(r_squared):
        warnings.append(
            "INVALID FIT: R-squared is not finite."
        )

    elif r_squared < 0.95:
        warnings.append(
            "CALIBRATION FIT WARNING: The recorded standards "
            "have an R-squared value below the provisional "
            "review threshold of 0.95. Review the data "
            "and suitability of the regression model."
        )

    if len(concentrations) < 5:
        warnings.append(
            "LIMITED CALIBRATION DATA: Fewer than five "
            "calibration measurements were recorded. "
            "Review whether the available data supports "
            "the intended analysis."
        )

    return warnings


# ============================================================
# 3. PDF GENERATOR
# ============================================================

def generate_spectrophotometry_pdf(
    experiment,
    standards
):

    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm
    )

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="LabPilotSpectroTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=23,
        textColor=colors.HexColor("#17365D"),
        alignment=TA_CENTER,
        spaceAfter=12
    ))

    def safe(value):
        if value is None:
            return "Not recorded"
        return escape(str(value))

    story = []

    # --------------------------------------------------------
    # REPORT HEADING
    # --------------------------------------------------------

    story.append(Paragraph(
        "LABPILOT AI",
        styles["LabPilotSpectroTitle"]
    ))

    story.append(Paragraph(
        "Spectrophotometry - Calibration Analysis Report",
        styles["Heading2"]
    ))

    story.append(Spacer(1, 8 * mm))

    # --------------------------------------------------------
    # EXPERIMENT DETAILS
    # --------------------------------------------------------

    story.append(Paragraph(
        "Experiment Details",
        styles["Heading2"]
    ))

    details = [
        ("Experiment ID", experiment["id"]),
        ("Title", experiment["experiment_title"]),
        ("Sample", experiment["sample_name"]),
        ("Wavelength (nm)", experiment["wavelength"]),
        (
            "Concentration unit",
            experiment["concentration_unit"]
        ),
        ("Date recorded", experiment["created_at"])
    ]

    details_table = Table(
        [
            [
                Paragraph(safe(label), styles["BodyText"]),
                Paragraph(safe(value), styles["BodyText"])
            ]
            for label, value in details
        ],
        colWidths=[50 * mm, 120 * mm]
    )

    details_table.setStyle(TableStyle([
        (
            "BACKGROUND",
            (0, 0),
            (0, -1),
            colors.HexColor("#F1F5F9")
        ),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        (
            "LINEBELOW",
            (0, 0),
            (-1, -1),
            0.3,
            colors.lightgrey
        )
    ]))

    story.append(details_table)
    story.append(Spacer(1, 8 * mm))

    # --------------------------------------------------------
    # CALIBRATION STANDARDS
    # --------------------------------------------------------

    story.append(Paragraph(
        "Calibration Standards",
        styles["Heading2"]
    ))

    unit = (
        experiment["concentration_unit"]
        or "Unit not recorded"
    )

    standards_data = [[
        "Standard",
        f"Concentration ({unit})",
        "Absorbance (AU)"
    ]]

    for index, standard in enumerate(
        standards,
        start=1
    ):
        standards_data.append([
            str(index),
            str(standard["concentration"]),
            str(standard["absorbance"])
        ])

    standards_table = Table(
        standards_data,
        colWidths=[35 * mm, 75 * mm, 60 * mm],
        repeatRows=1
    )

    standards_table.setStyle(TableStyle([
        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            colors.HexColor("#17365D")
        ),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        (
            "ROWBACKGROUNDS",
            (0, 1),
            (-1, -1),
            [
                colors.white,
                colors.HexColor("#F8FAFC")
            ]
        ),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP")
    ]))

    story.append(standards_table)
    story.append(Spacer(1, 8 * mm))

    # --------------------------------------------------------
    # CALIBRATION ANALYSIS RESULTS
    # --------------------------------------------------------

    story.append(Paragraph(
        "Calibration Analysis Results",
        styles["Heading2"]
    ))

    results = [
        ("Slope", f'{experiment["slope"]:.6f}'),
        ("Intercept", f'{experiment["intercept"]:.6f}'),
        ("R-squared", f'{experiment["r_squared"]:.6f}'),
        (
            "Unknown absorbance (AU)",
            f'{experiment["unknown_absorbance"]:.4f}'
        ),
        (
            "Estimated unknown concentration",
            f'{experiment["unknown_concentration"]:.4f} {unit}'
        )
    ]

    for label, value in results:

        story.append(Paragraph(
            f"<b>{safe(label)}:</b> {safe(value)}",
            styles["BodyText"]
        ))

        story.append(Spacer(1, 2 * mm))

    # --------------------------------------------------------
    # CALIBRATION GRAPH
    # KEEP HEADING AND GRAPH ON THE SAME PAGE
    # --------------------------------------------------------

    story.append(Spacer(1, 8 * mm))

    calibration_graph = create_calibration_graph(
        experiment,
        standards
    )

    story.append(
        KeepTogether([
            Paragraph(
                "Calibration Curve",
                styles["Heading2"]
            ),
            Spacer(1, 4 * mm),
            calibration_graph
        ])
    )

    story.append(Spacer(1, 8 * mm))

    # --------------------------------------------------------
    # DATA QUALITY AND SCIENTIFIC WARNINGS
    # --------------------------------------------------------

    story.append(Paragraph(
        "Data Quality &amp; Scientific Warnings",
        styles["Heading2"]
    ))

    story.append(Spacer(1, 3 * mm))

    warnings = validate_calibration_report(
        experiment,
        standards
    )

    if warnings:

        for warning in warnings:

            story.append(Paragraph(
                safe(warning),
                styles["BodyText"]
            ))

            story.append(Spacer(1, 4 * mm))

    else:

        story.append(Paragraph(
            "No automated warning thresholds were "
            "triggered for this dataset. This does "
            "not establish analytical or clinical "
            "validation of the experiment.",
            styles["BodyText"]
        ))

    story.append(Spacer(1, 8 * mm))

    # --------------------------------------------------------
    # SCIENTIFIC LIMITATIONS
    # --------------------------------------------------------

    story.append(Paragraph(
        "Scientific Limitations",
        styles["Heading2"]
    ))

    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(
        "This report presents a concentration estimate "
        "calculated using linear regression of the "
        "recorded calibration standards. "
        "A high R-squared value indicates how closely "
        "the recorded points fit the regression line, "
        "but does not independently confirm measurement "
        "accuracy, precision, or method validity. "
        "Results outside the calibrated concentration "
        "range require particular caution. "
        "Instrument calibration, sample preparation, "
        "measurement conditions, and experimental "
        "procedures must be independently verified. "
        "The R-squared and measurement-count review "
        "thresholds are provisional software rules, "
        "not universal laboratory acceptance criteria. "
        "LabPilot AI is a research-support prototype "
        "and is not intended for clinical diagnosis "
        "or treatment decisions.",
        styles["BodyText"]
    ))

    # --------------------------------------------------------
    # BUILD AND RETURN PDF
    # --------------------------------------------------------

    document.build(story)

    output.seek(0)

    return output
