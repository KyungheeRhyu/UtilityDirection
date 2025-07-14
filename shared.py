import os
from dotenv import load_dotenv
import pathlib
import arcpy


def set_environment():
    """
    Set the environment for the script by loading the .env file and defining arcpy env settings. Assumes the .env file is in the same directory as this script.
    """
    script_dir = pathlib.Path(__file__).parent.resolve()
    env_path = script_dir / '.env'
    load_dotenv(dotenv_path=env_path)
    arcpy.env.overwriteOutput = True
    arcpy.env.workspace = os.getenv('GDB')  # Set the workspace from the .env file