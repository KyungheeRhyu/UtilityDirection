import os
from collections import Counter
import datetime as dt
import arcpy
from shared import set_environment

'''
Assign values to a new field in a utility point layer based on attributes of connected utility line segments. (Will first be used to assign owner values from connected segments to points.)

First, ensure that:
- the field(s) holding values to be assigned to the point layer have been populated in the utility line layer.
- topology errors have been fixed in the both layers (unless using a reliable tolerance for selecting lines that should be connected).

1. Add field(s) to the utility point layer e.g. connected_line_owner_values (which will hold all values in the 'owner' field of the connected segments in the utility line layer).
2. Use an update cursor to iterate over features in point layer and for each point:
    a. select intersecting lines (possibly within a specified tolerance e.g. 0.2 feet).
    b. get and concatenate all values from the specified field(s) in the selected lines.
    c. write the concatenated values to the point feature's new field(s).

'''