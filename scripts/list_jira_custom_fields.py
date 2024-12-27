#!../.venv/bin/python
import os
import requests
import csv
import sys
from http import HTTPStatus

# Read the Jira Personal Access Token from the environment variable
PERSONAL_ACCESS_TOKEN = os.getenv("PERSONAL_ACCESS_TOKEN")

if not PERSONAL_ACCESS_TOKEN:
    print("Error: PERSONAL_ACCESS_TOKEN environment variable is not set.")
    sys.exit(1)

# Jira base URL, fields endpoint, & output CSV filename
JIRA_BASE_URL = "http://localhost:8080"
CUSTOM_FIELDS_ENDPOINT = f"{JIRA_BASE_URL}/rest/api/2/field"
OUTPUT_CSV_FILENAME = "list_jira_custom_fields.csv"

# required headers
HEADERS = {
    "Authorization": f"Bearer {PERSONAL_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}


def fetch_custom_fields():
    """
    Fetch custom fields from the Jira API.
    :return: List of custom fields (as dictionaries), sorted by 'id'.
    """
    # make an authenticated GET request to the API
    response = requests.get(CUSTOM_FIELDS_ENDPOINT, headers=HEADERS)

    if response.status_code == HTTPStatus.OK:
        # print(response.json()) # for debugging
        fields = response.json()  # parse the response JSON

        # only select fields that have custom = true
        custom_fields = [field for field in fields if field["custom"]]

        # sort custom fields by id
        return sorted(custom_fields, key=lambda field: field["id"])
    else:
        print(f"Failed to retrieve fields. Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        return []


def write_custom_fields_to_csv(custom_fields):
    """
    Write custom fields to a CSV file with headers 'id' and 'name'.
    :param custom_fields: List of custom fields to write.
    """
    with open(OUTPUT_CSV_FILENAME, mode="w", newline="", encoding="utf-8") as csvfile:
        csv_writer = csv.writer(csvfile)

        # write header row
        csv_writer.writerow(["id", "name"])

        # write each custom field as a row
        for field in custom_fields:
            csv_writer.writerow([field["id"], field["name"]])

    print(f"Custom fields have been written to {OUTPUT_CSV_FILENAME} successfully.")


def main():
    """
    Main function to orchestrate fetching custom fields and writing output.
    """
    # fetch the custom fields from Jira
    custom_fields = fetch_custom_fields()

    if not custom_fields:
        # if no custom fields got fetched, output an error and exit
        print("Error: No custom fields were retrieved from the Jira API. Exiting.")
        sys.exit(1)  # exit the script with a non-zero status to indicate an error

    # write the fields to a CSV file
    write_custom_fields_to_csv(custom_fields)


if __name__ == "__main__":
    main()
