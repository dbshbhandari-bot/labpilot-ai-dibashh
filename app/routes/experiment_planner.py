from flask import Blueprint, render_template, request,redirect
from app.database.db import get_connection
from app.services.ast_analysis import analyse_ast_replicates
from app.services.serial_dilution import calculate_cfu, analyse_cfu
from io import BytesIO
from flask import send_file
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from app.services.spectrophotometry import analyse_calibration
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from xml.sax.saxutils import escape
experiment_planner_bp = Blueprint(
    "experiment_planner",
    __name__
)


@experiment_planner_bp.route("/experiment-planner")
def experiment_planner():
    return render_template("experiment_planner.html")

@experiment_planner_bp.route("/experiment-planner/start")
def start_experiment():

    area = request.args.get("area")
    experiment = request.args.get("experiment")

    if experiment == "Serial Dilution & CFU Analysis":
        return render_template(
            "serial_dilution_workspace.html"
        )

    if experiment == "Antibiotic Susceptibility Testing":
        return render_template(
            "antibiotic_susceptibility_workspace.html"
        )

    if experiment == "Spectrophotometry / Beer-Lambert Analysis":
        return render_template(
            "spectrophotometry_workspace.html"
        )

    return render_template(
        "experiment_workspace.html",
        area=area,
        experiment=experiment
    )

def save_experiment():

    area = request.form.get("area")
    experiment = request.form.get("experiment")
    research_question = request.form.get("research_question")
    hypothesis = request.form.get("hypothesis")
    independent_variable = request.form.get("independent_variable")
    dependent_variable = request.form.get("dependent_variable")
    controls = request.form.get("controls")
    notes = request.form.get("notes")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO experiments (
            area,
            experiment,
            research_question,
            hypothesis,
            independent_variable,
            dependent_variable,
            controls,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            area,
            experiment,
            research_question,
            hypothesis,
            independent_variable,
            dependent_variable,
            controls,
            notes
        )
    )

    connection.commit()
    connection.close()

    return render_template(
        "experiment_saved.html",
        area=area,
        experiment=experiment,
        research_question=research_question,
        hypothesis=hypothesis,
        independent_variable=independent_variable,
        dependent_variable=dependent_variable,
        controls=controls,
        notes=notes
    )
@experiment_planner_bp.route("/my-experiments")
def my_experiments():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            area,
            experiment,
            research_question,
            created_at
        FROM experiments
        ORDER BY id DESC
    """)

    experiments = cursor.fetchall()

    connection.close()

    return render_template(
        "my_experiments.html",
        experiments=experiments
    )

@experiment_planner_bp.route(
    "/experiments/<int:experiment_id>",
    methods=["GET"]
)
def view_experiment(experiment_id):

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # 1. Retrieve the saved experiment.
        cursor.execute("""
            SELECT
                id,
                area,
                experiment,
                research_question,
                hypothesis,
                independent_variable,
                dependent_variable,
                controls,
                notes,
                created_at
            FROM experiments
            WHERE id = ?
        """, (experiment_id,))

        experiment = cursor.fetchone()

        if experiment is None:
            return "Experiment not found.", 404

        if experiment[2] != "Serial Dilution & CFU Analysis":
            return "This is not a Serial Dilution experiment.", 404

        # 2. Retrieve every saved plate.
        # Column order matches experiment_detail.html.
        cursor.execute("""
            SELECT
                id,
                experiment_id,
                colony_count,
                dilution,
                volume_ml,
                cfu_per_ml,
                created_at,
                experiment_title,
                sample_name,
                plate_label
            FROM serial_dilution_results
            WHERE experiment_id = ?
            ORDER BY id ASC
        """, (experiment_id,))

        all_plates = cursor.fetchall()

    finally:
        connection.close()

    # 3. Select the original plate.
    result = all_plates[0] if all_plates else None

    scientific_cfu = None
    analysis = []

    # 4. Prepare the calculation and analysis.
    if result is not None:

        scientific_cfu = f"{result[5]:.2e}"

        analysis = analyse_cfu(
            result[2],
            result[3],
            result[4],
            result[5]
        )

    # 5. Display the existing experiment template.
    return render_template(
        "experiment_detail.html",
        experiment=experiment,
        result=result,
        scientific_cfu=scientific_cfu,
        analysis=analysis,
        all_plates=all_plates
    )


@experiment_planner_bp.route(
    "/experiments/ast/<int:experiment_id>"
)
def view_ast_experiment(experiment_id):

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                id,
                experiment_title,
                organism,
                sample_name,
                antibiotic,
                zone_diameter,
                notes,
                created_at,
                replicate_number,
                testing_method,
                disk_strength,
                interpretation_standard
            FROM ast_results
            WHERE experiment_id = ?
            ORDER BY id ASC
        """, (experiment_id,))

        all_results = cursor.fetchall()

    finally:
        connection.close()

    if not all_results:
        return "AST experiment not found.", 404

    # Organize measurements by antibiotic.
    # These groups are candidates for analysis,
    # not automatically verified replicate sets.
    groups = {}

    for measurement in all_results:
        antibiotic = measurement[4].strip()
        zone_diameter = measurement[5]
        replicate_number = measurement[8]

        key = antibiotic.casefold()

        if key not in groups:
            groups[key] = {
                "antibiotic": antibiotic,
                "measurements": [],
                "replicate_numbers": []
            }

        groups[key]["measurements"].append(zone_diameter)
        groups[key]["replicate_numbers"].append(
            replicate_number
        )

    ast_statistics = []

    for group in groups.values():

        replicate_numbers = group["replicate_numbers"]

        # Duplicate replicate identifiers mean
        # we cannot confidently identify the set.
        unique_replicates = (
            len(replicate_numbers)
            == len(set(replicate_numbers))
        )

        if unique_replicates and len(replicate_numbers) >= 2:
            status = "Needs comparability review"
        else:
            status = "Insufficient or ambiguous replicates"

        ast_statistics.append({
            "antibiotic": group["antibiotic"],
            "count": len(group["measurements"]),
            "status": status,
            "statistics": None
        })

    return render_template(
        "ast_experiment_detail.html",
        experiment_id=experiment_id,
        result=all_results[0],
        all_results=all_results,
        ast_statistics=ast_statistics
    )

