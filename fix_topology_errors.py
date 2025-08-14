from arcgis.gis import GIS
from arcgis.features import FeatureLayer, Feature, FeatureSet, use_proximity
from arcgis.geometry import Point, SpatialReference, project #within cannot be imported
#within cannot be imported from arcgis.geometry.functions
#from arcgis.geometry.functions import within
#from arcgis.geometry.filters import contains, within
from arcgis.geometry.filters import intersects, within, contains
import math
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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

# TODO - remove these constants if not necessary
BUFFER_WIDTH_FEET = 0.3
SNAP_TOLERANCE_FEET = 0.000001


def get_buffer_feature_layer(gis, item_title=None, point_layer=None, buffer_distance=None):
    """
    Return a FeatureLayer of buffered features from the specified item in ArcGIS Online or a new buffer created from the given point layer.
    :param gis: GIS object - the GIS connection to use
    :param item_title: str or None - title of the existing item to fetch, if None, item will be created
    :param point_layer: FeatureLayer or None - if provided, will use this layer to create buffers
    :param buffer_distance: float or None - distance in feet to create buffers, can be None if using an existing item
    :return: FeatureLayer or None if item not found
    """
    search_results = gis.content.search(item_title, item_type="Feature Service", max_items=1)
    logging.info(f"Found {len(search_results)} search results for item title: {item_title}")
    if search_results:
        # query() returns a FeatureSet
        #buffer_feature_set = search_results[0].layers[0].query(where="1=1", return_geometry=True)
        buffer_feature_layer = search_results[0].layers[0]
    else:
        # create_buffers() returns a FeatureLayer
        buffer_feature_layer = use_proximity.create_buffers(point_layer, distances=[buffer_distance], units="Feet", output_name=item_title)
    buffer_feature_set = buffer_feature_layer.query(where="1=1", return_geometry=False)
    logging.info(f"Buffer feature layer contains {len(buffer_feature_set.features)} features.")
    # TODO - clean this up if feature layer works as expected
    #buffer_feature_set = FeatureSet.from_dict({buffer_feature_layer})
    #return buffer_feature_set
    logging.debug(f"type of buffer_feature_layer: {type(buffer_feature_layer)}")
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


def get_nearest_point(point: Point, point_list: list) -> Point:
    """
    Find the nearest point in the point layer to the given point.
    :param point: Point - the point to find the nearest neighbor for
    :param point_list: list of Point objects - the list containing candidate points
    :return: Point - the nearest point found, or None if no points are in the layer
    """
    nearest_point = None
    min_distance = float("inf")
    for candidate in point_list:
        logging.debug(f'type of candidate from point list: {type(candidate)}')
        #distance = get_point_distance(point, candidate.geometry)
        distance = get_point_distance(point, candidate)
        if distance < min_distance:
            min_distance = distance
            #nearest_point = candidate.geometry
            nearest_point = candidate
    return nearest_point


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
    #logging.info(f"Endpoint {endpoint} is {'snapped' if snapped else 'not snapped'} to target point {target_point} with gap distance {distance} feet.")
    logging.info(f"Endpoint is {'snapped' if snapped else 'not snapped'} to target point with gap distance of {distance} feet.")
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


def get_intersecting_buffer_features(line_feature, buffer_layer):
    """
    Get buffer feature(s) that intersect with the given line feature (should return between 0 and 2 buffer features if buffer around each point is < 1 foot).
    :param line_feature: Feature object - the line feature to check against
    :param buffer_layer: FeatureLayer - the layer containing buffer features
    :return: list of intersecting buffer features
    """
    line_geom = line_feature.geometry
    #for buffer_feature in buffer_feature_set.features:
    #buffer_geom = buffer_feature.geometry
    query_filter = intersects(line_geom)
    intersecting_buffers = buffer_layer.query(geometry_filter=query_filter,
                                          return_geometry=True,
                                          out_fields="*").features
    logging.info(f"Found {len(intersecting_buffers)} buffer feature(s) intersecting line {line_feature.attributes.get('FACILITYID')}.")
    return intersecting_buffers


def get_points_in_buffer(point_layer, buffer_feature):
    """
    Return the point(s) from the given point layer that fall within the given buffer feature.
    :param point_layer: FeatureLayer object - the point layer containing points that may be within the given buffer
    :param buffer_feature: Feature object - the buffer feature to check against
    :return: list of points within the buffer
    """
    buffer_geom = buffer_feature.geometry
    # using within(), script does not throw an error but returns empty list
    #query_filter = within(buffer_geom)
    query_filter = intersects(buffer_geom)
    features = point_layer.query(geometry_filter=query_filter,
                              return_geometry=True,
                              out_fields="*").features
    # convert features to Points
    return [Point({"x": f.geometry['x'], "y": f.geometry['y'], "spatialReference": f.geometry['spatialReference']}) for f in features]


