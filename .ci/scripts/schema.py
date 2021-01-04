import json
from drf_spectacular.validation import JSON_SCHEMA_SPEC_PATH

with open(JSON_SCHEMA_SPEC_PATH) as fh:
    openapi3_schema_spec = json.load(fh)

properties = openapi3_schema_spec["definitions"]["Paths"]["patternProperties"]
# Making OpenAPI validation to accept paths starting with / and {
if "^\\/|{" not in properties:
    properties["^\\/|{"] = properties["^\\/"]
    del properties["^\\/"]

with open(JSON_SCHEMA_SPEC_PATH, "w") as fh:
    json.dump(openapi3_schema_spec, fh)
