#!../.venv/bin/python
import csv
from utils.jira_utils import (fetch_custom_fields, query_issues_using_field, FILE_WRITE_MODE, JsonFieldNames,
                              LOG_FETCH_FIELDS)

# key global variables
OUTPUT_CSV_FILENAME = "1_custom_field_usage_report.csv"
HEADER_FIELD_NAMES = ["custom_field_id", "custom_field_name", "issues_using_field"]

# console log messages
LOG_QUERY_FIELD_USAGE = "Querying usage for field '{field_name}' ({clause_name})..."
LOG_WRITE_SUCCESS = "Custom field usage data has been written to {filename} successfully."


def write_field_usage_to_csv(field_usage_data):
    """
    Write the custom field usage data to a CSV file.
    :param field_usage_data: List of dictionaries containing field usage data.
    :return: None
    """
    with open(OUTPUT_CSV_FILENAME, FILE_WRITE_MODE) as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(HEADER_FIELD_NAMES)
        for field in field_usage_data:
            csv_writer.writerow([field[JsonFieldNames.ID], field[JsonFieldNames.NAME], field[JsonFieldNames.USAGE]])

    print(LOG_WRITE_SUCCESS.format(filename=OUTPUT_CSV_FILENAME))


def main():
    """
    The script processes custom fields data, queries for their usage in issues, and outputs the resulting data
    to a CSV file. It fetches the custom fields, queries issues for each field's usage, and records the
    information in a structured format.
    :return: None
    """
    print(LOG_FETCH_FIELDS)
    custom_fields = fetch_custom_fields()

    field_usage_data = []
    for field in custom_fields:
        clause_name = field[JsonFieldNames.CLAUSE_NAMES][0]
        schema_type = field.get(JsonFieldNames.SCHEMA, {}).get(JsonFieldNames.TYPE, JsonFieldNames.UNKNOWN)
        print(LOG_QUERY_FIELD_USAGE.format(field_name=field[JsonFieldNames.NAME], clause_name=clause_name))
        usage = query_issues_using_field(clause_name, schema_type)
        field_usage_data.append({JsonFieldNames.ID: field[JsonFieldNames.ID], JsonFieldNames.NAME: field[
            JsonFieldNames.NAME], JsonFieldNames.USAGE: usage})

    write_field_usage_to_csv(field_usage_data)


if __name__ == "__main__":
    main()
