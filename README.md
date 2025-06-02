# Utility Materials Assignment

This script adds adjacency and material information to the attribute table of a line feature class. Using each segment’s start and end points, it identifies the IDs of adjacent segments and determines the material type of those adjacent segments based on the `PIPE_TYPE` field. While this logic can be applied to any linear feature class, it was developed to support utility network modeling and downstream analysis.

## Overview

The script **`get_materials.py`** does the following:

1. **Projects** the input feature class (originally in WGS 1984) into a specified projected coordinate system.
2. **Adds** (if not already present) the following fields to the projected feature class:
   - `Material_Source` (TEXT)  
   - `From_Material` (TEXT)  
   - `To_Material` (TEXT)  
   > **Note:** The script assumes `from_adjacent_id` and `to_adjacent_id` already exist and does not create them.
3. **Reads** each line’s geometry and its `PIPE_TYPE` value.
4. **Builds** a list of all start and end points to find which segments connect at each endpoint (using a small XY tolerance).
5. **Maps** each adjacent segment’s `PIPE_TYPE` value to a human-readable material string (e.g., `PVC`, `Cast Iron`).
6. **Populates**:
   - `from_adjacent_id` (preexisting)  
   - `to_adjacent_id` (preexisting)  
   - `Material_Source` (sets to “Legacy” if `PIPE_TYPE` is nonzero/nonnull; otherwise blank)  
   - `From_Material` (material name of the adjacent segment at the start point)  
   - `To_Material` (material name of the adjacent segment at the end point)  

## Input Data

The script operates on geospatial data - a feature class of lines stored in an **ArcGIS geodatabase**. The direction of each line segment in the input feature class is represented by the starting point and ending point used to draw each segment.

## Dependencies

The script requires:
- **ArcGIS Pro** with **arcpy**
- **Python 3.x** (as used in ArcGIS)
- **dotenv**

## Usage

1. Ensure all dependencies are installed and that ArcGIS Pro/ArcMap is available with necessary licenses.
2. Configure the .env file according to the file '.env.example' (.env will not be committed to version control)
3. Inside `get_materials.py`, update the `PIPE_TYPE_TO_MATERIAL_MAP` dictionary to match your organization’s `PIPE_TYPE` codes and material names.
4. Run get_materials.py

The script can be run as a standalone Python script from a terminal (`python path/to/script.py` or `propy path/to/script.py` if using the 'propy' environment provided with ArcGIS Pro).

## Output

After the script is run, the output feature class can be found in the same geodatabase as the input feature class but will have the wkid appended to it e.g. 'input_feature_class_2277'

