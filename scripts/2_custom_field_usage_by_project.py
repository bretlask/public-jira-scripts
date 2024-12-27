#!../.venv/bin/python
import csv
from utils.jira_utils import (fetch_custom_fields, fetch_projects, query_issues_using_field, FILE_WRITE_MODE,
                              JsonFieldNames, LOG_FETCH_FIELDS)

# key global variables
OUTPUT_CSV_FILENAME = "2_custom_field_usage_by_project.csv"
HEADER_FIELD_NAMES = [
    "custom_field_id",
    "custom_field_name",
    "project_key",
    "project_name",
    "issues_using_field"
]

# console log messages
LOG_FETCH_PROJECTS = "Fetching projects..."
LOG_QUERY_FIELD_USAGE = (
    "Querying usage for field '{field_name}' in project '{project_name}'..."
)
LOG_WRITE_SUCCESS = "Custom field usage data (by project) has been written to {filename} successfully."


def write_field_usage_to_csv(field_usage_data):
    """
    Takes a list of field usage data dictionaries, writes it to a CSV file using pre-defined headers,
    and confirms successful writing through a log message. Each dictionary in the input expects to have specific
    field keys to extract relevant data for writing to the CSV file.
    :param field_usage_data: List of dictionaries containing field usage information.
    :return: None
    """
    with open(OUTPUT_CSV_FILENAME, FILE_WRITE_MODE) as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(HEADER_FIELD_NAMES)
        for field in field_usage_data:
            csv_writer.writerow([
                field[JsonFieldNames.ID],
                field[JsonFieldNames.NAME],
                field[JsonFieldNames.PROJECT_KEY],
                field[JsonFieldNames.PROJECT_NAME],
                field[JsonFieldNames.USAGE]
            ])

    print(LOG_WRITE_SUCCESS.format(filename=OUTPUT_CSV_FILENAME))


def main():
    """
    Executes the main workflow for retrieving the projects and custom field data, querying usage statistics for each
    field across projects, and writing the results to a CSV file. The function involves multiple stages,
    including fetching data, iterating over projects and fields, querying field usage, and saving the gathered
    information. It operates as the pipeline of data processing to generate structured field usage analytics.
    :return: None
    """
    print(LOG_FETCH_PROJECTS)
    projects = fetch_projects()

    print(LOG_FETCH_FIELDS)
    custom_fields = fetch_custom_fields()

    field_usage_data = []
    for field in custom_fields:
        clause_name = field[JsonFieldNames.CLAUSE_NAMES][0]
        schema_type = field.get(JsonFieldNames.SCHEMA, {}).get(JsonFieldNames.TYPE, JsonFieldNames.UNKNOWN)
        for project in projects:
            print(LOG_QUERY_FIELD_USAGE.format(
                field_name=field[JsonFieldNames.NAME],
                project_name=project[JsonFieldNames.NAME]
            ))
            usage = query_issues_using_field(clause_name, schema_type, project[JsonFieldNames.KEY])
            field_usage_data.append({
                JsonFieldNames.ID: field[JsonFieldNames.ID],
                JsonFieldNames.NAME: field[JsonFieldNames.NAME],
                JsonFieldNames.PROJECT_KEY: project[JsonFieldNames.KEY],
                JsonFieldNames.PROJECT_NAME: project[JsonFieldNames.NAME],
                JsonFieldNames.USAGE: usage
            })

    write_field_usage_to_csv(field_usage_data)


if __name__ == "__main__":
    main()
