# Utility Flow Direction Assignment

This script adds direction information to the attribute table of a line feature class - direction is determined using the starting and ending point. While this can be done for any line feature class, a model of utility networks brought about the need for it.

## Overview

The script **`get_flow_direction.py`** does the following:

1. creates a copy of the input feature class using the specified projected spatial reference
2. adds attribute table fields to hold the following for each line segment:
    - the id's of adjacent segments
    - the bearing of the line segment
    - a cardinal direction of the line segment - one of 'N', 'S', 'E', 'W', 'NW', 'NE', 'SW', 'SE'
3. populates the new fields

## Input Data

The script operates on geospatial data - a feature class of lines stored in an **ArcGIS geodatabase**. The direction of each line segment in the input feature class is represented by the starting point and ending point used to draw each segment.

## Dependencies

These scripts require:
- **ArcGIS Pro** with **arcpy**
- **Python 3.x** (as used in ArcGIS)
- **dotenv**

## Usage

1. Ensure all dependencies are installed and that ArcGIS Pro/ArcMap is available with necessary licenses.
2. Configure the .env file according to the file '.env.example' (.env will not be committed to version control)
3. In the run() function of get_flow_direction.py, modify the values assigned to the following variables: spatial_ref_wkid, geographic_transformation, from_adjacent_id, to_adjacent_id, direction_float, direction_text, id_field, and xy_tolerance - see the docstrings and comments for explanations of these
4. Run get_flow_direction.py

The script can be run as a standalone Python script from a terminal (`python path/to/script.py` or `propy path/to/script.py` if using the 'propy' environment provided with ArcGIS Pro).

## Output

After the script is run, the output feature class can be found in the same geodatabase as the input feature class but will have the wkid appended to it e.g. 'input_feature_class_2277'

