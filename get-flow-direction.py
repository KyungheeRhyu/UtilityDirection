import os
import math
import dotenv
import arcpy


def get_projected_feature_class(in_fc, out_fc, out_coordinate_system, geographic_transformation):
    """
    Project a feature class using the geographic coordinate system WGS84 to a specified coordinate system using the given transformation.
    :param in_fc - string: Path to the input feature class.
    :param out_fc - string: Path to the output feature class.
    :param out_coordinate_system - string: The output coordinate system (e.g., WKID or path).
    :param geographic_transformation - string: The geographic transformation to use.
    return: output feature class path
    """
    try:
        arcpy.management.Project(
            in_dataset=in_fc,
            out_dataset=out_fc,
            out_coor_system=out_coordinate_system,
            transform_method=geographic_transformation,
            in_coor_system=arcpy.SpatialReference(4326)
        )
        print("Projection complete.")

    except Exception as e:
        print(f"Error during projection: {e}")
        exit() # Exit the script if projection fails


# Path to your ORIGINAL sewer line feature class in WGS 1984
original_feature_class_wgs84 = r"your_path\Sewer Line.gdb/SanitarySewerLines_ExportFeatures" # <--- !! Update this path !!

# Path and name for the NEW feature class that will be created in the projected coordinate system
# This should be in the same geodatabase or a different one
projected_feature_class_path = r"your_path\Sewer Line.gdb/SanitarySewerLines_Projected" # <--- !! Update this path and name !!

# The desired OUTPUT Projected Coordinate System (PCS)
# This MUST be a PCS with linear units (like Feet or Meters)
# You can find the spatial reference code (WKID) or path in ArcGIS Pro
# Example for Texas State Plane Central FIPS 4203 Feet (WKID: 2277)
out_coordinate_system = arcpy.SpatialReference(2277) # <--- !! Update WKID or path to your desired PCS (in Feet) !!

# The Geographic Transformation needed to transform from WGS 1984 to your chosen PCS
# This is crucial for accuracy. ArcGIS Pro will often suggest one.
# You can find the transformation name or path in ArcGIS Pro's Project tool or documentation.
# Example for WGS 1984 to NAD 1983 (which State Plane 2277 is based on)
# You might need a specific NAD 1983 (2011) or other transformation depending on your data and area
geographic_transformation = "WGS_1984_(ITRF00)_To_NAD_1983" # <--- !! Update this to the correct transformation !!


# The name of the unique ID field in your feature class (should be the same in the projected data)
id_field = "FACILITYID" # <--- !! Updated to FACILITYID !!

# Names for the new fields to be added (these will be added to the projected feature class)
from_adj_field = "from_adjacent_id" # Will hold the ID of the segment adjacent to the START point
to_adj_field = "to_adjacent_id"   # Will hold the ID of the segment adjacent to the END point
direction_float_field = "direction_float" # Will hold the bearing (0-360) from start to end
direction_text_field = "direction_text" # Will hold the cardinal/intercardinal direction text

# Set a small tolerance for comparing point locations in the PROJECTED coordinate system units
# Since the output PCS is in FEET, this tolerance is in FEET.
xy_tolerance = 0.001 # <--- Tolerance set to 0.001 FEET after projection
print(f"Using XY Tolerance: {xy_tolerance} (in units of the projected coordinate system)")


# --- 1. Project the feature class ---
#print(f"Projecting '{original_feature_class_wgs84}' to '{projected_feature_class_path}'...")
## Check if the original feature class exists before proceeding
#if not arcpy.Exists(original_feature_class_wgs84):
#    print(f"Error: Original feature class '{original_feature_class_wgs84}' does not exist.")
#    print("Please ensure the path is correct.")
#    exit() # Exit the script if the original feature class is not found
## Define the output geodatabase path and feature class name
#output_gdb = os.path.dirname(projected_feature_class_path)
#output_name = os.path.basename(projected_feature_class_path)

# Check if the output projected feature class already exists and delete it if you want to overwrite
#if arcpy.Exists(projected_feature_class_path):
#    print(f"Output feature class '{projected_feature_class_path}' already exists. Deleting...")
#    arcpy.Delete_management(projected_feature_class_path)