def process_endpoint(line_feature: Feature, endpoint: Point, endpoint_index: int, buffer_features, point_layer):
    """
    For a single endpoint:
    - Check if endpoint is within any of the given buffer features
    - If so, get points within that buffer and snap to nearest point if not already snapped
    :param line_feature: Feature object - the line feature being processed
    :param endpoint: Point object - the endpoint to process
    :param endpoint_index: int - 0 for start, 1 for end
    :param buffer_features: list of Feature objects - the buffer features to check against
    :param point_layer: FeatureLayer object - the layer containing point features
    :return: tuple (bool, Feature object (line)) - boolean indicating if endpoint of line was updated, and the line feature which may or may not be updated
    """
    updated = False
    ep_in_question = None
    target_points = []
    for buffer_feature in buffer_features:
        if within(endpoint, buffer_feature.geometry):
            ep_in_question = endpoint
            target_points = get_points_in_buffer(point_layer, buffer_feature)
    if ep_in_question and target_points:
        # Snap the endpoint to the nearest target point
        nearest_point = get_nearest_point(ep_in_question, target_points)
        if nearest_point and not is_snapped(ep_in_question, nearest_point, SNAP_TOLERANCE_FEET):
            logging.info(f"Endpoint {ep_in_question} will be snapped to nearest point {nearest_point}.")
            updated_line_feature = snap_endpoint_to_point(line_feature, endpoint_index, nearest_point)
            logging.info(f"Snapped endpoint {endpoint_index} of line {line_feature.attributes.get('FACILITYID')} to point {nearest_point}.")
            updated = True
            return (updated, updated_line_feature)
        else:
            logging.info(f"Endpoint {ep_in_question} is already snapped to nearest point {nearest_point}.")
    return (updated, line_feature)


def process_line(line_feature, buffer_layer, point_layer):
    """
    For a single line:
    - Get endpoints
    - For each endpoint, if endpoint is not snapped to a point within ______ (that point's buffer), snap it to that point
    :param line_feature: Feature object - the line feature to process
    :param buffer_layer: FeatureLayer object - the layer containing buffer features
    :param point_layer: FeatureLayer object - the layer containing point features
    :return: tuple (bool, Feature object (line)) - boolean indicating if line was updated, and the line feature which may or may not be updated
    """
    endpoints = get_endpoints(line_feature.geometry)
    #point_geom = point_feature.geometry
    #target_point = Point({"x": point_geom['x'], "y": point_geom['y'], "spatialReference": point_geom['spatialReference']})
    #updated = False
    buffer_features = get_intersecting_buffer_features(line_feature, buffer_layer)

    # TODO - build function from logic for a single endpoint if it works - then feed updated line feature to function to check (and possibly modify) second endpoint
    ep1, ep2 = endpoints[0], endpoints[1]
    ep1_updated, processed_line_feature = process_endpoint(line_feature, ep1, 0, buffer_features, point_layer)
    if ep1_updated:
        ep2_updated, final_line_feature = process_endpoint(processed_line_feature, ep2, 1, buffer_features, point_layer)
    else:
        ep2_updated, final_line_feature = process_endpoint(line_feature, ep2, 1, buffer_features, point_layer)
    #logging.debug(f'type of endpoint 1: {type(ep1)}')
    #buffer_features = get_intersecting_buffer_features(line_feature, buffer_layer)
    #ep_in_question = None
    #target_points = []
    #for buffer_feature in buffer_features:
    #    if within(ep1, buffer_feature.geometry):
    #        ep_in_question = ep1
    #        target_points = get_points_in_buffer(point_layer, buffer_feature)
    ##if ep_in_question:
    #if target_points:
    #    # Snap the endpoint to the nearest target point
    #    nearest_point = get_nearest_point(ep_in_question, target_points)
    #    if nearest_point and not is_snapped(ep_in_question, nearest_point, SNAP_TOLERANCE_FEET):
    #        line_feature = snap_endpoint_to_point(line_feature, 0, nearest_point)
    #        updated = True
    #        logging.info(f"Snapped endpoint 0 of line {line_feature.attributes.get('FACILITYID')} to point {nearest_point}. Endpoint 1 NOT YET CHECKED")
    #else:
    #    logging.info(f"No target points found for endpoint 0 of line {line_feature.attributes.get('FACILITYID')}.")

    #for buffer_feature in buffer_features:
    #    points_in_buffer = get_points_in_buffer(point_layer, buffer_feature)
    #    logging.info(f"Found {len(points_in_buffer)} points in buffer {buffer_feature.attributes.get('FACILITYID')}.")
    #    target_points.extend(points_in_buffer)

    # TODO - get target points nearest to endpoints
    
    #for ep in endpoints:
    #    nearest_point = find_nearest_point(ep, point_feature)
    #    if nearest_point:
    #        target_points.append(nearest_point)

    #for i, ep in enumerate(endpoints):
    #    if is_snapped(ep, target_point, SNAP_TOLERANCE_FEET):
    #        line_feature = snap_endpoint_to_point(line_feature, i, target_point)
    #        updated = True
    #        logging.info(f"Snapped endpoint {i} of line {line_feature.attributes.get('FACILITYID')} to point {point_feature.attributes.get('FACILITYID')}.")

    if ep1_updated or ep2_updated:
        logging.info(f"Updated at least one endpoint of line {final_line_feature.attributes.get('FACILITYID')} with new geometry.")
        return True, final_line_feature
    else:
        logging.info(f"No updates made to line {line_feature.attributes.get('FACILITYID')}.")
        return False, line_feature


