import json
from urllib import request
from fastapi import APIRouter, requests, templating
from flask import current_app, flash, redirect, url_for
import requests
#from flask import (current_app,    Blueprint,    request,    flash,    redirect,    url_for,    render_template,    )
import pulumi
from pulumi.automation import auto
from pulumi_aws import s3

router = APIRouter(
    prefix="/sites", tags=['sites'])


def create_pulumi_program(content: str):
    site_bucket = s3.bucket(
        "s3-website-bucket", website=s3.BucketWebsiteArgs(index_document="index.html")
    )
    index_content = content

    s3.BucketObject(
        "index",
        bucket=site_bucket.id,
        content=index_content,
        key="index.html",
        content_type="text/html; charset=utf-8"
    )

    s3.BucketPolicy("bucket-policy",
                    bucket=site_bucket.id,
                    policy=site_bucket.id.apply(
                        lambda id: json.dumps(
                            {
                                "Version": "2012-10-17",
                                "Statement": {
                                    "Effect": "Allow",
                                    "Principal": "*",
                                    "Action": ["s3.GetObject"],
                                    "Resource": [f"arn.aws:s3:::{id}/*"],
                                }

                            }
                        )
                    )

                    )

    pulumi.export("website_url", site_bucket.website_endpoint)
    pulumi.export("website_content", index_content)


@router.post("/new")
def create_site():
    """creates new site"""
    stack_name = request.form.get("site-id")
    file_url = request.form.get("file-url")
    if file_url:
        site_content = requests.get(file_url).text
    else:
        site_content = request.form.get("site-content")

    def pulumi_program():
        return create_pulumi_program(str(site_content))

    try:
        stack = auto.create_stack(
            stack_name=str(stack_name),
            project_name=current_app.config["PROJECT_NAME"],
        )
        stack.set_config("aws:region", auto.ConfigValue("us-east-1"))
        stack.up(on_output=print)
        flash(
            f"Successfully created site '{stack_name}'", category="success")
    except auto.StackAlreadyExistsError:
        flash(
            f"Error: Site wiht name '{stack_name}' already exists, pick a unique name",
            category="danger",
        )
    return redirect(url_for("sites.list_sites"))


@router.get("/")
def list_sites():
    """lists all sites"""
    sites = []
    org_name = current_app.config["PULUMI_ORG"]
    project_name = current_app.config["PROJECT_NAME"]
    try:
        ws = auto.LocalWorkspace(
            project_settings=auto.ProjectSettings(
                name=project_name, runtime="python")
        )
        all_stacks = ws.list_stacks()
        for stack in all_stacks:
            stack = auto.select_stack(
                stack_name=stack.name,
                project_name=project_name,
                # no-op program, just to get outputs
                program=lambda: None,
            )
            outs = stack.outputs()
            if 'website_url' in outs:
                sites.append(
                    {
                        "name": stack.name,
                        "url": f"http://{outs['website_url'].value}",
                        "console_url": f"https://app.pulumi.com/{org_name}/{project_name}/{stack.name}",
                    }
                )
    except Exception as exn:
        flash(str(exn), category="danger")

    return templating("sites/index.html", sites=sites)


@router.post("/<id>/update")
def update_site(id: str):
    stack_name = id

    file_url = request.form.get("file-url")
    if file_url:
        site_content = requests.get(file_url).text
    else:
        site_content = str(request.form.get("site-content"))

        try:

            def pulumi_program():
                create_pulumi_program(str(site_content))

            stack = auto.select_stack(
                stack_name=stack_name,
                project_name=current_app.config["PROJECT_NAME"],
                program=pulumi_program,
            )
            stack.set_config("aws:region", auto.ConfigValue("us-east-1"))
            # deploy the stack, tailing the logs to stdout
            stack.up(on_output=print)
            flash(f"Site '{stack_name}' successfully updated!",
                  category="success")
        except auto.ConcurrentUpdateError:
            flash(
                f"Error: site '{stack_name}' already has an update in progress",
                category="danger",
            )
        except Exception as exn:
            flash(str(exn), category="danger")
        return redirect(url_for("sites.list_sites"))

    stack = auto.select_stack(
        stack_name=stack_name,
        project_name=current_app.config["PROJECT_NAME"],
        # noop just to get the outputs
        program=lambda: None,
    )
    outs = stack.outputs()
    content_output = outs.get("website_content")
    content = content_output.value if content_output else None


@router.get("'/<id>/update")
def update_site_get(id: str):
    stack_name = id
    stack = auto.select_stack(
        stack_name=stack_name,
        project_name=current_app.config["PROJECT_NAME"],
        # noop just to get the outputs
        program=lambda: None,
    )
    outs = stack.outputs()
    content_output = outs.get("website_content")
    content = content_output.value if content_output else None
    return templating("sites/update.html", name=stack_name, content=content)


@router.post("/<id>/delete")
def delete_site(id: str):
    stack_name = id
    try:
        stack = auto.select_stack(
            stack_name=stack_name,
            project_name=current_app.config["PROJECT_NAME"],
            # noop program for destroy
            program=lambda: None,
        )
        stack.destroy(on_output=print)
        stack.workspace.remove_stack(stack_name)
        flash(f"Site '{stack_name}' successfully deleted!", category="success")
    except auto.ConcurrentUpdateError:
        flash(
            f"Error: Site '{stack_name}' already has update in progress",
            category="danger",
        )
    except Exception as exn:
        flash(str(exn), category="danger")

    return redirect(url_for("sites.list_sites"))