@experiment_planner_bp.route(
    "/experiments/<int:experiment_id>/update",
    methods=["POST"]
)
def update_experiment(experiment_id):

    research_question = request.form.get("research_question")
    hypothesis = request.form.get("hypothesis")
    independent_variable = request.form.get("independent_variable")
    dependent_variable = request.form.get("dependent_variable")
    controls = request.form.get("controls")
    notes = request.form.get("notes")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE experiments

        SET
            research_question = ?,
            hypothesis = ?,
            independent_variable = ?,
            dependent_variable = ?,
            controls = ?,
            notes = ?

        WHERE id = ?
        """,
        (
            research_question,
            hypothesis,
            independent_variable,
            dependent_variable,
            controls,
            notes,
            experiment_id
        )
    )

    connection.commit()
    connection.close()

    return redirect(
        f"/experiments/{experiment_id}"
    )
@experiment_planner_bp.route(
    "/experiments/<int:experiment_id>/delete",
    methods=["POST"]
)

def delete_experiment(experiment_id):

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Delete measurements belonging to this experiment
        cursor.execute(
            """
            DELETE FROM serial_dilution_results
            WHERE experiment_id = ?
            """,
            (experiment_id,)
        )

        # Delete the experiment itself
        cursor.execute(
            """
            DELETE FROM experiments
            WHERE id = ?
            """,
            (experiment_id,)
        )

        # Save both deletions together
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return redirect("/my-experiments")

@experiment_planner_bp.route(
    "/experiments/<int:experiment_id>/edit",
    methods=["GET"]
)

def edit_experiment(experiment_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            area,
            experiment,
            research_question,
            hypothesis,
            independent_variable,
            dependent_variable,
            controls,
            notes,
            created_at
        FROM experiments
        WHERE id = ?
        """,
        (experiment_id,)
    )

    experiment = cursor.fetchone()

    connection.close()

    return render_template(
        "edit_experiment.html",
        experiment=experiment
    )
@experiment_planner_bp.route(
    "/experiments/serial-dilution/calculate",
    methods=["GET", "POST"]
)
def serial_dilution_calculator():

    result = None
    error = None

    if request.method == "POST":

        colonies = request.form.get("colonies")
        dilution = request.form.get("dilution")
        volume_ml = request.form.get("volume_ml")

        try:
            colonies = float(colonies)
            dilution = float(dilution)
            volume_ml = float(volume_ml)

            result = calculate_cfu(
                colonies,
                dilution,
                volume_ml
            )

            if result is None:
                error = "Please enter valid positive values."

        except ValueError:
            error = "Please enter numbers only."

    return render_template(
        "serial_dilution_calculator.html",
        result=result,
        error=error
    )
