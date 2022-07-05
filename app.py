from crypt import methods
import os
from fastapi import FastAPI, templating
#from flask import Flask, render_template

import pulumi.automation as auto

app = FastAPI()


def ensure_plugins():
    ws = auto.LocalWorkspace()
    ws.install_plugin("aws", "v4.0.0")


def create_app():
    ensure_plugins()
    app = FastAPI(__name__, instance_relative_config=True)
    app.cofig.from_mapping(
        SECRET_KEY="secret",
        PROJECT_NAME="reroku",
        PULUMI_ORG=os.environ.get("PULUMI_ORG"),
    )

    @app.get("/")
    def index():
        return templating("index.html")

    import sites

    import virtual_machines

    return app
