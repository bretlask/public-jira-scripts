#!../.venv/bin/python
import csv
from http import HTTPStatus
import requests
from utils.jira_utils import (FIELDS, FILE_APPEND_MODE, FILE_WRITE_MODE, IS_NOT_EMPTY_CLAUSE, MAX_RESULTS, START_AT,
                              START_AT_VALUE)
from utils.jira_utils import HEADERS, JIRA_BASE_URL, JsonFieldNames, SEARCH_ENDPOINT

# key global Variables
MULTI_SELECT_SOURCE = "10112"
MULTI_SELECT_DESTINATION = "10113"
UPDATE_ENDPOINT = f"{JIRA_BASE_URL}/rest/api/2/issue/"
SAVE_FILENAME = "3-after_current_multi_select_fields.csv"

# additional global variables
ALLOWED_VALUES = "allowedValues"
EDIT_META = "editmeta"
ALLOWED_VALUES_REQUEST = f"?expand={EDIT_META}&{FIELDS}="
CUSTOM_FIELD_JQL = "cf[{source}]"
CUSTOM_FIELD_JSON = "customfield_"
DESTINATION_VALUES = "destination_values"
ISSUES = "issues"
ISSUE_KEY = "issue_key"
ORDER = "order by ID"
PAGE_SIZE = 50
SOURCE_VALUES = "source_values"
VALUE = "value"

# console error and Log messages
ERROR_MSG_APPEND_LOAD = "Error appending backup file. Issue key: {issue_key} Error: {error}"
ERROR_MSG_FETCH_ISSUES = ("Error fetching issues with source field '{source_field}'. Status Code: {status_code}. "
                          "Response: {response}")
ERROR_MSG_FETCH_OPTIONS = "Error fetching options for field '{field_id}', status: {status_code}, response: {response}"
ERROR_MSG_FETCH_OPTIONS_SHORT = "Error fetching options for field '{field_id}': {error}"
LOG_SAVE_SUCCESS = "Successfully saved issue '{issue_key}'."
LOG_FETCH_ISSUES = "Fetching issues with source field '{field}'..."
LOG_OPTION_MAPPING_CREATED = "Dynamic option mapping created: {mapping}"
LOG_PAYLOAD_PREVIEW = "Updating issue '{issue_key}' with payload: {payload}"
LOG_SKIP_ISSUE = "Skipping issue '{issue_key}' because the destination values are already up-to-date."
LOG_SKIP_NO_VALID_VALUES = ("Skipping issue '{issue_key}' as no valid mappings were found for source value ids: {"
                            "value_ids}")
LOG_UPDATE_FAILURE = ("Failed to update issue '{issue_key}' for field '{field}'. Status Code: {status_code}. Response: "
                      "{response}")
LOG_UPDATE_SUCCESS = "Successfully updated issue '{issue_key}'."
LOG_UPDATE_INFO = "Updating issue '{issue_key}' with normalized destination values: {values}"
WARNING_NO_ISSUES_TO_FETCH_DESTINATION_FIELDS = ("Warning: No issues available to fetch destination field allowed "
                                                 "values.")
WARNING_NO_OPTIONS_FOUND = "Warning: No options found for field '{field}'"


def get_field_options_from_issues(field_id, issues):
    """
    Build options for a specific field from issue data.
    :param field_id: The custom field ID (for example, 10112 or 10113).
    :param issues: List of issues containing the populated field values.
    :return: A dictionary mapping the option values to option IDs.
    """
    options = {}
    field_json = f"{CUSTOM_FIELD_JSON}{field_id}"

    for issue in issues:
        # safely retrieve the field's values or default to an empty list
        field_values = issue.get(FIELDS, {}).get(field_json, [])

        # ensure field_values is an iterable list, otherwise skip if None or invalid
        if not isinstance(field_values, list):
            continue

        for option in field_values:
            # ensure option contains the required keys
            if JsonFieldNames.ID in option and VALUE in option:
                options[option[VALUE]] = option[JsonFieldNames.ID]

    return options


