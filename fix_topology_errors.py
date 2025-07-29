from arcgis.gis import GIS
from arcgis.features import FeatureLayer, FeatureSet, use_proximity
from arcgis.geometry import Point, SpatialReference, project #within cannot be imported
#within cannot be imported from arcgis.geometry.functions
#from arcgis.geometry.functions import within
#from arcgis.geometry.filters import contains, within
from arcgis.geometry.filters import intersects, within
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


def get_buffer_feature_set(gis, item_title=None, point_layer=None, buffer_distance=None):
    """
    Return a FeatureSet of buffered features from the specified item in ArcGIS Online or a new buffer created from the given point layer.
    :param gis: GIS object - the GIS connection to use
    :param item_title: str or None - title of the existing item to fetch, if None, item will be created
    :param point_layer: FeatureLayer or None - if provided, will use this layer to create buffers
    :param buffer_distance: float or None - distance in feet to create buffers, can be None if using an existing item
    :return: FeatureSet or None if item not found
    """
    search_results = gis.content.search(item_title, item_type="Feature Service", max_items=1)
    print(f"Found {len(search_results)} search results for item title: {item_title}")
    if search_results:
        buffer_feature_layer = search_results[0].layers[0].query(where="1=1", return_geometry=True)
    else:
        buffer_feature_layer = use_proximity.create_buffers(point_layer, distances=[buffer_distance], units="Feet", output_name=item_title)
    print(f"Buffer feature layer contains {len(buffer_feature_layer.features)} features.")
    # TODO - clean this up if feature layer works as expected
    buffer_feature_set = FeatureSet.from_dict({buffer_feature_layer})
    #return buffer_feature_set
    return buffer_feature_layer

# --- GEOMETRY HELPERS ---

def get_endpoints(line_geom: dict) -> list:
    """Extracts start and end Points from a line geometry."""
    path = line_geom['paths'][0]
    sr = line_geom['spatialReference']
    return [
        Point({"x": path[0][0], "y": path[0][1], "spatialReference": sr}),
        Point({"x": path[-1][0], "y": path[-1][1], "spatialReference": sr})
    ]


def get_point_distance(p1: Point, p2: Point) -> float:
    """Return the Euclidean distance between two Points."""
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def is_snapped(endpoint: Point, point_geom: Point, tolerance: float = SNAP_TOLERANCE_FEET) -> bool:
    """
    Check whether an endpoint is already snapped to the point.
    :param endpoint: Point - the endpoint to check
    :param point_geom: Point - the point geometry to check against
    :param tolerance: float - the snapping tolerance in feet
    :return: bool - True if the endpoint is within the tolerance of the point, False otherwise
    """
    return get_point_distance(endpoint, point_geom) <= tolerance


def snap_endpoint_to_point(line_feature, endpoint_index, new_point: Point):
    """
    Modify the endpoint (start or end) of a line geometry.
    :param line_feature: Feature object - the line feature to modify
    :param endpoint_index: int - 0 for start, 1 for end
    :param new_point: Point - the new location for the endpoint
    """
    path = line_feature.geometry['paths'][0]
    if endpoint_index == 0:
        path[0][0] = new_point.x
        path[0][1] = new_point.y
    else:
        path[-1][0] = new_point.x
        path[-1][1] = new_point.y
    line_feature.geometry = {"paths": [path], "spatialReference": line_feature.geometry['spatialReference']}


def process_buffer(buffer_feature, point_feature, line_layer):
    """
    For a single buffer:
    - Get intersecting lines
    - For each line, get endpoints
    - If endpoint is inside the buffer and not snapped, add the updated line feature to the list of updated lines.
    :param buffer_feature: Feature object - the buffer feature to process
    :param point_feature: Feature object - the point feature to snap to
    :param line_layer: FeatureLayer - the layer containing utility lines
    :return: list of updated line features
    """
    buffer_geom = buffer_feature.geometry
    point_geom = point_feature.geometry
    updated_lines = []

    print(f"Processing buffer around point {point_feature.attributes.get('FACILITYID')} with geometry: {buffer_geom}")

    query_filter = intersects(buffer_geom)
    # Spatial filter to get only intersecting lines
    intersecting_lines = line_layer.query(geometry_filter=query_filter,
                                          #spatial_relationship='intersects',
                                          return_geometry=True,
                                          out_fields="*").features

    for line in intersecting_lines:
        endpoints = get_endpoints(line.geometry)
        print(f"Processing line {line.attributes.get('FACILITYID')} with endpoints: {endpoints}")
        for i, ep in enumerate(endpoints):
            # per docs, contains() from arcgis.geometry requires arcpy or Shapely
            #if contains(buffer_geom, ep) and not is_snapped(ep, point_geom):
            # can a single point be queried or should it be a layer? no TODO - make a layer from the point - ughh
            intersecting_point = ep.query(geometry_filter=query_filter).features
            if not intersecting_point:
                print(f"Endpoint {i} of line {line.attributes.get('FACILITYID')} is not within buffer.")
            else:
                print(f"Endpoint {i} of line {line.attributes.get('FACILITYID')} is within buffer.")
            if within(ep, buffer_geom):
                print(f"Endpoint {i} of line {line.attributes.get('FACILITYID')} is within buffer.")
            if within(ep, buffer_geom) and not is_snapped(ep, point_geom):
                snap_endpoint_to_point(line, i, point_geom)
                updated_lines.append(line)
                print(f"Updated endpoint {i} of line {line.attributes.get('OBJECTID')} (snap not yet applied).")

    return updated_lines


