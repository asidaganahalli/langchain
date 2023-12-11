"""
Develop integration packages for LangChain.
"""

import re
import shutil
import subprocess
from pathlib import Path

import typer
from typing_extensions import Annotated

integration_cli = typer.Typer(no_args_is_help=True, add_completion=False)


@integration_cli.command()
def new(
    integration_name: Annotated[
        str,
        typer.Option(
            help="The name of the integration to create. "
            "Do not include `langchain-`.",
            prompt=True,
        ),
    ],
):
    """
    Creates a new integration package.

    Should be run from libs/partners
    """
    integration_name = integration_name.lower()

    if integration_name.startswith("langchain-"):
        typer.echo("Name should not start with `langchain-`.")
        raise typer.Exit(code=1)

    destination_dir = Path.cwd() / integration_name
    if destination_dir.exists():
        typer.echo(f"Folder {destination_dir} exists.")
        raise typer.Exit(code=1)

    # copy over template from ../integration_template
    project_template_dir = Path(__file__).parents[1] / "integration_template"
    shutil.copytree(project_template_dir, destination_dir, dirs_exist_ok=False)

    package_name = f"langchain-{integration_name}"
    module_name = re.sub(
        r"[^a-zA-Z0-9_]",
        "_",
        package_name,
    )

    # replace template strings
    pyproject = destination_dir / "pyproject.toml"
    pyproject_contents = pyproject.read_text()
    pyproject.write_text(
        pyproject_contents.replace("__package_name__", package_name).replace(
            "__module_name__", module_name
        )
    )

    # move module folder
    package_dir = destination_dir / module_name
    shutil.move(destination_dir / "integration_template", package_dir)

    # update init
    init = package_dir / "__init__.py"
    init_contents = init.read_text()
    init.write_text(init_contents.replace("__module_name__", module_name))

    # poetry install
    subprocess.run(["poetry", "install"], cwd=destination_dir)