def get_allowed_values_for_field(issue_key, field_id):
    """
    Fetch the allowed values for a Jira custom field using UPDATE_ENDPOINT.
    :param issue_key: The key of the issue (for example, "SCRUM-1").
    :param field_id: The ID of the custom field (for example, MULTI_SELECT_DESTINATION).
    :return: A dictionary mapping option values to option IDs.
    """
    endpoint = f"{UPDATE_ENDPOINT}{issue_key}{ALLOWED_VALUES_REQUEST}{CUSTOM_FIELD_JSON}{field_id}"
    response = requests.get(endpoint, headers=HEADERS)

    if response.status_code != HTTPStatus.OK:
        print(
            ERROR_MSG_FETCH_OPTIONS.format(
                field_id=field_id, status_code=response.status_code, response=response.text
            )
        )
        return {}

    # extract allowed values from the API response
    try:
        allowed_values = (
            response.json()
            .get(EDIT_META, {})
            .get(FIELDS, {})
            .get(f"{CUSTOM_FIELD_JSON}{field_id}", {})
            .get(ALLOWED_VALUES, [])
        )
        return {option[VALUE]: option[JsonFieldNames.ID] for option in allowed_values}
    except Exception as error:
        print(
            ERROR_MSG_FETCH_OPTIONS_SHORT.format(
                field_id=field_id, error=str(error)
            )
        )
        return {}


def build_field_option_mapping(issues):
    """
    Build a dynamic mapping between source and destination field options based on shared values.
    Approach is from: https://confluence.atlassian.com/jirakb/how-to-retrieve-available-options-for-a-multi-select-customfield-via-jira-rest-api-815566715.html
    :return: A dictionary mapping the source option IDs to destination option IDs.
    """
    source_options = get_field_options_from_issues(MULTI_SELECT_SOURCE, issues)
    print(LOG_FETCH_ISSUES.format(field=f"{CUSTOM_FIELD_JSON}{MULTI_SELECT_DESTINATION}"))
    first_issue_key = issues[0][JsonFieldNames.KEY] if issues else None

    if first_issue_key:
        destination_options = get_allowed_values_for_field(first_issue_key, MULTI_SELECT_DESTINATION)
    else:
        destination_options = {}
        print(WARNING_NO_ISSUES_TO_FETCH_DESTINATION_FIELDS)

    if not source_options:
        print(f"{WARNING_NO_OPTIONS_FOUND.format(field=f'{CUSTOM_FIELD_JSON}{MULTI_SELECT_SOURCE}')}.")
    if not destination_options:
        print(f"{WARNING_NO_OPTIONS_FOUND.format(field=f'{CUSTOM_FIELD_JSON}{MULTI_SELECT_DESTINATION}')}.")

    # map source IDs to destination IDs based on matching values
    field_option_mapping = {
        source_id: destination_options[value]
        for value, source_id in source_options.items()
        if value in destination_options  # match source values with destination values
    }

    print(LOG_OPTION_MAPPING_CREATED.format(mapping=field_option_mapping))
    return field_option_mapping


def update_field(issue_key, desired_values):
    """
    Update the destination multi-select field for a specific issue.
    :param issue_key: Key of the issue to update (for example, "PROJ-123").
    :param desired_values: list of destination option IDs.
    :return: None
    """
    # skip the update if there are no valid destination IDs
    if not desired_values:
        print(LOG_SKIP_NO_VALID_VALUES.format(issue_key=issue_key, value_ids=desired_values))
        return

    # create the update payload
    payload = {
        FIELDS: {
            f"{CUSTOM_FIELD_JSON}{MULTI_SELECT_DESTINATION}": desired_values
        }
    }

    print(LOG_PAYLOAD_PREVIEW.format(issue_key=issue_key, payload=str(payload))) # for debugging; str used for enums

    response = requests.put(f"{UPDATE_ENDPOINT}{issue_key}", headers=HEADERS, json=payload)

    if response.status_code == HTTPStatus.NO_CONTENT:
        print(LOG_UPDATE_SUCCESS.format(issue_key=issue_key))
    else:
        print(LOG_UPDATE_FAILURE.format(
            issue_key=issue_key,
            field=f"{CUSTOM_FIELD_JSON}{MULTI_SELECT_DESTINATION}",
            status_code=response.status_code,
            response=response.text
        ))


def get_issues_with_source_field_values(start_at=START_AT_VALUE, page_size=PAGE_SIZE):
    """
    Fetch issues that have values in the source multi-select custom field.
    :param start_at: Start index for pagination.
    :param page_size: Number of issues to fetch per page.
    :return: List of issues.
    """
    custom_field_jql = f"{CUSTOM_FIELD_JQL.format(source=MULTI_SELECT_SOURCE)}"
    jql = f"{custom_field_jql} {IS_NOT_EMPTY_CLAUSE} {ORDER}"
    payload = {
        JsonFieldNames.JQL: jql,
        START_AT: start_at,
        MAX_RESULTS: page_size,
        FIELDS: [f"{CUSTOM_FIELD_JSON}{MULTI_SELECT_SOURCE}", f"{CUSTOM_FIELD_JSON}{MULTI_SELECT_DESTINATION}"],
    }

    response = requests.post(SEARCH_ENDPOINT, headers=HEADERS, json=payload)

    if response.status_code != HTTPStatus.OK:
        print(ERROR_MSG_FETCH_ISSUES.format(
            source_field=custom_field_jql,
            status_code=response.status_code,
            response=response.text
        ))
        return []

    return response.json().get(ISSUES, [])