# --- 2. Check if required fields exist and add them if they don't (on the PROJECTED data) ---
def add_required_fields(feature_class, from_adj_field, to_adj_field, direction_float_field, direction_text_field):
    """
    Add required fields to the feature class if they don't already exist.
    :param feature_class: The feature class to check and add fields to.
    :param from_adj_field: The name of the field for the adjacent ID at the start point.
    :param to_adj_field: The name of the field for the adjacent ID at the end point.
    :param direction_float_field: The name of the field for the direction in degrees.
    :param direction_text_field: The name of the field for the direction as text.
    """
    print("Checking and adding required fields on the projected feature class...")

    existing_fields = [f.name for f in arcpy.ListFields(feature_class)]

    # Determine the data type for the adjacent ID fields based on the id_field type
    # We need to check the field type on the *projected* feature class
    #id_field_type = "TEXT" # Default to TEXT
    #id_field_type = None
    #for field in arcpy.ListFields(feature_class):
    #    if field.name == id_field:
    #        id_field_type = field.type
    #        break
    #if id_field_type is None:
    #    print(f"Error: ID field '{id_field}' not found in the PROJECTED feature class.")
    #    # You might want to exit or raise an error here
    #    exit() # Exiting script

    # Determine the ArcGIS field type for the adjacent ID fields
    # Use "TEXT" if the ID field is a string type, otherwise use "LONG"
    # This ensures compatibility when writing the ID or None
    #adj_field_arcgis_type = "TEXT"
    adj_field_length = 50

    #print(f"Determined adjacent ID field type based on '{id_field}' ({id_field_type}): {adj_field_arcgis_type}")

    fields_to_add = {
        from_adj_field: "TEXT",
        to_adj_field: "TEXT",
        direction_float_field: "DOUBLE",
        direction_text_field: "TEXT"
    }

    for field_name, field_type in fields_to_add.items():
        if field_name not in existing_fields:
            print(f"Adding field: {field_name} ({field_type})")
            if field_type == "TEXT":
                # Add field with specified length for text
                arcpy.AddField_management(feature_class, field_name, field_type, field_length=adj_field_length)
            else:
                # Add numeric field
                arcpy.AddField_management(feature_class, field_name, field_type)
        else:
            print(f"Field '{field_name}' already exists.")


def calculate_bearing(x1, y1, x2, y2):
    """
    Calculate the bearing from point (x1, y1) to point (x2, y2) in degrees, clockwise from North (0-360) - called to calculate value of 'direction_float'.
    :param x1 - float: X coordinate of the start point.
    :param y1 - float: Y coordinate of the start point.
    :param x2 - float: X coordinate of the end point.
    :param y2 - float: Y coordinate of the end point.
    :return: Bearing in degrees (0-360) or None if the points are the same.
    """
    # Handle case where start and end points are the same
    if x1 == x2 and y1 == y2:
        return None # Or return 0, depending on desired behavior for zero-length lines

    # Calculate the angle in radians from the positive X-axis (East)
    # atan2(y, x) gives the angle between the positive x-axis and the point (x, y)
    # We want angle from (x1, y1) to (x2, y2), so use delta_x and delta_y
    delta_x = x2 - x1
    delta_y = y2 - y1
    angle_radians = math.atan2(delta_y, delta_x)

    # Convert radians to degrees
    angle_degrees = math.degrees(angle_radians)

    # Convert angle from positive X-axis (counter-clockwise) to bearing from North (clockwise)
    # Bearing = 90 - angle_degrees
    # Ensure bearing is between 0 and 360
    bearing = (90 - angle_degrees + 360) % 360

    return bearing


def get_direction_text(bearing):
    """
    Convert a bearing (in degrees) to a cardinal/intercardinal direction text.
    :param bearing: Bearing in degrees (0-360).
    :return: Direction text (N, NE, E, SE, S, SW, W, NW) or None if bearing is None.
    """
    if bearing is None:
        return None
    # Ensure bearing is within 0-360
    bearing = bearing % 360

    if (bearing >= 337.5 and bearing <= 360) or (bearing >= 0 and bearing < 22.5):
        return "N"
    elif (bearing >= 22.5 and bearing < 67.5):
        return "NE"
    elif (bearing >= 67.5 and bearing < 112.5):
        return "E"
    elif (bearing >= 112.5 and bearing < 157.5):
        return "SE"
    elif (bearing >= 157.5 and bearing < 202.5):
        return "S"
    elif (bearing >= 202.5 and bearing < 247.5):
        return "SW"
    elif (bearing >= 247.5 and bearing < 292.5):
        return "W"
    elif (bearing >= 292.5 and bearing < 337.5):
        return "NW"
    else:
        return None # Should not happen with bearing 0-360, but good practice