@experiment_planner_bp.route(
    "/serial-dilution-results/<int:result_id>/edit",
    methods=["GET"]
)
def edit_serial_dilution_result(result_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            experiment_id,
            colony_count,
            dilution,
            volume_ml,
            cfu_per_ml,
            created_at
        FROM serial_dilution_results
        WHERE id = ?
        """,
        (result_id,)
    )

    result = cursor.fetchone()

    connection.close()

    return render_template(
        "edit_serial_dilution_result.html",
        result=result
    )
@experiment_planner_bp.route(
    "/experiments/serial-dilution/save",
    methods=["POST"]
)

def save_serial_dilution():

    # 1. Read experiment information from the form
    area = request.form.get("area")
    experiment = request.form.get("experiment")

    experiment_title = request.form.get("experiment_title")
    research_question = request.form.get("research_question")
    sample_name = request.form.get("sample_name")
    notes = request.form.get("notes")

    # 2. Convert measurement inputs into numbers
    try:
        colonies = float(request.form["colonies"])
        dilution = float(request.form["dilution"])
        volume_ml = float(request.form["volume_ml"])

    except (ValueError, KeyError, TypeError):
        return "Please enter valid numerical values.", 400

    # 3. Calculate CFU/mL
    cfu_per_ml = calculate_cfu(
        colonies,
        dilution,
        volume_ml
    )

    # 4. Stop if measurements are invalid
    if cfu_per_ml is None:
        return (
            "Invalid laboratory measurements. "
            "Colony count must be a non-negative whole number. "
            "Dilution must be greater than 0 and at most 1. "
            "Volume plated must be greater than 0.",
            400
        )

    # 5. Connect to the database only after validation
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # 6. Save the main experiment
        cursor.execute(
            """
            INSERT INTO experiments (
                area,
                experiment,
                research_question,
                hypothesis,
                independent_variable,
                dependent_variable,
                controls,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                area,
                experiment,
                research_question,
                "",
                "",
                "",
                "",
                notes
            )
        )

        experiment_id = cursor.lastrowid

        # 7. Save the Serial Dilution measurements
        cursor.execute(
            """
            INSERT INTO serial_dilution_results (
                experiment_id,
                experiment_title,
                sample_name,
                colony_count,
                dilution,
                volume_ml,
                cfu_per_ml
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                experiment_title,
                sample_name,
                colonies,
                dilution,
                volume_ml,
                cfu_per_ml
            )
        )

        # 8. Save both records together
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    # 9. Return to the saved experiment
    return redirect(
        f"/experiments/{experiment_id}"
    )

@experiment_planner_bp.route(
    "/serial-dilution-results/<int:result_id>/update",
    methods=["POST"]
)
def update_serial_dilution_result(result_id):

    # Step 1: Read the updated measurements
    try:
        colonies = float(request.form["colonies"])
        dilution = float(request.form["dilution"])
        volume_ml = float(request.form["volume_ml"])

    except (ValueError, KeyError, TypeError):
        return "Please enter valid numerical values.", 400

    # Step 2: Recalculate CFU/mL
    cfu_per_ml = calculate_cfu(
        colonies,
        dilution,
        volume_ml
    )

    # Step 3: Reject invalid measurements
    if cfu_per_ml is None:
        return (
            "Invalid laboratory measurements. "
            "Colony count must be a non-negative whole number. "
            "Dilution must be greater than 0 and at most 1. "
            "Volume plated must be positive.",
            400
        )

    # Step 4: Connect to SQLite
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Step 5: Find the experiment linked to this result
        cursor.execute(
            """
            SELECT experiment_id
            FROM serial_dilution_results
            WHERE id = ?
            """,
            (result_id,)
        )

        row = cursor.fetchone()

        if row is None:
            return "Plate result not found.", 404

        experiment_id = row[0]

        # Step 6: Update the saved measurements
        cursor.execute(
            """
            UPDATE serial_dilution_results
            SET
                colony_count = ?,
                dilution = ?,
                volume_ml = ?,
                cfu_per_ml = ?
            WHERE id = ?
            """,
            (
                colonies,
                dilution,
                volume_ml,
                cfu_per_ml,
                result_id
            )
        )

        # Step 7: Save the changes
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    # Step 8: Return to the experiment
    return redirect(
        f"/experiments/{experiment_id}"
    )
@experiment_planner_bp.route(
    "/experiments/<int:experiment_id>/plates/add",
    methods=["POST"]
)

def add_serial_dilution_plate(experiment_id):

    plate_label = request.form.get("plate_label", "").strip()
    sample_name = request.form.get("sample_name", "").strip()

    try:
        colonies = float(request.form["colonies"])
        dilution = float(request.form["dilution"])
        volume_ml = float(request.form["volume_ml"])

    except (ValueError, KeyError, TypeError):
        return "Please enter valid numerical values.", 400

    cfu_per_ml = calculate_cfu(
        colonies,
        dilution,
        volume_ml
    )

    if cfu_per_ml is None:
        return (
            "Invalid laboratory measurements. "
            "Colonies must be a non-negative whole number, "
            "dilution must be greater than 0 and at most 1, "
            "and plated volume must be positive.",
            400
        )


    cfu_per_ml = calculate_cfu(colonies, dilution, volume_ml)

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id FROM experiments WHERE id = ?",
        (experiment_id,)
    )

    if cursor.fetchone() is None:
        connection.close()
        return "Experiment not found.", 404

    cursor.execute("""
        INSERT INTO serial_dilution_results (
            experiment_id,
            plate_label,
            sample_name,
            colony_count,
            dilution,
            volume_ml,
            cfu_per_ml
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        experiment_id,
        plate_label or "Additional Plate",
        sample_name,
        colonies,
        dilution,
        volume_ml,
        cfu_per_ml
    ))

    connection.commit()
    connection.close()

    return redirect(f"/experiments/{experiment_id}")

