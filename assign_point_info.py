import os
from collections import Counter
import datetime as dt
import arcpy
from shared import set_environment

'''
Full overview below not yet updated to reflect changes in this file.

To be run after the adjacency IDs have been populated in the sewer line layer.
1. Add fields ‘from_point_id’, ‘to_point_id’, ‘from_point_type’, and ‘to_point_type’ to table for line layer
2. Using lines layer with adjacent id’s populated, for each line segment (segment A):
    a. Get FACILITYID of line and adjacent line segment (segment B) using either to_adjacent_id or from_adjacent_id
    b. Select both lines
    c. Get coordinates of all points that make up both lines (separate function?)
    d. Get common coordinates to get intersection (separate function)
    e. Select point from coordinates
    f. Write the following to the attribute table of line layer for:
        i. to_point_id for segment A
        ii. from_point_id for segment B
        iii. to_point_type for segment A
        iv. from_point_type for segment B

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


# TODO - remove if not needed
def get_line_endpoints(line_segment):
    """
    Get the start and end points of a line segment.
    :param line_segment: A tuple containing the coordinates of the line segment.
    :return: A tuple containing the start and end points of the line segment.
    """
    if not line_segment:
        return None, None
    start_point = (line_segment[0][0], line_segment[0][1])
    end_point = (line_segment[-1][0], line_segment[-1][1])
    return start_point, end_point


def find_point_info(coords, spatial_reference, point_layer):
    """
    Find the ID and feature type of the point that corresponds to the given coordinates.
    :param coords: A tuple of coordinates (x, y) representing the line segment.
    :param spatial_reference: The spatial reference of the coordinates (arcpy SpatialReference object).
    :param point_layer: The feature layer containing sewer line points.
    :return: A dictionary containing the point ID and feature type if found, otherwise None.
    """
    # Select the point features that intersect the line segment
    #arcpy.management.SelectLayerByLocation(point_layer, 'INTERSECT', coords)
    print(f"Selecting point features that intersect with coordinates: {coords}")
    try:
        point_geom = arcpy.PointGeometry(arcpy.Point(coords[0], coords[1]), spatial_reference)
        print(f"Point geometry created: {point_geom.firstPoint}")
    except Exception as e:
        print(f"Error creating PointGeometry from coordinates {coords}: {e}")
        return None
    try:
        # adjust the search distance if necessary but hope to fix all topology issues before final run of script
        arcpy.management.SelectLayerByLocation(
            in_layer=point_layer,
            overlap_type="INTERSECT",
            select_features=point_geom,
            #search_distance=None,
            #search_distance="0.01 Meters",
            search_distance="0.05 Meters",
            selection_type="NEW_SELECTION"
        )
    except Exception as e:
        print(f"Error selecting point features using SelectLayerByLocation: {e}")
        return None

    print(f"Selected point features: {arcpy.management.GetCount(point_layer)}")

    # Get the point ID from the selected features
    with arcpy.da.SearchCursor(point_layer, ['FACILITYID', 'FEATURE_DE']) as cursor:
        for row in cursor:
            return {
                'point_id': row[0],
                'feature_type': row[1]
            }
    #return None


def update_point_info_single_side(line_layer, adjacent_id_field, adjacency_type, point_layer, point_id_field, point_type_field, spatial_reference):
    """
    Update the point IDs for a single side (from or to) of the line segments.
    :param line_layer: The feature layer containing sewer line segments.
    :param adjacent_id_field: The field containing the adjacent line segment ID.
    :param adjacency_type: The type of adjacency - either 'to' or 'from'. (only used for logging)
    :param point_layer: The feature layer containing sewer line points.
    :param point_id_field: The field to update with the point ID.
    :param point_type_field: The field to update with the point type.
    :param spatial_reference: The spatial reference of the coordinates (arcpy SpatialReference object).
    """
    with arcpy.da.UpdateCursor(line_layer, ['FACILITYID', adjacent_id_field, point_id_field, point_type_field]) as cursor:
        for row in cursor:
            facility_id = row[0]
            adjacent_id = row[1]
            print(f"\nProcessing line segment with FACILITYID: {facility_id} and {adjacency_type} adjacent id: {adjacent_id}")

            # Select the line segment and its adjacent line segment
            arcpy.management.SelectLayerByAttribute(line_layer, 'NEW_SELECTION', f"FACILITYID in ('{facility_id}', '{adjacent_id}')")
            print(f"Selected line segments: {arcpy.management.GetCount(line_layer)}")

            # Get the coordinates of the selected line segments
            line_coords = get_line_coordinates(line_layer)

            line_intersection = get_line_intersection(line_coords)

            # Find the corresponding point for the line segment
            try:
                point_dict = find_point_info(line_intersection, spatial_reference, point_layer)
            except Exception as e:
                print(f"Error finding point dictionary: {e}")
                point_dict = None

            # Assign the point ID to the appropriate fields
            if point_dict:
                # populate from_point_dict for segment being processed
                row[2] = point_dict['point_id']
                row[3] = point_dict['feature_type']
                cursor.updateRow(row)


def assign_point_info(line_layer, point_layer, spatial_reference):
    """
    Assign point IDs to line segments based on adjacent IDs and coordinates.
    
    :param line_layer: The feature layer containing sewer line segments.
    :param point_layer: The feature layer containing sewer line points.
    :param spatial_reference: The spatial reference of the coordinates (arcpy SpatialReference object).
    """
    # add necessary fields to the line layer if they do not exist
    line_fields = [f.name for f in arcpy.ListFields(line_layer)]
    from_point_id_field = 'from_point_id'
    to_point_id_field = 'to_point_id'
    from_point_type_field = 'from_point_type'
    to_point_type_field = 'to_point_type'
    new_fields = [from_point_id_field, to_point_id_field, from_point_type_field, to_point_type_field]
    for field in new_fields:
        if field not in line_fields:
            arcpy.AddField_management(line_layer, field, 'TEXT')

    #update_point_info_single_side(line_layer, 'to_adjacent_id', 'to', point_layer, to_point_id_field, to_point_type_field, spatial_reference)
    #arcpy.management.SelectLayerByAttribute(line_layer, 'CLEAR_SELECTION')
    #update_point_info_single_side(line_layer, 'from_adjacent_id', 'from', point_layer, from_point_id_field, from_point_type_field, spatial_reference)

    with arcpy.da.UpdateCursor(line_layer, ['FACILITYID', to_point_id_field, from_point_id_field, to_point_type_field, from_point_type_field, 'SHAPE@']) as cursor:
        for row in cursor:
            #facility_id = row[0]
            #to_point_id = row[1]
            #from_point_id = row[2]
            #to_point_type = row[3]
            #from_point_type = row[4]
            shape = row[5]
            line_start = shape.firstPoint
            start_point_info = find_point_info((line_start.X, line_start.Y), spatial_reference, point_layer)
            if start_point_info:
                row[2] = start_point_info['point_id']
                row[4] = start_point_info['feature_type']
            line_end = shape.lastPoint
            end_point_info = find_point_info((line_end.X, line_end.Y), spatial_reference, point_layer)
            if end_point_info:
                row[1] = end_point_info['point_id']
                row[3] = end_point_info['feature_type']
            cursor.updateRow(row)


def run():
    start_time = dt.datetime.now()
    print(f"Script started at {start_time}")
    set_environment()
    line_fc = os.getenv('INPUT_FC')
    point_fc = os.getenv('POINT_FC')
    line_layer = arcpy.MakeFeatureLayer_management(line_fc, "line_layer")
    point_layer = arcpy.MakeFeatureLayer_management(point_fc, "point_layer")
    spatial_reference = arcpy.Describe(line_layer).spatialReference

    # Call the function to assign point IDs
    assign_point_info(line_layer, point_layer, spatial_reference)
    print(f'spatial reference of line layer: {spatial_reference.name}')
    print(f'spatial reference of point layer: {arcpy.Describe(point_layer).spatialReference.name}')
    end_time = dt.datetime.now()
    duration = end_time - start_time
    print(f"Script completed at {end_time} - Duration: {duration}")


if __name__ == "__main__":
    run()
