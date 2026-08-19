from flask import Blueprint, render_template, request,redirect
from app.database.db import get_connection
from app.services.serial_dilution import calculate_cfu

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

    return render_template(
        "experiment_workspace.html",
        area=area,
        experiment=experiment
    )
@experiment_planner_bp.route(
    "/experiment-planner/save",
    methods=["POST"]
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
@experiment_planner_bp.route("/experiments/<int:experiment_id>")
def view_experiment(experiment_id):

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
        WHERE experiment_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (experiment_id,)
    )

    result = cursor.fetchone()
    scientific_cfu = None

    if result:
        scientific_cfu = f"{result[5]:.2e}"

    connection.close()

    return render_template(
        "experiment_detail.html",
        experiment=experiment,
        result=result,
        scientific_cfu=scientific_cfu
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
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM experiments
        WHERE id = ?
        """,
        (experiment_id,)
    )

    connection.commit()
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

    area = request.form.get("area")
    experiment = request.form.get("experiment")

    experiment_title = request.form.get("experiment_title")
    research_question = request.form.get("research_question")
    sample_name = request.form.get("sample_name")
    notes = request.form.get("notes")

    colonies = float(request.form.get("colonies"))
    dilution = float(request.form.get("dilution"))
    volume_ml = float(request.form.get("volume_ml"))

    cfu_per_ml = calculate_cfu(
        colonies,
        dilution,
        volume_ml
    )

    connection = get_connection()
    cursor = connection.cursor()

    # Save the main experiment
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

    # Save the Serial Dilution-specific data
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

    connection.commit()
    connection.close()

    return redirect(
        f"/experiments/{experiment_id}"
    )
@experiment_planner_bp.route(
    "/serial-dilution-results/<int:result_id>/update",
    methods=["POST"]
)
def update_serial_dilution_result(result_id):

    colonies = float(request.form.get("colonies"))
    dilution = float(request.form.get("dilution"))
    volume_ml = float(request.form.get("volume_ml"))

    cfu_per_ml = calculate_cfu(
        colonies,
        dilution,
        volume_ml
    )

    connection = get_connection()
    cursor = connection.cursor()

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

    connection.commit()

    cursor.execute(
        """
        SELECT experiment_id
        FROM serial_dilution_results
        WHERE id = ?
        """,
        (result_id,)
    )

    row = cursor.fetchone()

    connection.close()

    experiment_id = row[0]

    return redirect(
        f"/experiments/{experiment_id}"
    )