# --- 3. Read feature geometries, calculate direction, and store in memory (from the PROJECTED data) ---
def calculate_direction_values(feature_class, id_field):
    """
    Read the feature geometries from the feature class and calculate direction values.
    :param feature_class - string: Path of the projected feature class to read from.
    :param id_field - string: The name of the unique ID field in the feature class.
    :return feature_data: List of tuples containing feature data with calculated direction values.
    """
    print("Reading projected feature geometries and calculating direction...")
    feature_data = []
    # Use OID@ for internal row identification, SHAPE@ for the geometry object
    # Ensure the id_field is included in the fields list
    fields_for_processing = ['OID@', id_field, 'SHAPE@']

    with arcpy.da.SearchCursor(feature_class, fields_for_processing) as cursor:
        for row in cursor:
            oid = row[0]
            # Get the actual ID from the specified id_field
            feat_id = row[1]
            shape = row[2] # Get the geometry object

            if shape is None:
                # print(f"Warning: Skipping feature with OID {oid} due to None geometry.") # Commented out to reduce console spam
                continue # Skip features with no geometry

            # Get the first and last points from the geometry object
            # For a simple line, points[0] is the start, points[-1] is the end
            try:
                start_point = shape.firstPoint
                end_point = shape.lastPoint
                sx, sy = start_point.X, start_point.Y
                ex, ey = end_point.X, end_point.Y

                # Calculate the bearing (direction_float) using coordinates from the PROJECTED data
                bearing = calculate_bearing(sx, sy, ex, ey)

                # Determine the direction text
                direction_text = get_direction_text(bearing)

            except Exception as e:
                # print(f"Warning: Could not get start/end points or calculate direction for feature with OID {oid}. Error: {e}") # Commented out
                # If calculation fails, set bearing and text to None
                bearing = None
                direction_text = None
                continue # Skip features if points cannot be accessed or direction calculated

            # Store data as (OID, Actual ID, StartX, StartY, EndX, EndY, Bearing, DirectionText)
            feature_data.append((oid, feat_id, sx, sy, ex, ey, bearing, direction_text))

    print(f"Read data and calculated direction for {len(feature_data)} features.")


def get_adjacent_ids(feature_data, xy_tolerance):
    """
    Get the adjacent IDs for each feature in the feature class.
    :param feature_data: List of tuples containing feature data with calculated direction values.
    :param xy_tolerance: Tolerance for comparing point locations in the projected coordinate system units.
    :return: a tuple of two dictionaries holding from_adjacent_id's and to_adjacent_id's for each feature id
    """
    # Create a list of all start and end points with their associated feature info for adjacency check
    all_endpoints = []
    for oid, feat_id, sx, sy, ex, ey in feature_data:
        all_endpoints.append({'id': feat_id, 'oid': oid, 'x': sx, 'y': sy}) # Start point
        all_endpoints.append({'id': feat_id, 'oid': oid, 'x': ex, 'y': ey}) # End point

    # Dictionaries to store the found adjacent IDs, keyed by the feature's OID
    from_adjacent_ids = {}
    to_adjacent_ids = {}

    # Initialize the dictionaries with None
    for oid, feat_id, sx, sy, ex, ey in feature_data:
        from_adjacent_ids[oid] = None
        to_adjacent_ids[oid] = None

    # Calculate the values for 'from_adjacent_id' and 'to_adjacent_id'
    print("Comparing endpoints to find adjacent segments on projected data...")
    for i, (oid, feat_id, sx, sy, ex, ey) in enumerate(feature_data):

        # Compare the start point of the current feature to ALL endpoints from OTHER features
        # This finds the segment connected at the START point (origin)
        for endpoint_info in all_endpoints:
            if endpoint_info['oid'] == oid:
                continue # Don't compare a line's start to its own endpoints

            # Check if the current line's start point (sx, sy) is coincident with endpoint_info's location
            # Use math.dist for distance calculation on projected coordinates
            if math.dist((sx, sy), (endpoint_info['x'], endpoint_info['y'])) < xy_tolerance:
                from_adjacent_ids[oid] = endpoint_info['id']
                # Assuming simple junctions (only one other line connects at an endpoint)
                # If complex junctions exist, you would need to store a list of IDs here.
                break # Found an adjacent segment at the start, move to checking the end

        # Compare the end point of the current feature to ALL endpoints from OTHER features
        # This finds the segment connected at the END point
        for endpoint_info in all_endpoints:
            if endpoint_info['oid'] == oid:
                continue # Don't compare a line's end to its own endpoints

            # Check if the current line's end point (ex, ey) is coincident with endpoint_info's location
            if math.dist((ex, ey), (endpoint_info['x'], endpoint_info['y'])) < xy_tolerance:
                to_adjacent_ids[oid] = endpoint_info['id']
                # Assuming simple junctions
                break # Found an adjacent segment at the end

        if (i + 1) % 1000 == 0:
            print(f"Processed {i + 1} features for adjacency...")

    print("Finished finding adjacent segments.")
    return from_adjacent_ids, to_adjacent_ids


