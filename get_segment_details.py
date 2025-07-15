import os
import datetime as dt
import arcpy
from shared import set_environment

def get_connected_point_count(line_layer, point_layer):
    """
    Write number of points connected to each segment to a new field. (Assumes both layers use the same spatial reference.)
    :param line_layer: The feature layer containing sewer line segments.
    :param point_layer: The feature layer containing sewer line points including (or containing only) manholes.
    """
    line_fields = [f.name for f in arcpy.ListFields(line_layer)]
    new_field = 'connected_point_count'
    if new_field not in line_fields:
        arcpy.AddField_management(line_layer, new_field, 'SHORT')
        print(f"Added new field '{new_field}' to line layer.")
    with arcpy.da.UpdateCursor(line_layer, ['OBJECTID', new_field]) as cursor:
        print(f"Updating '{new_field}' field in line layer with connected point counts...")
        for row in cursor:
            arcpy.management.SelectLayerByAttribute(line_layer, 'NEW_SELECTION', f"OBJECTID = {row[0]}")
            #print(f"Selected line segment with OBJECTID: {row[0]}")
            # Select points that intersect with the line segment - TODO - adjust search distance if necessary
            arcpy.management.SelectLayerByLocation(
                in_layer=point_layer,
                overlap_type="INTERSECT",
                select_features=line_layer,
                search_distance=None,
                selection_type="NEW_SELECTION"
            )
            selected_point_count = arcpy.management.GetCount(point_layer)[0]
            #print(f"Selected points overlapping with line segment: {selected_point_count}")
            #rint(f"Selected line segments: {arcpy.management.GetCount(line_layer)}\n")
            row[1] = int(selected_point_count)
            cursor.updateRow(row)


def run():
    """
    Main function to run the script.
    """
    start_time = dt.datetime.now()
    print(f"Script started at {start_time}")
    set_environment()
    line_fc = os.getenv('INPUT_FC')
    point_fc = os.getenv('POINT_FC')
    line_layer = arcpy.MakeFeatureLayer_management(line_fc, "line_layer")
    point_layer = arcpy.MakeFeatureLayer_management(point_fc, "point_layer")
    get_connected_point_count(line_layer, point_layer)
    end_time = dt.datetime.now()
    duration = end_time - start_time
    print(f"Script ended at {end_time}")
    print(f"Total duration: {duration}")


if __name__ == "__main__":
    run()