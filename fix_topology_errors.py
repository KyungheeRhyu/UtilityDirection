from arcgis.gis import GIS
from arcgis.features import FeatureLayer
from arcgis.geometry import Point, SpatialReference, project
import math

# --- CONFIG ---
GIS_LOGIN = "home"  # or use credentials
LINE_URL = "https://services2.arcgis.com/kXGqZY4GIOcEYxoF/arcgis/rest/services/Sanitary_Sewer_Subset/FeatureServer/0"
POINT_URL = "https://services2.arcgis.com/kXGqZY4GIOcEYxoF/arcgis/rest/services/Sanitary_Sewer_Subset/FeatureServer/1"

SR_WGS84 = SpatialReference(4326)
SR_PROJECTED = SpatialReference(2276)  # NAD83 / Texas North Central (ftUS)

SNAP_TOLERANCE_FEET = 0.3

# --- GEOMETRY HELPERS ---

def get_endpoints(polyline_feature):
    """
    Return start and end Point objects from a polyline geometry dict.
    :param polyline_feature - tuple containing a single Feature object: The polyline geometry as a list of features.
    :return: tuple of Point objects (start, end)
    """

    feature_dict = polyline_feature[0].as_dict
    #print(f'feature_dict: {feature_dict}')
    paths = feature_dict['geometry']['paths']
    p1 = Point({"x": paths[0][0], "y": paths[0][1], "spatialReference": feature_dict['geometry']['spatialReference']})
    p2 = Point({"x": paths[-1][0], "y": paths[-1][1], "spatialReference": feature_dict['geometry']['spatialReference']})
    print(f'Endpoints:\np1: {p1},\np2: {p2}\n\n')
    return p1, p2



def point_distance(p1, p2):
    """
    Euclidean distance between two arcgis Point objects (must be in same spatial reference).
    """
    print(f'p1: {p1}, p2: {p2}')
    if p1 and p2:
        return math.hypot(p1['x'] - p2['x'], p1['y'] - p2['y'])
    else:
        print("One of the points is None, returning None for distance.")
        return None


def find_nearest_point(target_pt, candidate_pts, tolerance):
    """Returns the nearest candidate point within the specified tolerance, else None."""
    nearest = None
    min_dist = tolerance
    for pt in candidate_pts:
        dist = point_distance(target_pt, pt)
        if dist and dist <= min_dist:
            nearest = pt
            min_dist = dist
        elif dist is None:
            nearest = None
    return nearest


# --- CORE PROCESSING ---

def get_features(layer):
    """Query all features from a FeatureLayer."""
    return layer.query(where="1=1", out_fields="*", return_geometry=True).features


def snap_line_endpoints(line_feature, point_pool, line_endpoints, tolerance):
    """Try to snap start/end of line to nearest point/endpoint in tolerance."""
    modified = False
    geom = line_feature.geometry
    paths = geom['paths'][0]

    start_pt = Point({"x": paths[0][0], "y": paths[0][1], "spatialReference": geom['spatialReference']})
    end_pt = Point({"x": paths[-1][0], "y": paths[-1][1], "spatialReference": geom['spatialReference']})

    for i, pt in enumerate([start_pt, end_pt]):
        nearest = find_nearest_point(pt, point_pool, tolerance)
        if not nearest:
            nearest = find_nearest_point(pt, line_endpoints, tolerance)

        if nearest:
            if i == 0:  # snap start
                paths[0][0] = nearest.x
                paths[0][1] = nearest.y
            else:       # snap end
                paths[-1][0] = nearest.x
                paths[-1][1] = nearest.y
            modified = True
        else:
            print(f"No snap found for {'start' if i == 0 else 'end'} of line {line_feature.attributes['FACILITYID']}")

    if modified:
        # Update geometry in WGS84
        new_geom_proj = {
            "paths": [paths],
            "spatialReference": geom['spatialReference']
        }
        geom_projected = project(new_geom_proj, SR_PROJECTED, SR_WGS84)
        line_feature.geometry = geom_projected
        return line_feature
    else:
        return None


def fix_dangles(lines, points):
    """Projects geometries, snaps endpoints, and returns list of modified line features."""
    updated = []

    # Project points and lines to EPSG:2276
    point_proj = [project(pt.geometry, SR_WGS84, SR_PROJECTED) for pt in points]
    line_proj = [(ln, project(ln.geometry, SR_WGS84, SR_PROJECTED)) for ln in lines]
    print(f"Projected {len(point_proj)} points and {len(line_proj)} lines to EPSG:2276.")
    print(f"line_proj sample: {line_proj[0] if line_proj else 'No lines'}")
    # Build list of all line endpoints (in EPSG:2276)
    all_line_endpoints = []
    #for _, proj_geom in line_proj:
    for proj_geom in line_proj:
        start, end = get_endpoints(proj_geom)
        all_line_endpoints.extend([start, end])

    # Snap logic
    for original_line, proj_geom in line_proj:
        modified_feature = snap_line_endpoints(original_line, point_proj, all_line_endpoints, SNAP_TOLERANCE_FEET)
        if modified_feature:
            updated.append(modified_feature)
            print(f"Line {original_line.attributes['FACILITYID']} modified.")

    return updated


# --- MAIN SCRIPT ---

def run():
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
