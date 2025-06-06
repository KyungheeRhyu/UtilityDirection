# Utility Flow Direction Assignment

TODO - add details on material (PIPE_TYPE) updates to this section, Overview, and Usage

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

The script requires:
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

## Post-Processing

After the script has been run, the following are recommended:

1. Spot-checks of the direction values - check a few locations to ensure that the correct bearing and text direction are found in the respective fields. This can be done using a version of the sanitary sewer lines data styled with direction arrows. Though manual intervention has not been needed for the direction values so far, some of the results should still be checked.
2. Population of the original material field ('PIPE_TYPE' field in the original run of the script) based on the values in the new fields - as of June 5, 2025, this is not done in the script though it may be incorporated later after manual population. In order to avoid issues with modifying an existing domain, it may be necessary to export the feature class produced by the script to a separate (new) geodatabase before attempting to edit the original material field. Note: all SQL statements below are to be used in the SQL option of 'Select by Attributes' in ArcGIS Pro

The steps below involve the material fields. 

For cases where the original material field (PIPE_TYPE) should be updated and the From_Material and To_Material values match:
1. `(PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND From_Material = To_Material` 
2. Using 'Calculate Field', set Material_Source equal to ‘Adjacency’ for the selected records
3. `(PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND (From_Material = To_Material) AND From_Material = 'Unknown'` 
- With Calculate Field, set PIPE_TYPE equal to 0
- (PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND (From_Material = To_Material) AND From_Material = 'Ductile Iron'
- With Calculate Field, set PIPE_TYPE equal to 4
- (PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND (From_Material = To_Material) AND From_Material = 'Cast Iron'
- With Calculate Field, set PIPE_TYPE equal to 3

TODO - finish editing/formatting section below
(PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND (From_Material = To_Material) AND From_Material = 'PVC' - selects 123 records - with Calculate Field, set PIPE_TYPE equal to 1
(PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND (From_Material = To_Material) AND From_Material = 'RCP' - selects 2 records - with Calculate Field, set PIPE_TYPE equal to 2
(PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND (From_Material = To_Material) AND From_Material = 'VCP' - selects 16 records - with Calculate Field, set PIPE_TYPE equal to 5
(PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND (From_Material = To_Material) AND From_Material = 'R.C.C.P' - selects 0 records - no action
Select those where PIPE_TYPE should be updated where either From_Material or To_Material is not null and the other (From_Material or To_Material) is null (similar to a dead-end situation but flow is away from a starting point) - finish this
Select records where segment with unknown material is adjacent only to a single segment with known material (similar to a dead-end situation but flow is away from a starting point) - select where:
(PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND ((From_Material IS NULL AND To_Material IS NOT null) OR (To_Material IS NULL AND From_Material IS NOT null)) AND (From_Material = 'R.C.C.P' OR To_Material = 'R.C.C.P') - selects 3 records -  with Calculate Field, set PIPE_TYPE equal to 6
(PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND ((From_Material IS NULL AND To_Material IS NOT null) OR (To_Material IS NULL AND From_Material IS NOT null)) AND (From_Material = 'VCP' OR To_Material = 'VCP') - selected 62 records - with Calculate Field, set PIPE_TYPE equal to 5
(PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND ((From_Material IS NULL AND To_Material IS NOT null) OR (To_Material IS NULL AND From_Material IS NOT null)) AND (From_Material = 'RCP' OR To_Material = 'RCP') - selected 15 records - with Calculate Field, set PIPE_TYPE equal to 2
(PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND ((From_Material IS NULL AND To_Material IS NOT null) OR (To_Material IS NULL AND From_Material IS NOT null)) AND (From_Material = 'PVC' OR To_Material = 'PVC') - selected 216 records - with Calculate Field, set PIPE_TYPE equal to 1
(PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND ((From_Material IS NULL AND To_Material IS NOT null) OR (To_Material IS NULL AND From_Material IS NOT null)) AND (From_Material = 'Cast Iron' OR To_Material = 'Cast Iron') - selected 2 records - with Calculate Field, set PIPE_TYPE equal to 3
(PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND ((From_Material IS NULL AND To_Material IS NOT null) OR (To_Material IS NULL AND From_Material IS NOT null)) AND (From_Material = 'Ductile Iron' OR To_Material = 'Ductile Iron') - selected 1 record - with Calculate Field, set PIPE_TYPE equal to 4
(PIPE_TYPE IS NULL Or PIPE_TYPE = 0) AND ((From_Material IS NULL AND To_Material IS NOT null) OR (To_Material IS NULL AND From_Material IS NOT null)) AND (From_Material = 'Unknown' OR To_Material = 'Unknown') - selected 595 records - with Calculate Field, set PIPE_TYPE equal to 0
Can then:
re-run PIPE_TYPE portion of script with input feature class being the modified feature class (the feature class after the steps above have been taken) 
Repeat the steps above on the output of the run of the script


