import os
import sys
from enum import StrEnum
from http import HTTPStatus
import requests

# key API global variables
PERSONAL_ACCESS_TOKEN = os.getenv("PERSONAL_ACCESS_TOKEN")
JIRA_BASE_URL = "http://localhost:8080"
CUSTOM_FIELDS_ENDPOINT = f"{JIRA_BASE_URL}/rest/api/2/field"
PROJECTS_ENDPOINT = f"{JIRA_BASE_URL}/rest/api/2/project"
SEARCH_ENDPOINT = f"{JIRA_BASE_URL}/rest/api/2/search"

# HTTP headers
AUTHORIZATION_HEADER = "Authorization"
BEARER_TOKEN_PREFIX = "Bearer"
CONTENT_TYPE_HEADER = "Content-Type"
CONTENT_TYPE_JSON = "application/json"
HEADERS = {
    AUTHORIZATION_HEADER: f"{BEARER_TOKEN_PREFIX} {PERSONAL_ACCESS_TOKEN}",
    CONTENT_TYPE_HEADER: CONTENT_TYPE_JSON,
}

# console error messages
ERROR_MSG_ENV_VARIABLE = "Error: PERSONAL_ACCESS_TOKEN environment variable is not set."
ERROR_MSG_FETCH_FIELDS = "Failed to retrieve fields. Status Code: {status_code}"
ERROR_MSG_FETCH_PROJECTS = "Failed to retrieve projects. Status Code: {status_code}"
ERROR_MSG_QUERY_ISSUES = "Error querying issues for {clause_name} in {project_info}. Status Code: {status_code}"
ERROR_MSG_UNSUPPORTED_FIELD_TYPE = "Unsupported field type '{field_type}'. Skipping..."
ERROR_MSG_RESPONSE_TEXT = "Response: {response_text}"
LOG_FETCH_FIELDS = "Fetching custom fields..."
WARNING_BAD_REQUEST = (f"Got error {HTTPStatus.BAD_REQUEST} BAD_REQUEST for 'any' field type with 'IS NOT EMPTY', "
                       f"retrying with > 0'")

class JsonFieldNames(StrEnum):
    """
    A class representing enumeration of JSON field names.
    """
    ANY = "any"
    ARRAY = "array"
    CLAUSE_NAMES = "clauseNames"
    CUSTOM = "custom"
    DATE = "date"
    ID = "id"
    JQL = "jql"
    KEY = "key"
    NAME = "name"
    NUMBER = "number"
    OPTION = "option"
    PROJECT_KEY = "project_key"
    PROJECT_NAME = "project_name"
    SCHEMA = "schema"
    STRING = "string"
    TOTAL = "total"
    TYPE = "type"
    UNKNOWN = "unknown"
    USAGE = "usage"

# additional global variables
ALL_PROJECTS = "all projects"
COMMITS_FIELD = "[commits]"
DEVELOPMENT_FIELD = "cf[10000]"
FIELDS = "fields"
FILE_APPEND_MODE = "a"
FILE_WRITE_MODE = "w"
GREATER_THAN_ZERO_CLAUSE = "> 0"
IS_NOT_EMPTY_CLAUSE = "IS NOT EMPTY"
MAX_RESULTS = "maxResults"
PROJECT = "project"
PROJECT_CONDITION_TEMPLATE = 'project = "{project_key}" AND '
START_AT = "startAt"
START_AT_VALUE = 0
SUPPORTED_FIELD_TYPES = [JsonFieldNames.NUMBER, JsonFieldNames.ANY, JsonFieldNames.STRING, JsonFieldNames.ARRAY,
                         JsonFieldNames.DATE, JsonFieldNames.OPTION]

# requires access token from environment variable
if not PERSONAL_ACCESS_TOKEN:
    print(ERROR_MSG_ENV_VARIABLE)
    sys.exit(1)


def fetch_custom_fields():
    """
    Fetch all custom fields from the Jira API.
    :return: List of custom fields (as dictionaries), sorted by 'id'.
    """
    response = requests.get(CUSTOM_FIELDS_ENDPOINT, headers=HEADERS)

    if response.status_code != HTTPStatus.OK:
        print(ERROR_MSG_FETCH_FIELDS.format(status_code=response.status_code))
        print(ERROR_MSG_RESPONSE_TEXT.format(response_text=response.text))
        sys.exit(1)

    fields = response.json()
    custom_fields = [field for field in fields if field.get(JsonFieldNames.CUSTOM)]
    return sorted(custom_fields, key=lambda field: field[JsonFieldNames.ID])


def fetch_projects():
    """
    Fetch all projects in the Jira instance.
    :return: List of projects with their keys and names.
    """
    response = requests.get(PROJECTS_ENDPOINT, headers=HEADERS)

    if response.status_code != HTTPStatus.OK:
        print(ERROR_MSG_FETCH_PROJECTS.format(status_code=response.status_code))
        print(ERROR_MSG_RESPONSE_TEXT.format(response_text=response.text))
        sys.exit(1)

    return response.json()


def query_issues_using_field(clause_name, field_type, project_key=None):
    """
    Query the number of issues using a specific custom field in a specific project (if project_key gets provided).
    If no project_key gets provided, query usage across all projects.
    :param clause_name: The JQL-friendly `cf[...]` clause name of the custom field.
    :param field_type: Schema type of the custom field to determine the JQL condition.
    :param project_key: (Optional) The project key to scope the query.
    :return: Number of issues using the field.
    """
    # determine the project-specific or global JQL condition
    project_condition = PROJECT_CONDITION_TEMPLATE.format(project_key=project_key) if project_key else ""

    # formulate JQL based on field type
    if clause_name == DEVELOPMENT_FIELD:
        jql_condition = f"{project_condition}{clause_name}{COMMITS_FIELD}.all {IS_NOT_EMPTY_CLAUSE}"
    elif field_type in [JsonFieldNames.NUMBER]:
        jql_condition = f"{project_condition}{clause_name} {GREATER_THAN_ZERO_CLAUSE}"
    elif field_type in SUPPORTED_FIELD_TYPES:
        jql_condition = f"{project_condition}{clause_name} {IS_NOT_EMPTY_CLAUSE}"
    else:
        print(ERROR_MSG_UNSUPPORTED_FIELD_TYPE.format(field_type=field_type))
        return 0

    # query issues
    payload = {JsonFieldNames.JQL: jql_condition, START_AT: 0, MAX_RESULTS: 0, FIELDS: []}
    response = requests.post(SEARCH_ENDPOINT, headers=HEADERS, json=payload)

    if response.status_code == HTTPStatus.BAD_REQUEST and field_type == JsonFieldNames.ANY:
        print(WARNING_BAD_REQUEST)
        jql_condition = f"{project_condition}{clause_name} {GREATER_THAN_ZERO_CLAUSE}"
        payload[JsonFieldNames.JQL] = jql_condition
        response = requests.post(SEARCH_ENDPOINT, headers=HEADERS, json=payload)

    if response.status_code != HTTPStatus.OK:
        project_info = f"{PROJECT} {project_key}" if project_key else ALL_PROJECTS
        print(ERROR_MSG_QUERY_ISSUES.format(clause_name=clause_name, project_info=project_info,
                                            status_code=response.status_code))
        print(ERROR_MSG_RESPONSE_TEXT.format(response_text=response.text))
        return 0

    # return the total count of issues
    return response.json().get(JsonFieldNames.TOTAL, 0)
