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
    """
    Extracts start and end Points from a line geometry.
    :param line_geom: dict - the geometry of the line feature
    :return: list of Point objects - start and end points of the line
    """
    path = line_geom['paths'][0]
    sr = line_geom['spatialReference']
    return [
        Point({"x": path[0][0], "y": path[0][1], "spatialReference": sr}),
        Point({"x": path[-1][0], "y": path[-1][1], "spatialReference": sr})
    ]


def get_point_distance(p1: Point, p2: Point) -> float:
    """
    Return the Euclidean distance between two Points.
    :param p1: Point - first point
    :param p2: Point - second point
    :return: float - the distance between the two points
    """
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def is_snapped(endpoint: Point, target_point: Point, tolerance: float = 0.000001) -> bool:
    """
    Check whether an endpoint is already snapped to the point.
    :param endpoint: Point - the endpoint to check
    :param target_point: Point - the target point to check against
    :param tolerance: float - the snapping tolerance in feet
    :return: bool - True if the endpoint is within the tolerance of the point, False otherwise
    """
    distance = get_point_distance(endpoint, target_point)
    snapped = distance <= tolerance
    #print(f"Endpoint {endpoint} is {'snapped' if snapped else 'not snapped'} to target point {target_point} with gap distance {distance} feet.")
    print(f"Endpoint is {'snapped' if snapped else 'not snapped'} to target point with gap distance of {distance} feet.")
    return snapped


def snap_endpoint_to_point(line_feature, endpoint_index, new_point: Point):
    """
    Modify the endpoint (start or end) of a line geometry.
    :param line_feature: Feature object - the line feature to modify
    :param endpoint_index: int - 0 for start, 1 for end
    :param new_point: Point - the new location for the endpoint
    :return: Feature object - the modified line feature with updated endpoint
    """
    path = line_feature.geometry['paths'][0]
    if endpoint_index == 0:
        path[0][0] = new_point.x
        path[0][1] = new_point.y
    else:
        path[-1][0] = new_point.x
        path[-1][1] = new_point.y
    line_feature.geometry = {"paths": [path], "spatialReference": line_feature.geometry['spatialReference']}
    return line_feature


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
    target_point = Point({"x": point_geom['x'], "y": point_geom['y'], "spatialReference": point_geom['spatialReference']})
    updated_lines = []

    print(f"Processing buffer around point {point_feature.attributes.get('FACILITYID')} with buffer geometry: {buffer_geom}")

    query_filter = intersects(buffer_geom)
    # Spatial filter to get only intersecting lines
    intersecting_lines = line_layer.query(geometry_filter=query_filter,
                                          #spatial_relationship='intersects',
                                          return_geometry=True,
                                          out_fields="*").features

    for line in intersecting_lines:
        endpoints = get_endpoints(line.geometry)
        print(f"\nProcessing line {line.attributes.get('FACILITYID')} with endpoints: {endpoints}")

        #ep1 = endpoints[0]
        #ep2 = endpoints[1]
        ## TODO - modify snap_endpoint_to_point to return just the corrected point? then construct the line feature from one or both of the edited endpoints?
        #if within(ep1, buffer_geom) and not is_snapped(ep1, target_point, 0.0001):
        #    line = snap_endpoint_to_point(line, 0, target_point)

        for i, ep in enumerate(endpoints):

            #print(f'sample endpoint {i}: {ep}')
            #print(f'buffer_geom: {buffer_geom}')
            #if within(ep, buffer_geom):
            #    print(f"Endpoint {i} of line {line.attributes.get('FACILITYID')} is within buffer.")
            #else:
            #    print(f"Endpoint {i} of line {line.attributes.get('FACILITYID')} is NOT within buffer.")
            #    continue

            # first make a feature from the Point object? or return Feature object from get_endpoints()?

            #print(f'intersection test: {ep.geometry.intersection(buffer_geom)}')
            if within(ep, buffer_geom) and not is_snapped(ep, target_point, 0.0001):
                snap_endpoint_to_point(line, i, target_point)
                # TODO - before appending, second endpoint should be checked if it hasn't already
                #if i == 0:
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
        print(f"\n*********\nFound buffer feature for point OID: {point_oid}")
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


if __name__ == "__main__":
    main()
