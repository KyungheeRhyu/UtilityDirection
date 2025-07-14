import os
from collections import Counter
import datetime as dt
import arcpy
from shared import set_environment

'''
To be run after the adjacency IDs have been populated in the sewer line layer.
1. Add fields ‘From_Manhole’ and ‘To_Manhole’ to table for line layer
2. Using lines layer with adjacent id’s populated, for each line segment (segment A):
    a. Get FACILITYID of line and to_adjacent_id (segment B)
    b. Select both lines
    c. Get coordinates of all points that make up both lines (separate function?)
    d. Get common coordinates to get intersection (separate function)
    e. Select manhole from coordinates
    f. Write manhole id to attribute table of line layer for:
        i. To_Manhole for segment A
        ii. From_Manhole for segment B

'''

def get_line_coordinates(line_layer):
    """
    Get the coordinates of all points that make up the (selected) line segments in the specified layer.
    :param line_layer: The feature layer containing sewer line segments.
    :return: A list of tuples containing coordinates for each line segment.
    """
    coordinates = []
    with arcpy.da.SearchCursor(line_layer, ['SHAPE@']) as cursor:
        for row in cursor:
            shape = row[0]
            if shape:
                coords = [point for point in shape.getPart(0)]
                if coords:
                    coords = [(point.X, point.Y) for point in coords]
                for pair in coords:
                    coordinates.append(pair)
    print(f"Extracted coordinates from {arcpy.management.GetCount(line_layer)} line segments, coordinates: {coordinates}.")
    return coordinates


def get_line_intersection(coord_pairs):
    """
    Get the common coordinates between two input line segments.
    :param coord_pairs: A list of tuples containing coordinate pairs for each line segment.
    :return: A tuple of common coordinates.
    """
    if len(coord_pairs) < 2:
        return ()
    # Round the coordinates to 2 decimal places to avoid floating point precision issues - nearest hundredth of a meter should be fine but may need to be adjusted
    rounded_pairs = [(round(x, 2), round(y, 2)) for (x, y) in coord_pairs]
    print(f"Rounded coordinate pairs: {rounded_pairs}")
    intersection_coords = [k for (k, v) in Counter(rounded_pairs).items() if v > 1]
    if not intersection_coords:
        print("No common coordinates found between the line segments.")
    else:
        print(f"Found common coordinates: {intersection_coords}")
        return intersection_coords[0]


def find_manhole_id(coords, spatial_reference, manhole_layer):
    """
    Find the manhole ID that corresponds to the given coordinates.
    :param coords: A tuple of coordinates (x, y) representing the line segment.
    :param spatial_reference: The spatial reference of the coordinates (arcpy SpatialReference object).
    :param manhole_layer: The feature layer containing manholes.
    :return: The manhole ID if found, otherwise None.
    """
    # Select the manhole features that intersect the line segment
    #arcpy.management.SelectLayerByLocation(manhole_layer, 'INTERSECT', coords)
    print(f"Selecting manhole features that intersect with coordinates: {coords}")
    try:
        point_geom = arcpy.PointGeometry(arcpy.Point(coords[0], coords[1]), spatial_reference)
    except Exception as e:
        print(f"Error creating PointGeometry from coordinates {coords}: {e}")
        return None
    arcpy.management.SelectLayerByLocation(
        in_layer=manhole_layer,
        overlap_type="INTERSECT",
        select_features=point_geom,
        search_distance="0.05 Meters",
        selection_type="NEW_SELECTION"
    )

    print(f"Selected manhole features: {arcpy.management.GetCount(manhole_layer)}")

    # Get the manhole ID from the selected features
    with arcpy.da.SearchCursor(manhole_layer, ['FACILITYID']) as cursor:
        for row in cursor:
            return row[0]
    return None


def update_manhole_ids_single_side(line_layer, adjacent_id_field, adjacency_type, manhole_layer, manhole_id_field, spatial_reference):
    """
    Update the manhole IDs for a single side (from or to) of the line segments.
    :param line_layer: The feature layer containing sewer line segments.
    :param adjacent_id_field: The field containing the adjacent line segment ID.
    :param adjacency_type: The type of adjacency - either 'to' or 'from'. (only used for logging)
    :param manhole_layer: The feature layer containing manholes.
    :param manhole_id_field: The field to update with the manhole ID.
    :param spatial_reference: The spatial reference of the coordinates (arcpy SpatialReference object).
    """
    with arcpy.da.UpdateCursor(line_layer, ['FACILITYID', adjacent_id_field, manhole_id_field]) as cursor:
        for row in cursor:
            facility_id = row[0]
            adjacent_id = row[1]
            print(f"\n Processing line segment with FACILITYID: {facility_id} and {adjacency_type} adjacent id: {adjacent_id}")

            # Select the line segment and its adjacent line segment
            arcpy.management.SelectLayerByAttribute(line_layer, 'NEW_SELECTION', f"FACILITYID in ('{facility_id}', '{adjacent_id}')")
            print(f"Selected line segments: {arcpy.management.GetCount(line_layer)}")

            # Get the coordinates of the selected line segments
            line_coords = get_line_coordinates(line_layer)

            line_intersection = get_line_intersection(line_coords)

            # Find the corresponding manhole for the line segment
            try:
                manhole_id = find_manhole_id(line_intersection, spatial_reference, manhole_layer)
            except Exception as e:
                print(f"Error finding manhole ID: {e}")
                manhole_id = None

            # Assign the manhole ID to the appropriate fields
            if manhole_id:
                # populate from_manhole_id for segment being processed
                row[2] = manhole_id
                cursor.updateRow(row)


def assign_manhole_ids(line_layer, manhole_layer, spatial_reference):
    """
    Assign manhole IDs to line segments based on adjacent IDs and coordinates.
    
    :param line_layer: The feature layer containing sewer line segments.
    :param manhole_layer: The feature layer containing manholes.
    :param spatial_reference: The spatial reference of the coordinates (arcpy SpatialReference object).
    """
    # add necessary fields to the line layer if they do not exist
    line_fields = [f.name for f in arcpy.ListFields(line_layer)]
    from_manhole_field = 'from_manhole_id'
    to_manhole_field = 'to_manhole_id'
    new_fields = [from_manhole_field, to_manhole_field]
    for field in new_fields:
        if field not in line_fields:
            arcpy.AddField_management(line_layer, field, 'TEXT')

    update_manhole_ids_single_side(line_layer, 'to_adjacent_id', 'to', manhole_layer, to_manhole_field, spatial_reference)
    arcpy.management.SelectLayerByAttribute(line_layer, 'CLEAR_SELECTION')
    update_manhole_ids_single_side(line_layer, 'from_adjacent_id', 'from', manhole_layer, from_manhole_field, spatial_reference)


def run():
    start_time = dt.datetime.now()
    print(f"Script started at {start_time}")
    set_environment()
    line_fc = os.getenv('INPUT_FC')
    manhole_fc = os.getenv('MANHOLE_FC')
    line_layer = arcpy.MakeFeatureLayer_management(line_fc, "line_layer")
    manhole_layer = arcpy.MakeFeatureLayer_management(manhole_fc, "manhole_layer")
    spatial_reference = arcpy.Describe(line_layer).spatialReference

    # Call the function to assign manhole IDs
    assign_manhole_ids(line_layer, manhole_layer, spatial_reference)
    end_time = dt.datetime.now()
    duration = end_time - start_time
    print(f"Script completed at {end_time} - Duration: {duration}")


if __name__ == "__main__":
    run()
