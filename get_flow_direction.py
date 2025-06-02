import os
import math
from dotenv import load_dotenv
import pathlib
import arcpy

def set_environment():
    """
    Set the environment for the script by loading the .env file and defining arcpy env settings.
    Assumes the .env file is in the same directory as this script.
    """
    script_dir = pathlib.Path(__file__).parent.resolve()
    env_path = script_dir / '.env'
    load_dotenv(dotenv_path=env_path)
    arcpy.env.overwriteOutput = True
    arcpy.env.workspace = os.getenv('GDB')  # Set the workspace from the .env file


def get_projected_feature_class(in_fc, out_fc, out_coordinate_system, geographic_transformation):
    """
    Project a feature class using the geographic coordinate system WGS84 to a specified coordinate system
    using the given transformation.
    :param in_fc: Path to the input feature class.
    :param out_fc: Path to the output feature class.
    :param out_coordinate_system: The output coordinate system (SpatialReference object).
    :param geographic_transformation: The geographic transformation to use.
    :return: output feature class path
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
        return out_fc

    except Exception as e:
        print(f"Error during projection: {e}")
        exit()  # Exit the script if projection fails


def add_required_fields(feature_class,
                        from_material_field, to_material_field):
    """
    Add required material fields to the feature class if they don't already exist.
    Assumes 'from_adjacent_id', 'to_adjacent_id', and 'Material_Source' already exist.
    :param feature_class: The projected feature class to check and add fields to.
    :param from_material_field: The name of the field for the material at the start point.
    :param to_material_field: The name of the field for the material at the end point.
    """
    print("Checking and adding required material fields on the projected feature class...")

    existing_fields = [f.name for f in arcpy.ListFields(feature_class)]
    material_length = 50

    fields_to_add = {
        from_material_field: "TEXT",
        to_material_field: "TEXT"
    }

    for field_name, field_type in fields_to_add.items():
        if field_name not in existing_fields:
            print(f"Adding field: {field_name} ({field_type})")
            arcpy.AddField_management(feature_class, field_name, field_type, field_length=material_length)
        else:
            print(f"Field '{field_name}' already exists.")


def calculate_adjacent_and_material(feature_class, id_field, xy_tolerance, pipe_type_map):
    """
    Read the feature geometries from the feature class and calculate adjacent IDs and material types for each segment.
    :param feature_class: Path of the projected feature class to read from.
    :param id_field: The name of the unique ID field in the feature class.
    :param xy_tolerance: Tolerance for comparing point locations in the projected coordinate system units.
    :param pipe_type_map: Dictionary mapping PIPE_TYPE values to material names.
    :return: Dictionary keyed by OID with values:
             { 'from_adjacent_id': ..., 'to_adjacent_id': ..., 'from_material': ..., 'to_material': ... }
    """
    print("Reading projected feature geometries and calculating adjacency + material...")

    # First pass: read geometries & attributes
    features_data = {}
    fields_to_read = ['OID@', id_field, 'SHAPE@', 'PIPE_TYPE']
    with arcpy.da.SearchCursor(feature_class, fields_to_read) as cursor:
        for row in cursor:
            oid, feat_id, shape, pipe_type = row
            if shape is None:
                continue
            try:
                start_pt = shape.firstPoint
                end_pt = shape.lastPoint
                sx, sy = start_pt.X, start_pt.Y
                ex, ey = end_pt.X, end_pt.Y
            except:
                continue
            features_data[oid] = {
                'id': feat_id,
                'sx': sx, 'sy': sy,
                'ex': ex, 'ey': ey,
                'pipe_type': pipe_type
            }

    print(f"Read and processed {len(features_data)} features.")

    # Build endpoint list for adjacency lookup
    endpoints = []
    for oid, data in features_data.items():
        endpoints.append({'oid': oid, 'x': data['sx'], 'y': data['sy']})
        endpoints.append({'oid': oid, 'x': data['ex'], 'y': data['ey']})

    # Prepare output dictionary
    results = {}

    # Second pass: calculate adjacency and material
    for i, (oid, data) in enumerate(features_data.items()):
        sx, sy = data['sx'], data['sy']
        ex, ey = data['ex'], data['ey']

        from_adj = None
        to_adj = None
        from_mat = None
        to_mat = None

        # Find from_adjacent_id/material
        for ep in endpoints:
            if ep['oid'] == oid:
                continue
            if math.dist((sx, sy), (ep['x'], ep['y'])) < xy_tolerance:
                from_adj = features_data[ep['oid']]['id']
                adj_pipe = features_data[ep['oid']]['pipe_type']
                from_mat = pipe_type_map.get(adj_pipe, "Unknown")
                break

        # Find to_adjacent_id/material
        for ep in endpoints:
            if ep['oid'] == oid:
                continue
            if math.dist((ex, ey), (ep['x'], ep['y'])) < xy_tolerance:
                to_adj = features_data[ep['oid']]['id']
                adj_pipe = features_data[ep['oid']]['pipe_type']
                to_mat = pipe_type_map.get(adj_pipe, "Unknown")
                break

        results[oid] = {
            'from_adjacent_id': from_adj,
            'to_adjacent_id': to_adj,
            'from_material': from_mat,
            'to_material': to_mat
        }

        if (i + 1) % 1000 == 0:
            print(f"Processed {i + 1} features for adjacency & material...")

    print("Finished calculating adjacency and material for all features.")
    return results


def update_fields(feature_class, calc_dict,
                  from_adj_field, to_adj_field,
                  material_source_field, from_material_field, to_material_field):
    """
    Update the fields in the feature class with the calculated values.
    :param feature_class: The feature class to update.
    :param calc_dict: Dictionary keyed by OID with calculated values.
    :param from_adj_field: The field name for the start-point adjacent ID.
    :param to_adj_field: The field name for the end-point adjacent ID.
    :param material_source_field: The field name for material source.
    :param from_material_field: The field name for the start-point material.
    :param to_material_field: The field name for the end-point material.
    """
    print("Updating fields in the feature class...")
    update_fields_list = [
        'OID@',
        from_adj_field, to_adj_field,
        material_source_field, from_material_field, to_material_field,
        'PIPE_TYPE'
    ]

    desc = arcpy.Describe(feature_class)
    editor = arcpy.da.Editor(desc.path)

    try:
        if not editor.isEditing:
            editor.startEditing(False, False)
        editor.startOperation()

        with arcpy.da.UpdateCursor(feature_class, update_fields_list) as cursor:
            for row in cursor:
                oid = row[0]
                data = calc_dict.get(oid)

                if data:
                    row[1] = data['from_adjacent_id']
                    row[2] = data['to_adjacent_id']

                    pipe_val = row[update_fields_list.index('PIPE_TYPE')]
                    row[3] = "Legacy" if pipe_val not in (None, 0) else None

                    row[4] = data['from_material']
                    row[5] = data['to_material']
                else:
                    for idx in range(1, len(update_fields_list)):
                        row[idx] = None

                cursor.updateRow(row)

        editor.stopOperation()
        editor.stopEditing(True)
        print("Attribute table updated successfully with adjacency and material fields.")
    except Exception as e:
        print(f"Error during attribute table update: {e}")
        if editor.isEditing:
            editor.stopOperation()
            editor.stopEditing(False)


def run():
    set_environment()

    input_fc_name = os.getenv('INPUT_FC')
    input_fc = os.path.join(arcpy.env.workspace, input_fc_name)

    spatial_ref_wkid = int(os.getenv('SPATIAL_REF_WKID', 2277))
    out_coordinate_system = arcpy.SpatialReference(spatial_ref_wkid)
    geographic_transformation = os.getenv('GEOGRAPHIC_TRANSFORMATION', "WGS_1984_(ITRF00)_To_NAD_1983")

    output_fc_name = f"{input_fc_name}_{spatial_ref_wkid}"
    projected_fc = get_projected_feature_class(input_fc, output_fc_name,
                                               out_coordinate_system, geographic_transformation)

    from_adjacent_id = "from_adjacent_id"
    to_adjacent_id = "to_adjacent_id"
    material_source = "Material_Source"
    from_material = "From_Material"
    to_material = "To_Material"

    # Only add material fields; 'from_adjacent_id', 'to_adjacent_id', and 'Material_Source' already exist
    add_required_fields(projected_fc,
                        from_material, to_material)

    id_field_name = "FACILITYID"
    xy_tolerance = float(os.getenv('XY_TOLERANCE', 0.001))
    PIPE_TYPE_TO_MATERIAL_MAP = {
        1: "PVC",
        2: "RCP",
        3: "Cast Iron",
        4: "Ductile Iron",
        5: "VCP",
        6: "R.C.C.P",
        None: "Unknown",
        0: "Unknown",
        "N/A": "Unknown"
    }

    calc_results = calculate_adjacent_and_material(projected_fc, id_field_name,
                                                   xy_tolerance, PIPE_TYPE_TO_MATERIAL_MAP)

    update_fields(projected_fc, calc_results,
                  from_adjacent_id, to_adjacent_id,
                  material_source, from_material, to_material)

    print("\nScript finished.")


if __name__ == "__main__":
    run()