def update_fields(feature_class, feature_data, from_adj_field, to_adj_field, direction_float_field, direction_text_field):
    """
    Update the fields in the feature class with the calculated values.
    :param feature_class: The feature class to update.
    :param from_adj_field: The name of the field for the adjacent ID at the start point.
    :param to_adj_field: The name of the field for the adjacent ID at the end point.
    :param direction_float_field: The name of the field for the direction in degrees.
    :param direction_text_field: The name of the field for the direction as text.
    """
    print("Updating fields in the feature class...")
    # --- 5. Update the attribute table with calculated values (on the PROJECTED data) ---
    print(f"Updating attribute table of projected feature class with {from_adj_field}, {to_adj_field}, {direction_float_field}, and {direction_text_field}...")
    update_fields = ['OID@', from_adj_field, to_adj_field, direction_float_field, direction_text_field]

    # Start an edit session for safe updating
    # Check if the feature class is registered as versioned if working with enterprise geodatabase
    # For file geodatabases, startEditing(False, False) is typical
    desc = arcpy.Describe(feature_class)
    edit = arcpy.da.Editor(desc.path)

    # Create a dictionary to quickly look up calculated data by OID
    feature_data_dict = {item[0]: item for item in feature_data}

    try:
        # Check if editing is possible and start
        if not edit.isEditing:
            edit.startEditing(False, False) # Use False, False for file geodatabase
        edit.startOperation()

        with arcpy.da.UpdateCursor(feature_class, update_fields) as cursor:
            for row in cursor:
                oid = row[0]

                # Get the calculated data for this OID from the dictionary
                calculated_data = feature_data_dict.get(oid)

                if calculated_data:
                    # Unpack the stored data: (OID, Actual ID, StartX, StartY, EndX, EndY, Bearing, DirectionText)
                    # We only need the Bearing and DirectionText for this update step
                    _, _, _, _, _, _, bearing, direction_text = calculated_data

                    # Get the stored adjacent IDs using the feature's OID from the adjacency dictionaries
                    from_id = from_adjacent_ids.get(oid)
                    to_id = to_adjacent_ids.get(oid)

                    # Assign values to the update row
                    row[1] = from_id          # from_adjacent_id
                    row[2] = to_id            # to_adjacent_id
                    row[3] = bearing          # direction_float
                    row[4] = direction_text   # direction_text

                else:
                    # If for some reason the feature wasn't processed in Step 2 (e.g., None geometry),
                    # ensure fields are set to None
                    row[1] = None
                    row[2] = None
                    row[3] = None
                    row[4] = None


                cursor.updateRow(row)

        edit.stopOperation()
        edit.stopEditing(True) # Save edits
        print("Attribute table updated successfully with adjacent IDs and direction.")

    except Exception as e:
        print(f"Error during attribute table update: {e}")
        # Abort edits if an error occurs
        if edit.isEditing:
            edit.stopOperation()
            edit.stopEditing(False) # Abort edits

print("\nScript finished.")