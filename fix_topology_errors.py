from arcgis.gis import GIS
from arcgis.features import FeatureLayer
from arcgis.geometry import Point, SpatialReference, project
import math


'''
Fix topology errors in a utility line layer (in a feature service hosted in ArcGIS Online) by snapping endpoints of line segments to the nearest point within a specified tolerance.
TODO - modify script to fix topology errors by snapping line endpoints to the nearest point within a specified tolerance - for now:
- do not try to snap line endpoints to each other
- do not try to move point features
'''

# --- CONFIG ---
GIS_LOGIN = "home"
LINE_URL = "https://services2.arcgis.com/kXGqZY4GIOcEYxoF/arcgis/rest/services/Sanitary_Sewer_Subset/FeatureServer/0"
POINT_URL = "https://services2.arcgis.com/kXGqZY4GIOcEYxoF/arcgis/rest/services/Sanitary_Sewer_Subset/FeatureServer/1"

SR_WGS84 = SpatialReference(4326)
SR_PROJECTED = SpatialReference(2276)

SNAP_TOLERANCE_FEET = 0.3

# --- GEOMETRY HELPERS ---

def get_endpoints(polyline_feature):
    """
    Return start and end Point objects from a polyline geometry dict.
    :param polyline_feature - tuple containing a single Feature object: the polyline feature from which endpoints will be extracted
    :return: tuple of Point objects: first point (start), second point (end)
    """
    feature_dict = polyline_feature[0].as_dict
    paths = feature_dict['geometry']['paths']
    p1 = Point({"x": paths[0][0], "y": paths[0][1], "spatialReference": feature_dict['geometry']['spatialReference']})
    p2 = Point({"x": paths[-1][0], "y": paths[-1][1], "spatialReference": feature_dict['geometry']['spatialReference']})
    print(f'Endpoints:\np1: {p1},\np2: {p2}\n\n')
    return p1, p2


def get_point_distance(p1, p2):
    """
    Euclidean distance between two arcgis Point objects.
    Only works if both inputs are Points; otherwise returns None.
    """
    if isinstance(p1, Point) and isinstance(p2, Point):
        return math.hypot(p1.x - p2.x, p1.y - p2.y)
    else:
        print(f"get_point_distance error: invalid types\n  p1: {type(p1)}, p2: {type(p2)}")
        return None


def find_nearest_point(target_pt, candidate_pts, tolerance):
    """
    Return the nearest Point within the specified tolerance.
    :param target_pt - Point object: point to be examined
    :param candidate_pts - list of Point objects: list of points for comparison
    :param tolerance - float: distance within which to find the nearest point
    :return: nearest Point or None
    """
    nearest = None
    min_dist = tolerance
    for pt in candidate_pts:
        dist = get_point_distance(target_pt, pt)
        if dist is not None and dist <= min_dist:
            nearest = pt
            min_dist = dist
    return nearest


# --- CORE PROCESSING ---

def get_features(layer):
    """Query all features from a FeatureLayer."""
    return layer.query(where="1=1", out_fields="*", return_geometry=True).features


def snap_line_endpoints(line_feature, point_pool, line_endpoints, tolerance):
    """
    Snap endpoints of a line feature to nearby points or line ends within tolerance.
    :param line_feature: original Feature (WGS84)
    :param point_pool: list of Point (projected)
    :param line_endpoints: list of Point (projected)
    :param tolerance: float (feet)
    :return: updated Feature or None
    """
    modified = False
    geom = line_feature.geometry
    paths = geom['paths'][0]

    start_pt = Point({"x": paths[0][0], "y": paths[0][1], "spatialReference": geom['spatialReference']})
    end_pt = Point({"x": paths[-1][0], "y": paths[-1][1], "spatialReference": geom['spatialReference']})

    proj_start = project(start_pt, SR_WGS84, SR_PROJECTED)
    proj_end = project(end_pt, SR_WGS84, SR_PROJECTED)

    for i, pt in enumerate([proj_start, proj_end]):
        nearest = find_nearest_point(pt, point_pool, tolerance)
        if not nearest:
            nearest = find_nearest_point(pt, line_endpoints, tolerance)

        if nearest:
            if i == 0:
                paths[0][0] = nearest.x
                paths[0][1] = nearest.y
            else:
                paths[-1][0] = nearest.x
                paths[-1][1] = nearest.y
            modified = True
        else:
            print(f"No snap found for {'start' if i == 0 else 'end'} of line {line_feature.attributes.get('FACILITYID', 'UNKNOWN')}")

    if modified:
        new_geom = {
            "paths": [paths],
            "spatialReference": geom['spatialReference']
        }
        updated_geom = project(new_geom, SR_PROJECTED, SR_WGS84)
        line_feature.geometry = updated_geom
        return line_feature
    else:
        return None


def fix_dangles(lines, points):
    """
    Projects geometries, snaps endpoints, and returns list of modified line features.
    """
    updated = []

    point_proj = [project(pt.geometry, SR_WGS84, SR_PROJECTED) for pt in points]
    line_proj = [(ln, project(ln.geometry, SR_WGS84, SR_PROJECTED)) for ln in lines]
    print(f"Projected {len(point_proj)} points and {len(line_proj)} lines to EPSG:2276.")

    all_line_endpoints = []
    for proj_geom in line_proj:
        start, end = get_endpoints(proj_geom)
        all_line_endpoints.extend([start, end])

    for original_line, _ in line_proj:
        modified_feature = snap_line_endpoints(original_line, point_proj, all_line_endpoints, SNAP_TOLERANCE_FEET)
        if modified_feature:
            updated.append(modified_feature)
            print(f"Line {original_line.attributes.get('FACILITYID', 'UNKNOWN')} modified.")

    return updated


# --- MAIN SCRIPT ---

def run():
    """
    Main entry point for executing snapping process.
    """
    GIS(GIS_LOGIN)
    line_layer = FeatureLayer(LINE_URL)
    point_layer = FeatureLayer(POINT_URL)

    print("Fetching features...")
    lines = get_features(line_layer)
    points = get_features(point_layer)
    print(f"{len(lines)} lines and {len(points)} points loaded.")

    print("Fixing dangles...")
    updated_features = fix_dangles(lines, points)

    if updated_features:
        print(f"{len(updated_features)} lines modified. Uploading...")
        result = line_layer.edit_features(updates=updated_features)
        print("Edit result:", result)
    else:
        print("No features needed editing.")

if __name__ == "__main__":
    run()