def create_save_file(issue_key, source_values, destination_values):
    """
    Append the current state of an issue's source and destination fields to the save file.
    :param issue_key: The key of the issue (for example, "PROJ-123").
    :param source_values: Current values in the source field (a list of objects).
    :param destination_values: Current values in the destination field (a list of objects).
    :return: None
    """
    try:
        # extract the VALUE fields from the raw JSON objects
        source_values_cleaned = [entry[VALUE] for entry in source_values]
        destination_values_cleaned = [entry[VALUE] for entry in destination_values] if destination_values else ""

        # write the cleaned-up values
        with open(SAVE_FILENAME, FILE_APPEND_MODE) as save_file:
            writer = csv.writer(save_file)
            writer.writerow([issue_key, source_values_cleaned, destination_values_cleaned])
        print(LOG_SAVE_SUCCESS.format(issue_key=issue_key))
    except Exception as error:
        print(ERROR_MSG_APPEND_LOAD.format(issue_key=issue_key, error=str(error)))


def initialize_save_file():
    """
    Initialize the save file with headers if it doesn't exist or gets overwritten.
    :return: None
    """
    with open(SAVE_FILENAME, FILE_WRITE_MODE) as save_file:
        writer = csv.writer(save_file)
        writer.writerow([ISSUE_KEY, SOURCE_VALUES, DESTINATION_VALUES])  # save file headers


def main():
    """
    The script processes and updates issues with specific custom field values in a paginated manner using the JIRA API.
    Initially, it retrieves issues containing relevant field values, collects them for processing, and writes the
    current state into a save file as a backup. Subsequently, it builds a mapping of field option IDs and applies updates
    to the required field values for each issue, ensuring the changes are necessary before updating.
    :return: None
    """
    custom_source_json = f"{CUSTOM_FIELD_JSON}{MULTI_SELECT_SOURCE}"

    # initialize the save file
    initialize_save_file()

    print(LOG_FETCH_ISSUES.format(field=f"{CUSTOM_FIELD_JQL.format(source=MULTI_SELECT_SOURCE)}"))
    start_at = START_AT_VALUE
    issues_with_field_values = []  # collect all issues for processing field options
    while True:
        # fetch issues with pagination
        issues = get_issues_with_source_field_values(start_at=start_at, page_size=PAGE_SIZE)
        # print(f"Fetched {len(issues)} issues: {issues}...") # for debugging
        if not issues:
            break

        issues_with_field_values.extend(issues)  # collect the issues

        for issue in issues:
            issue_key = issue[JsonFieldNames.KEY]
            fields = issue[FIELDS]

            source_values = fields.get(custom_source_json, [])
            destination_values = fields.get(f"{CUSTOM_FIELD_JSON}{MULTI_SELECT_DESTINATION}", [])

            # create a save file with the current values
            create_save_file(issue_key, source_values, destination_values)

        # update the starting index for the next page
        start_at += PAGE_SIZE

    # build the field option mapping after collecting all issues
    field_option_id_map = build_field_option_mapping(issues_with_field_values)

    # process issues in a second loop to apply field updates
    for issue in issues_with_field_values:
        issue_key = issue[JsonFieldNames.KEY]
        fields = issue[FIELDS]

        # retrieve the source and destination values from the current issue
        source_values = fields.get(custom_source_json, [])
        current_destination_values = fields.get(f"{CUSTOM_FIELD_JSON}{MULTI_SELECT_DESTINATION}", [])

        # normalize current and desired values by extracting only the 'id' keys
        current_ids = {entry[JsonFieldNames.ID] for entry in current_destination_values or []}
        desired_ids = {
            field_option_id_map[entry[JsonFieldNames.ID]]
            for entry in source_values
            if entry[JsonFieldNames.ID] in field_option_id_map  # only include valid mappings
        }

        # if the current IDs already match the desired IDs, skip the update as it's unnecessary
        if current_ids == desired_ids:
            print(LOG_SKIP_ISSUE.format(issue_key=issue_key))
            continue

        # compute the desired destination values (used for the actual update payload)
        desired_values = [{str(JsonFieldNames.ID): id_value} for id_value in desired_ids]

        # for debugging
        print(LOG_UPDATE_INFO.format(
            issue_key=issue_key,
            values=desired_values))
        update_field(issue_key, desired_values)


if __name__ == "__main__":
    main()