# TODO - remove this function if not used
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

    logging.info(f"Processing buffer around point {point_feature.attributes.get('FACILITYID')} with buffer geometry: {buffer_geom}")

    query_filter = intersects(buffer_geom)
    # Spatial filter to get only intersecting lines
    intersecting_lines = line_layer.query(geometry_filter=query_filter,
                                          #spatial_relationship='intersects',
                                          return_geometry=True,
                                          out_fields="*").features

    for line in intersecting_lines:
        endpoints = get_endpoints(line.geometry)
        logging.info(f"\nProcessing line {line.attributes.get('FACILITYID')} with endpoints: {endpoints}")

        #ep1 = endpoints[0]
        #ep2 = endpoints[1]
        ## TODO - modify snap_endpoint_to_point to return just the corrected point? then construct the line feature from one or both of the edited endpoints?
        #if within(ep1, buffer_geom) and not is_snapped(ep1, target_point, 0.0001):
        #    line = snap_endpoint_to_point(line, 0, target_point)

        for i, ep in enumerate(endpoints):

            #logging.info(f'sample endpoint {i}: {ep}')
            #logging.info(f'buffer_geom: {buffer_geom}')
            #if within(ep, buffer_geom):
            #    logging.info(f"Endpoint {i} of line {line.attributes.get('FACILITYID')} is within buffer.")
            #else:
            #    logging.info(f"Endpoint {i} of line {line.attributes.get('FACILITYID')} is NOT within buffer.")
            #    continue

            # first make a feature from the Point object? or return Feature object from get_endpoints()?

            #logging.info(f'intersection test: {ep.geometry.intersection(buffer_geom)}')
            if within(ep, buffer_geom) and not is_snapped(ep, target_point, 0.0001):
                snap_endpoint_to_point(line, i, target_point)
                # TODO - before appending, second endpoint should be checked if it hasn't already
                #if i == 0:
                updated_lines.append(line)
                logging.info(f"Updated endpoint {i} of line {line.attributes.get('OBJECTID')} (snap not yet applied).")

    return updated_lines


def main():
    updated = []
    gis = GIS(GIS_LOGIN)
    line_layer = FeatureLayer(LINE_URL)
    point_layer = FeatureLayer(POINT_URL)

    #buffer_feature_set = get_buffer_feature_layer(gis, item_title='Test_buffer_around_subset_d_points', point_layer=point_layer, buffer_distance=SNAP_TOLERANCE_FEET)
    buffer_feature_layer = get_buffer_feature_layer(gis, item_title='Test_buffer_around_subset_d_points', point_layer=point_layer, buffer_distance=BUFFER_WIDTH_FEET)
    #logging.info(f"Buffer feature set contains {len(buffer_feature_set.features)} features.")
    #logging.info(f"Sample buffer feature: {buffer_feature_set.features[0].as_dict()}")
    result_lines = []
    updated_count = 0

    line_feature_set = line_layer.query(return_geometry=True)

    for line_feature in line_feature_set.features:
        logging.info(f"Processing line feature: {line_feature.attributes.get('FACILITYID')}")
        line_updated = False
        line_updated, processed_line = process_line(line_feature, buffer_feature_layer, point_layer)
        if line_updated:
            updated_count += 1
            result_lines.append(processed_line)
        else:
            result_lines.append(line_feature)

    logging.info(f"Total updated lines to apply: {updated_count}")

    #for buffer_feature in buffer_feature_set.features:
    #for buffer_feature in buffer_feature_layer.features:
    #    point_oid = buffer_feature.attributes.get('FACILITYID')
    #    logging.info(f"\n*********\nFound buffer feature for point OID: {point_oid}")
    #    if point_oid is None:
    #        continue
    #    point = point_layer.query(where=f"FACILITYID = '{point_oid}'", return_geometry=True).features
    #    if not point:
    #        continue
    #    updated_lines = process_buffer(buffer_feature, point[0], line_layer)
    #    updated.extend(updated_lines)
    #if updated:
    #    logging.info(f"Updating {len(updated)} modified lines...")
    #    # Uncomment the following line to apply updates to the line layer
    #    #result = line_layer.edit_features(updates=updated)
    #    #logging.info("Edit result:", result)
    #else:
    #    logging.info("No lines needed snapping.")


if __name__ == "__main__":
    main()