@experiment_planner_bp.route(
    "/experiments/<int:experiment_id>/report/pdf"
)
def download_serial_dilution_pdf(experiment_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, area, experiment, research_question,
               hypothesis, independent_variable,
               dependent_variable, controls, notes, created_at
        FROM experiments
        WHERE id = ?
    """, (experiment_id,))

    experiment = cursor.fetchone()

    if experiment is None:
        connection.close()
        return "Experiment not found.", 404

    if experiment[2] != "Serial Dilution & CFU Analysis":
        connection.close()
        return "PDF report is not available for this experiment.", 400

    cursor.execute("""
        SELECT plate_label, sample_name, colony_count,
               dilution, volume_ml, cfu_per_ml
        FROM serial_dilution_results
        WHERE experiment_id = ?
        ORDER BY id ASC
    """, (experiment_id,))

    plates = cursor.fetchall()
    connection.close()

    # Create the PDF in memory
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=(595.28, 841.89),
        rightMargin=35,
        leftMargin=35,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    story = []

    def add_text(label, value):
        safe_value = escape(str(value if value is not None else ""))
        story.append(
            Paragraph(
                f"<b>{escape(label)}:</b> {safe_value}",
                styles["Normal"]
            )
        )
        story.append(Spacer(1, 8))

    story.append(
        Paragraph("LabPilot AI", styles["Title"])
    )
    story.append(
        Paragraph(
            "Serial Dilution &amp; CFU Analysis Report",
            styles["Heading2"]
        )
    )
    story.append(Spacer(1, 15))

    add_text("Experiment ID", experiment[0])
    add_text("Experiment", experiment[2])
    add_text("Research Question", experiment[3])
    add_text("Created", experiment[9])
    add_text("Notes", experiment[8])

    story.append(Spacer(1, 15))
    story.append(
        Paragraph("Plate Measurements", styles["Heading2"])
    )

    table_data = [[
        "Plate", "Sample", "Colonies",
        "Dilution", "Volume", "CFU/mL"
    ]]

    for index, plate in enumerate(plates, start=1):
        table_data.append([
            Paragraph(
                escape(str(plate[0] or f"Plate {index}")),
                styles["Normal"]
            ),
            Paragraph(
                escape(str(plate[1] or "Not recorded")),
                styles["Normal"]
            ),
            str(plate[2]),
            f"{plate[3]:g}",
            f"{plate[4]:g}",
            f"{plate[5]:.2e}"
        ])

    if plates:
        table = Table(
            table_data,
            colWidths=[85, 90, 65, 65, 65, 100],
            repeatRows=1
        )

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF8")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
        ]))

        story.append(table)
    else:
        story.append(
            Paragraph("No plate measurements found.", styles["Normal"])
        )

    story.append(Spacer(1, 20))
    story.append(
        Paragraph("Calculation Method", styles["Heading2"])
    )
    story.append(
        Paragraph(
            "CFU/mL = Colony Count / (Dilution Factor x Volume Plated in mL)",
            styles["Normal"]
        )
    )

    story.append(Spacer(1, 15))
    story.append(
        Paragraph("Scientific Limitations", styles["Heading2"])
    )
    story.append(
        Paragraph(
            "Results are calculated from user-entered measurements. "
            "Plate suitability, dilution accuracy, sample identity, "
            "replicate consistency and laboratory methodology have "
            "not been independently verified. This report is a "
            "research prototype output, not a validated clinical report.",
            styles["Normal"]
        )
    )

    document.build(story)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"labpilot_experiment_{experiment_id}.pdf"
    )

@experiment_planner_bp.route(
    "/experiments/ast/<int:experiment_id>/methodology/save",
    methods=["POST"]
)

def save_ast_methodology(experiment_id):

    testing_method = request.form.get(
        "testing_method", ""
    ).strip()

    interpretation_standard = request.form.get(
        "interpretation_standard", ""
    ).strip()

    if not testing_method:
        return "Testing method is required.", 400

    if not interpretation_standard:
        return "Interpretation standard is required.", 400

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT id
            FROM ast_results
            WHERE experiment_id = ?
            ORDER BY id ASC
            LIMIT 1
        """, (experiment_id,))

        result = cursor.fetchone()

        if result is None:
            return "AST experiment not found.", 404

        cursor.execute("""
            UPDATE ast_results
            SET testing_method = ?,
                interpretation_standard = ?
            WHERE id = ?
        """, (
            testing_method,
            interpretation_standard,
            result[0]
        ))

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return redirect(f"/experiments/ast/{experiment_id}")


