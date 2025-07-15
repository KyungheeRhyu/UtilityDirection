import os
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
    with arcpy.da.UpdateCursor(line_layer, ['OBJECTID', new_field]) as cursor:
        for row in cursor:
            arcpy.management.SelectLayerByAttribute(line_layer, 'NEW_SELECTION', f"OBJECTID = {row[0]}")
            print(f"Selected line segment with OBJECTID: {row[0]}")
            # Select points that intersect with the line segment - TODO - adjust search distance if necessary
            arcpy.management.SelectLayerByLocation(
                in_layer=point_layer,
                overlap_type="INTERSECT",
                select_features=line_layer,
                search_distance="0.05 Meters",
                selection_type="NEW_SELECTION"
            )
            selected_point_count = arcpy.management.GetCount(point_layer)[0]
            print(f"Selected points overlapping with line segment: {selected_point_count}")
            #rint(f"Selected line segments: {arcpy.management.GetCount(line_layer)}\n")
            row[1] = int(selected_point_count)
            cursor.updateRow(row)


def run():
    """
    Main function to run the script.
    """
    set_environment()
    line_fc = os.getenv('INPUT_FC')
    point_fc = os.getenv('MANHOLE_FC')
    line_layer = arcpy.MakeFeatureLayer_management(line_fc, "line_layer")
    point_layer = arcpy.MakeFeatureLayer_management(point_fc, "point_layer")
    get_connected_point_count(line_layer, point_layer)


if __name__ == "__main__":
    run()