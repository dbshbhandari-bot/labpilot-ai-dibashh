
import os

from flask import Flask, render_template


def create_public_app():
    """
    Public-facing LabPilot AI demonstration website.

    This app is separate from the private laboratory
    application and does not access its database.
    """

    app = Flask(__name__)
    print("FLASK APP FILE:", __file__)
    print("FLASK TEMPLATE FOLDER:", app.template_folder)
    print("FLASK ROOT PATH:", app.root_path)

    secret_key = os.environ.get("LABPILOT_PUBLIC_SECRET_KEY")

    if not secret_key:
        raise RuntimeError(
            "LABPILOT_PUBLIC_SECRET_KEY is not configured."
        )

    app.config["SECRET_KEY"] = secret_key

    @app.route("/")
    def home():
        return render_template("public_home.html")

    @app.route("/demo/serial-dilution")
    def serial_dilution_demo():
        return render_template(
            "public_demo.html",
            experiment="serial"
        )

    @app.route("/demo/ast")
    def ast_demo():
        return render_template(
            "public_demo.html",
            experiment="ast"
        )

    @app.route("/demo/spectrophotometry")
    def spectrophotometry_demo():
        return render_template(
            "public_demo.html",
            experiment="spectro"
        )

    return app


if __name__ == "__main__":
    application = create_public_app()

    application.run(
        host="127.0.0.1",
        port=5001,
        debug=False
    )