@experiment_planner_bp.route(
    "/experiments/ast/<int:experiment_id>/add",
    methods=["POST"]
)
def add_ast_antibiotic(experiment_id):
    import math

    antibiotic = request.form.get("antibiotic", "").strip()

    disk_strength_input = request.form.get(
        "disk_strength", ""
    ).strip()

    try:
        disk_strength_value = float(disk_strength_input)
    except (ValueError, TypeError):
        return "Please enter a valid disk strength.", 400

    if not math.isfinite(disk_strength_value) or disk_strength_value <= 0:
        return "Disk strength must be greater than zero.", 400

    disk_strength = f"{disk_strength_value:g} µg"

    notes = request.form.get("notes", "").strip()

    # Validate antibiotic name
    if not antibiotic:
        return "Antibiotic name is required.", 400

    # Validate disk strength
    if not disk_strength:
        return "Antibiotic disk strength is required.", 400

    # Validate inhibition zone
    try:
        zone_diameter = float(request.form["zone_diameter"])
    except (ValueError, TypeError, KeyError):
        return "Please enter a valid zone diameter.", 400

    if not math.isfinite(zone_diameter) or zone_diameter < 0:
        return (
            "Zone diameter must be a finite, "
            "non-negative number.",
            400
        )

    # Validate replicate number
    try:
        replicate_number = int(request.form["replicate_number"])
    except (ValueError, TypeError, KeyError):
        return "Please enter a valid replicate number.", 400

    if replicate_number < 1:
        return "Replicate number must be at least 1.", 400

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Find the original experiment information
        cursor.execute("""
            SELECT
                experiment_title,
                organism,
                sample_name
            FROM ast_results
            WHERE experiment_id = ?
            ORDER BY id ASC
            LIMIT 1
        """, (experiment_id,))

        original = cursor.fetchone()

        if original is None:
            return "AST experiment not found.", 404

        experiment_title, organism, sample_name = original

        # Save the new measurement with disk strength
        cursor.execute("""
            INSERT INTO ast_results (
                experiment_id,
                experiment_title,
                organism,
                sample_name,
                antibiotic,
                zone_diameter,
                replicate_number,
                disk_strength,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            experiment_id,
            experiment_title,
            organism,
            sample_name,
            antibiotic,
            zone_diameter,
            replicate_number,
            disk_strength,
            notes
        ))

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return redirect(f"/experiments/ast/{experiment_id}")


@experiment_planner_bp.route(
    "/experiments/ast/measurements/<int:measurement_id>/edit"
)
def edit_ast_measurement(measurement_id):

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                id,
                experiment_id,
                antibiotic,
                zone_diameter,
                notes,
                disk_strength,
                replicate_number
            FROM ast_results
            WHERE id = ?
        """, (measurement_id,))

        measurement = cursor.fetchone()

    finally:
        connection.close()

    if measurement is None:
        return "AST measurement not found.", 404

    return render_template(
        "edit_ast_measurement.html",
        measurement=measurement
    )

@experiment_planner_bp.route(
    "/experiments/ast/measurements/<int:measurement_id>/update",
    methods=["POST"]
)
def update_ast_measurement(measurement_id):

    import math

    antibiotic = request.form.get(
        "antibiotic", ""
    ).strip()

    notes = request.form.get(
        "notes", ""
    ).strip()

    disk_strength_input = request.form.get(
        "disk_strength", ""
    ).strip()

    # Validate antibiotic name
    if not antibiotic:
        return "Antibiotic name is required.", 400

    # Validate disk strength
    try:
        disk_strength_value = float(disk_strength_input)
    except (ValueError, TypeError):
        return "Please enter a valid disk strength.", 400

    if (
        not math.isfinite(disk_strength_value)
        or disk_strength_value <= 0
    ):
        return "Disk strength must be greater than zero.", 400

    # Automatically add the microgram unit
    disk_strength = f"{disk_strength_value:g} µg"

    # Validate inhibition-zone diameter
    try:
        zone_diameter = float(
            request.form["zone_diameter"]
        )
    except (ValueError, TypeError, KeyError):
        return "Please enter a valid zone diameter.", 400

    if not math.isfinite(zone_diameter) or zone_diameter < 0:
        return (
            "Zone diameter must be a finite, "
            "non-negative number.",
            400
        )

    # Validate replicate number
    try:
        replicate_number = int(
            request.form["replicate_number"]
        )
    except (ValueError, TypeError, KeyError):
        return "Please enter a valid replicate number.", 400

    if replicate_number < 1:
        return "Replicate number must be at least 1.", 400

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # STEP 1: Find the existing measurement
        cursor.execute("""
            SELECT experiment_id
            FROM ast_results
            WHERE id = ?
        """, (measurement_id,))

        existing = cursor.fetchone()

        if existing is None:
            return "AST measurement not found.", 404

        experiment_id = existing[0]

        # STEP 2: Update the measurement once
        cursor.execute("""
            UPDATE ast_results
            SET antibiotic = ?,
                zone_diameter = ?,
                notes = ?,
                disk_strength = ?,
                replicate_number = ?
            WHERE id = ?
        """, (
            antibiotic,
            zone_diameter,
            notes,
            disk_strength,
            replicate_number,
            measurement_id
        ))

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    # STEP 3: Return to the experiment
    return redirect(
        f"/experiments/ast/{experiment_id}"
    )