def main():
    updated = []
    gis = GIS(GIS_LOGIN)
    line_layer = FeatureLayer(LINE_URL)
    point_layer = FeatureLayer(POINT_URL)

    #buffer_feature_set = get_buffer_feature_set(gis, item_title='Test_buffer_around_subset_d_points', point_layer=point_layer, buffer_distance=SNAP_TOLERANCE_FEET)
    buffer_feature_layer = get_buffer_feature_set(gis, item_title='Test_buffer_around_subset_d_points', point_layer=point_layer, buffer_distance=SNAP_TOLERANCE_FEET)
    #print(f"Buffer feature set contains {len(buffer_feature_set.features)} features.")
    #print(f"Sample buffer feature: {buffer_feature_set.features[0].as_dict()}")

    #for buffer_feature in buffer_feature_set.features:
    for buffer_feature in buffer_feature_layer.features:
        point_oid = buffer_feature.attributes.get('FACILITYID')
        print(f"Found buffer feature for point OID: {point_oid}")
        if point_oid is None:
            continue

        point = point_layer.query(where=f"FACILITYID = '{point_oid}'", return_geometry=True).features
        if not point:
            continue

        updated_lines = process_buffer(buffer_feature, point[0], line_layer)
        updated.extend(updated_lines)

    if updated:
        print(f"Updating {len(updated)} modified lines...")
        # Uncomment the following line to apply updates to the line layer
        #result = line_layer.edit_features(updates=updated)
        #print("Edit result:", result)
    else:
        print("No lines needed snapping.")


# *********************************** OLD FUNCTIONS ***********************************
# TODO - remove this function if not used
def get_endpoints_old(polyline_feature):
    """
    Return start and end Point objects from a polyline geometry dict.
    :param polyline_feature - tuple containing a single Feature object: the polyline feature from which endpoints will be extracted
    :return: tuple of Point objects: first point (start), second point (end)
    """
    feature_dict = polyline_feature[0].as_dict
    paths = feature_dict['geometry']['paths']
    print(f"Paths: {paths}\n")
    #p1 = Point({"x": paths[0][0], "y": paths[0][1], "spatialReference": feature_dict['geometry']['spatialReference']})
    #p2 = Point({"x": paths[-1][0], "y": paths[-1][1], "spatialReference": feature_dict['geometry']['spatialReference']})

    p1 = Point({"x": paths[0][0][0], "y": paths[0][0][1], "spatialReference": feature_dict['geometry']['spatialReference']})
    p2 = Point({"x": paths[0][1][0], "y": paths[0][1][1], "spatialReference": feature_dict['geometry']['spatialReference']})
    #p1 = Point()
    print(f'Endpoints:\np1: {p1},\np2: {p2}\n\n')
    return p1, p2


# TODO - remove this function if not used
def get_point_distance_old(p1, p2):
    """
    Euclidean distance between two arcgis Point objects.
    Only works if both inputs are Points; otherwise returns None.
    :param p1 - Point object: first point
    :param p2 - Point object: second point
    :return: float: distance in feet, or None if inputs are not Points
    """
    if isinstance(p1, Point) and isinstance(p2, Point):
        return math.hypot(p1.x - p2.x, p1.y - p2.y)
    else:
        print(f"get_point_distance error: invalid types\n  p1: {type(p1)}, p2: {type(p2)}")
        return None