@experiment_planner_bp.route(
    "/experiments/ast/<int:experiment_id>/analyse",
    methods=["POST"]
)
def analyse_ast_experiment(experiment_id):

    import math
    import re

    # Require researcher confirmation
    confirmation = request.form.get(
        "comparability_confirmed"
    )

    if confirmation != "yes":
        return (
            "Please confirm experimental comparability "
            "before statistical analysis.",
            400
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                antibiotic,
                zone_diameter,
                replicate_number,
                disk_strength
            FROM ast_results
            WHERE experiment_id = ?
            ORDER BY id ASC
        """, (experiment_id,))

        measurements = cursor.fetchall()


    finally:
        connection.close()

    if not measurements:
        return "AST experiment not found.", 404

    groups = {}

    # Group measurements by antibiotic
    for (
        antibiotic,
        zone_diameter,
        replicate_number,
        disk_strength
    ) in measurements:

        key = (antibiotic or "").strip().casefold()

        if key not in groups:
            groups[key] = {
                "antibiotic": (antibiotic or "").strip(),
                "zones": [],
                "replicates": [],
                "disk_strengths": []
            }

        groups[key]["zones"].append(zone_diameter)
        groups[key]["replicates"].append(replicate_number)

        # Convert stored values such as "5 µg"
        # into comparable numeric microgram values.
        strength_text = str(
            disk_strength or ""
        ).strip()

        match = re.fullmatch(
            r"(\d+(?:\.\d+)?)\s*µg",
            strength_text,
            flags=re.IGNORECASE
        )

        if match:
            strength_value = float(match.group(1))

            if (
                not math.isfinite(strength_value)
                or strength_value <= 0
            ):
                strength_value = None
        else:
            strength_value = None

        groups[key]["disk_strengths"].append(
            strength_value
        )

    results = []
    excluded_groups = []

    for group in groups.values():

        replicates = group["replicates"]
        strengths = group["disk_strengths"]

        # Require at least two measurements
        if len(replicates) < 2:
            excluded_groups.append({
                "antibiotic": group["antibiotic"],
                "reason": "At least two replicates are required."
            })
            continue

        # Reject missing or duplicate replicate IDs
        if (
            any(
                not isinstance(rep, int)
                or rep < 1
                for rep in replicates
            )
            or len(replicates) != len(set(replicates))
        ):
            excluded_groups.append({
                "antibiotic": group["antibiotic"],
                "reason": "Invalid or duplicate replicate numbers."
            })
            continue

        # Reject missing or invalid disk strengths
        if any(strength is None for strength in strengths):
            excluded_groups.append({
                "antibiotic": group["antibiotic"],
                "reason": "Missing or invalid disk strength."
            })
            continue

        # Reject different disk strengths
        if len(set(strengths)) != 1:
            excluded_groups.append({
                "antibiotic": group["antibiotic"],
                "reason": "Replicates have different disk strengths."
            })
            continue

        # Calculate statistics for eligible groups
        statistics_result = analyse_ast_replicates(
            group["zones"]
        )

        results.append({
            "antibiotic": group["antibiotic"],
            "statistics": statistics_result
        })

    return render_template(
        "ast_statistical_analysis.html",
        experiment_id=experiment_id,
        results=results,
        excluded_groups=excluded_groups
    )

@experiment_planner_bp.route(
    "/experiments/ast/<int:experiment_id>/report"
)
def download_ast_report(experiment_id):

    import math
    import re

    from io import BytesIO
    from flask import send_file
    from xml.sax.saxutils import escape

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
        TableStyle
    )

    # ----------------------------------------
    # 1. RETRIEVE SAVED AST MEASUREMENTS
    # ----------------------------------------

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                id,
                experiment_title,
                organism,
                sample_name,
                antibiotic,
                zone_diameter,
                notes,
                created_at,
                replicate_number,
                testing_method,
                disk_strength,
                interpretation_standard
            FROM ast_results
            WHERE experiment_id = ?
            ORDER BY id ASC
        """, (experiment_id,))

        measurements = cursor.fetchall()

    finally:
        connection.close()

    if not measurements:
        return "AST experiment not found.", 404

    first = measurements[0]

    # Escape researcher-entered text for ReportLab.
    def safe(value):
        if value is None:
            return "Not recorded"
        return escape(str(value))

    # ----------------------------------------
    # 2. PREPARE PDF DOCUMENT
    # ----------------------------------------

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
        name="LabPilotTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=23,
        textColor=colors.HexColor("#17365D"),
        alignment=TA_CENTER,
        spaceAfter=12
    ))

    styles.add(ParagraphStyle(
        name="LabPilotSmall",
        parent=styles["BodyText"],
        fontSize=8,
        leading=11
    ))

    story = []

    # ----------------------------------------
    # 3. REPORT HEADING
    # ----------------------------------------

    story.append(Paragraph(
        "LABPILOT AI",
        styles["LabPilotTitle"]
    ))

    story.append(Paragraph(
        "Antibiotic Susceptibility Testing - Research Report",
        styles["Heading2"]
    ))

    story.append(Spacer(1, 8 * mm))

    # ----------------------------------------
    # 4. EXPERIMENT DETAILS
    # ----------------------------------------

    story.append(Paragraph(
        "Experiment Details",
        styles["Heading2"]
    ))

    details = [
        ["Experiment ID", str(experiment_id)],
        ["Title", first[1]],
        ["Organism", first[2]],
        ["Sample", first[3]],
        ["Testing method", first[9]],
        ["Interpretation standard", first[11]]
    ]

    details_table = Table(
        [
            [
                Paragraph(safe(label), styles["LabPilotSmall"]),
                Paragraph(safe(value), styles["LabPilotSmall"])
            ]
            for label, value in details
        ],
        colWidths=[45 * mm, 125 * mm]
    )

    details_table.setStyle(TableStyle([
        (
            "BACKGROUND",
            (0, 0),
            (0, -1),
            colors.HexColor("#F1F5F9")
        ),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
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

    # ----------------------------------------
    # 5. INDIVIDUAL AST MEASUREMENTS
    # ----------------------------------------

    story.append(Paragraph(
        "Antibiotic Measurements",
        styles["Heading2"]
    ))

    table_data = [[
        "Antibiotic",
        "Rep.",
        "Zone (mm)",
        "Disk strength"
    ]]

    for measurement in measurements:
        table_data.append([
            Paragraph(
                safe(measurement[4]),
                styles["LabPilotSmall"]
            ),
            str(measurement[8]),
            str(measurement[5]),
            Paragraph(
                safe(measurement[10]),
                styles["LabPilotSmall"]
            )
        ])

    measurements_table = Table(
        table_data,
        colWidths=[
            70 * mm,
            20 * mm,
            35 * mm,
            45 * mm
        ],
        repeatRows=1,
        hAlign="LEFT"
    )

    measurements_table.setStyle(TableStyle([
        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            colors.HexColor("#17365D")
        ),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
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
        (
            "LINEBELOW",
            (0, 1),
            (-1, -1),
            0.3,
            colors.lightgrey
        )
    ]))

    story.append(measurements_table)
    story.append(Spacer(1, 8 * mm))

    # ----------------------------------------
    # 6. LABORATORY NOTES
    # ----------------------------------------

    story.append(Paragraph(
        "Laboratory Notes",
        styles["Heading2"]
    ))

    has_notes = False

    for measurement in measurements:

        note = measurement[6]

        if note:
            has_notes = True

            story.append(Paragraph(
                f"<b>Measurement #{measurement[0]} "
                f"({safe(measurement[4])}):</b> "
                f"{safe(note)}",
                styles["LabPilotSmall"]
            ))

            story.append(Spacer(1, 3 * mm))

    if not has_notes:
        story.append(Paragraph(
            "No laboratory notes recorded.",
            styles["LabPilotSmall"]
        ))

    story.append(Spacer(1, 8 * mm))

    # ----------------------------------------
    # 7. GROUP MEASUREMENTS FOR ANALYSIS
    # ----------------------------------------

    groups = {}

    for measurement in measurements:

        antibiotic = (
            measurement[4] or ""
        ).strip()

        zone = measurement[5]
        replicate = measurement[8]
        disk_strength = measurement[10]

        key = antibiotic.casefold()

        if key not in groups:
            groups[key] = {
                "antibiotic": antibiotic,
                "zones": [],
                "replicates": [],
                "strengths": []
            }

        groups[key]["zones"].append(zone)

        groups[key]["replicates"].append(
            replicate
        )

        # Stored disk strength example: "5 µg"
        strength_text = str(
            disk_strength or ""
        ).strip()

        match = re.fullmatch(
            r"(\d+(?:\.\d+)?)\s*µg",
            strength_text,
            flags=re.IGNORECASE
        )

        if match:

            strength_value = float(
                match.group(1)
            )

            if (
                not math.isfinite(strength_value)
                or strength_value <= 0
            ):
                strength_value = None

        else:
            strength_value = None

        groups[key]["strengths"].append(
            strength_value
        )

    # ----------------------------------------
    # 8. VALIDATE REPLICATE GROUPS
    # ----------------------------------------

    valid_results = []
    excluded_results = []

    for group in groups.values():

        replicates = group["replicates"]
        strengths = group["strengths"]

        reason = None

        if len(replicates) < 2:

            reason = (
                "At least two replicates are required."
            )

        elif (
            any(
                not isinstance(rep, int)
                or rep < 1
                for rep in replicates
            )
            or len(replicates) != len(set(replicates))
        ):

            reason = (
                "Invalid or duplicate replicate numbers."
            )

        elif any(
            strength is None
            for strength in strengths
        ):

            reason = (
                "Missing or invalid disk strength."
            )

        elif len(set(strengths)) != 1:

            reason = (
                "Replicates have different disk strengths."
            )

        else:
            try:
                statistics_result = analyse_ast_replicates(
                    group["zones"]
                )
            except (ValueError, TypeError, OverflowError):
                reason = (
                    "Missing or invalid inhibition-zone "
                    "measurements."
                )

        if reason:

            excluded_results.append({
                "antibiotic": group["antibiotic"],
                "reason": reason
            })

            continue

        valid_results.append({
            "antibiotic": group["antibiotic"],
            "statistics": statistics_result
        })

    # ----------------------------------------
    # 9. PDF STATISTICAL SUMMARY
    # ----------------------------------------

    story.append(Paragraph(
        "Replicate Statistical Analysis",
        styles["Heading2"]
    ))

    story.append(Paragraph(
        "The following groups passed automated "
        "data-quality checks. Full experimental "
        "comparability has not been independently verified.",
        styles["LabPilotSmall"]
    ))

    story.append(Spacer(1, 4 * mm))

    if valid_results:

        stats_data = [[
            "Antibiotic",
            "Replicates",
            "Mean (mm)",
            "Sample SD (mm)"
        ]]

        for item in valid_results:

            stats = item["statistics"]

            stats_data.append([
                Paragraph(
                    safe(item["antibiotic"]),
                    styles["LabPilotSmall"]
                ),
                str(stats["count"]),
                str(stats["mean"]),
                str(stats["standard_deviation"])
            ])

        stats_table = Table(
            stats_data,
            colWidths=[
                70 * mm,
                30 * mm,
                35 * mm,
                35 * mm
            ],
            repeatRows=1
        )

        stats_table.setStyle(TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#17365D")
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            (
                "LINEBELOW",
                (0, 1),
                (-1, -1),
                0.3,
                colors.lightgrey
            )
        ]))

        story.append(stats_table)

    else:

        story.append(Paragraph(
            "No replicate groups passed automated "
            "data-quality checks.",
            styles["LabPilotSmall"]
        ))

    # ----------------------------------------
    # 10. EXCLUDED GROUPS
    # ----------------------------------------

    if excluded_results:

        story.append(Spacer(1, 8 * mm))

        story.append(Paragraph(
            "Excluded Replicate Groups",
            styles["Heading2"]
        ))

        for item in excluded_results:

            story.append(Paragraph(
                f"<b>{safe(item['antibiotic'])}:</b> "
                f"{safe(item['reason'])}",
                styles["LabPilotSmall"]
            ))

            story.append(Spacer(1, 3 * mm))

    # ----------------------------------------
    # 11. SCIENTIFIC LIMITATIONS
    # ----------------------------------------

    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph(
        "Scientific Limitations",
        styles["Heading2"]
    ))

    story.append(Paragraph(
        "This report contains researcher-recorded "
        "laboratory measurements. Automated checks "
        "verify replicate numbering and recorded "
        "disk strengths but do not establish full "
        "experimental comparability or independence. "
        "Inhibition-zone diameters alone do not "
        "establish clinical susceptibility categories. "
        "Clinical interpretation requires appropriate "
        "organism identification, validated testing "
        "methods and versioned breakpoint standards. "
        "This prototype report is not intended for "
        "clinical treatment decisions.",
        styles["BodyText"]
    ))

    # ----------------------------------------
    # 12. BUILD AND DOWNLOAD PDF
    # ----------------------------------------

    document.build(story)

    output.seek(0)

    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=(
            f"LabPilot_AST_Experiment_{experiment_id}.pdf"
        )
    )

@experiment_planner_bp.route(
    "/experiments/spectrophotometry/analyse",
    methods=["POST"]
)
def analyse_spectrophotometry():

    try:
        concentrations = []
        absorbances = []

        for i in range(1, 6):
            concentrations.append(
                request.form[f"concentration_{i}"]
            )

            absorbances.append(
                request.form[f"absorbance_{i}"]
            )

        unknown_absorbance = request.form["unknown_absorbance"]

        result = analyse_calibration(
            concentrations,
            absorbances,
            unknown_absorbance
        )

        return render_template(
            "spectrophotometry_workspace.html",
            result=result,
            concentrations=concentrations,
            absorbances=absorbances,
            unknown_absorbance=unknown_absorbance,
            experiment_title=request.form.get("experiment_title", ""),
            sample_name=request.form.get("sample_name", ""),
            wavelength=request.form.get("wavelength", ""),
            concentration_unit=request.form.get("concentration_unit", "mg/mL")
        )

    except (ValueError, KeyError) as error:
        return render_template(
            "spectrophotometry_workspace.html",
            error=str(error),
            form_data=request.form
        ), 400