def find_nearest_point(target_pt, candidate_pts, tolerance):
    """
    Return the candidate point nearest the target point within the specified tolerance.
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


def snap_line_endpoints(line_feature, utility_point, line_endpoints, tolerance):
    """
    Snap endpoints of a line feature to the nearest point within a specified tolerance.
    :param line_feature - Feature object: the line to be snapped (WGS84)
    *********:param point_pool - list of Point objects: list of points (projected)
    :param utility_point - Point object: point to which line endpoint will be snapped (projected)
    :param line_endpoints: list of Point objects (projected)
    :param tolerance: float (feet)
    :return: updated Feature or None
    """
    modified = False
    geom = line_feature.geometry
    paths = geom['paths'][0]

    # TODO - use variables below if indexes are correct
    p1x = paths[0][0]
    p1y = paths[0][1]
    p2x = paths[1][0]
    p2y = paths[1][1]

    start_pt = Point({"x": paths[0][0], "y": paths[0][1], "spatialReference": geom['spatialReference']})
    #end_pt = Point({"x": paths[-1][0], "y": paths[-1][1], "spatialReference": geom['spatialReference']})
    end_pt = Point({"x": paths[1][0], "y": paths[1][1], "spatialReference": geom['spatialReference']})

    print(f'start_pt: {start_pt}, end_pt: {end_pt}')
    proj_start = project(start_pt, SR_WGS84, SR_PROJECTED)
    proj_end = project(end_pt, SR_WGS84, SR_PROJECTED)

    #return
    nearest = find_nearest_point(utility_point, line_endpoints, tolerance)
    ## this seems to be redundant as line endpoints projected above are compared to the (projected) line endpoints passed to the function
    #for i, pt in enumerate([proj_start, proj_end]):
    #    print(f'sample point {i}: {pt}')
    #    #print(f'point_pool: {point_pool}')
    #    # do not try to find the nearest point in the pool to 'pt'
    #    #nearest = find_nearest_point(pt, point_pool, tolerance)
    #    #return
    #    #if not nearest:
    #    nearest = find_nearest_point(pt, line_endpoints, tolerance)

    if nearest:
        print(f"Nearest point found near utility point {utility_point} for {line_feature.attributes.get('FACILITYID', 'UNKNOWN')}: {nearest}")
        #if i == 0:
        #    paths[0][0] = nearest.x
        #    paths[0][1] = nearest.y
        #else:
        #    #paths[-1][0] = nearest.x
        #    #paths[-1][1] = nearest.y
        #    paths[1][0] = nearest.x
        #    paths[1][1] = nearest.y
        modified = True
    else:
        print(f"No snap found for line {line_feature.attributes.get('FACILITYID', 'UNKNOWN')}")

    if modified:
        new_geom = {
            "paths": [paths],
            "spatialReference": geom['spatialReference']
        }
        updated_geom = project(new_geom, SR_PROJECTED, SR_WGS84)
        print(f"Updated geometry for line {line_feature.attributes.get('FACILITYID', 'UNKNOWN')}: {updated_geom}")
        line_feature.geometry = updated_geom
        return line_feature
    else:
        return None


def fix_dangles(lines, points):
    """
    Projects geometries, snaps endpoints, and returns list of modified line features.
    """
    updated = []

    projected_points = [project(pt.geometry, SR_WGS84, SR_PROJECTED) for pt in points]
    projected_lines = [(ln, project(ln.geometry, SR_WGS84, SR_PROJECTED)) for ln in lines]
    print(f"Projected {len(projected_points)} points and {len(projected_lines)} lines to EPSG:2276.")

    # hold Point objects of all line endpoints as snapping candidates
    all_line_endpoints = []
    for proj_geom in projected_lines:
        start, end = get_endpoints(proj_geom)
        print(f'start: {start}, end: {end}')
        all_line_endpoints.extend([start, end])
        #all_line_endpoints.extend([start, end])
        #all_line_endpoints.append(start['x'])
        #all_line_endpoints.append(start['y'])
        #if start and end:
        #    print(f"all_line_endpoints: {all_line_endpoints}")
        #    return
    print(f"Total endpoints collected: {len(all_line_endpoints)}")
    print(f"all_line_endpoints: {all_line_endpoints}")
    #return
    for original_line, _ in projected_lines:
        for point in projected_points:
            #modified_feature = snap_line_endpoints(original_line, projected_points, all_line_endpoints, SNAP_TOLERANCE_FEET)
            modified_feature = snap_line_endpoints(original_line, point, all_line_endpoints, SNAP_TOLERANCE_FEET)
            if modified_feature:
                updated.append(modified_feature)
                #print(f"Line {original_line.attributes.get('FACILITYID', 'UNKNOWN')} modified.")
                print(f"Line {original_line.attributes.get('FACILITYID', 'UNKNOWN')} added to list of updates.")

    return updated



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
    # TODO - call snap_line_endpoints() with sample params
    snap_line_endpoints(lines[0], points[0], [Point({"x": 0, "y": 0, "spatialReference": SR_WGS84})], SNAP_TOLERANCE_FEET)
    return
    # TODO - uncomment after all calls to this point are working as expected
    #print("Fixing dangles...")
    #updated_features = fix_dangles(lines, points)

    # TODO - Uncomment the following lines to enable editing of features in the feature service.
    #if updated_features:
    #    print(f"{len(updated_features)} lines modified. Uploading...")
    #    result = line_layer.edit_features(updates=updated_features)
    #    print("Edit result:", result)
    #else:
    #    print("No features needed editing.")

if __name__ == "__main__":
    main()
