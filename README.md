# Setup steps
- Used an official docker image per [Atlassian docker](https://hub.docker.com/r/atlassian/jira-software) page
  - Ran these 2 commands locally to provide a backing store for the image:
    - `docker volume create --name jiraVolume`
    - `docker run -v jiraVolume:/var/atlassian/application-data/jira --name="jira" -d -p 8080:8080 atlassian/jira-software`
- Had a Postgres database installed via Homebrew
  - Pointed [Jira docker instance](http://localhost:8080/) to `host.docker.internal` as the local non-Docker database 
    host
  - Filled out user/password for the local Postgres public database and schema
- Set up trial license at id.atlassian.com
  - Copy/pasted it going through local Jira Data Center setup
- Set up admin user, then 2 initial projects using sample data
  - Both the Scrum and Project Management sample projects
  - Set up local access token for admin user
    - Using the jira-administrator role for this local Jira Data Center instance, which has enough permissions 
      to perform all 3 requests via the REST API
  - `cd scripts` in this repo
  - Edit the .env file and replace the `PERSONAL_ACCESS_TOKEN` variable value with the new access token for the 
    admin user
  - `source ./.env` (for zsh)
  - Using a secrets manager would be ideal outside this local environment; have previously used 1Password, GitHub, 
    CircleCI, or AWS Secrets Manager

# Approach to solve requests
## Background
- Normally I dig into requirements to understand the context as it has proven best to understand the "why" behind the 
  request as well as the request’s context
  - Once there is a clear "why," a more straightforward solution than the one requested might provide more value to 
    the customer (internal or external)
  - For both requests #1 & #2:
    - #1 Generates a report that shows the number of times a Custom Field has been used in total across 
      the system
    - #2 Generates a report that shows the number of times a Custom Field has been used in total across all projects 
      within the system
    - Thinking these can replace the [built-in UI report](http://localhost:8080/secure/admin/ViewCustomFields.jspa) 
      for custom fields
      - Due to the UI report refreshing only once a day, an on-demand report makes sense to provide the most up-to-date 
        information
      - Therefore, model the report output after key information in the UI report:
        - Custom field ID
        - Custom field name
        - Issues are an integer count of issues with data in the custom field
    - Provided the output in CSV format
      - Straightforward to change output to alternatives such as text, JSON, or gRPC based on team practices
- While the scale for these simplified examples only has a max of 29 issues, a more robust solution could require 
  pagination of results as well as streamlining REST API results to focus only on the required data
  - Used global variables as a starting place; if the scripts run outside a local environment, would move them 
    into a Config class with a corresponding object passed into functions
  - Testing scope is confirming the script output via the UI; it was very straightforward for these examples
    - Prefer to follow team testing best practices around unit/integration tests based on the environment and complexity
    - Found it best to add tests such that refactoring becomes a minimal risk activity
  - Used simplistic console logs and errors for these scripts since they run locally. Have experience setting up and 
    using DataDog, Open Telemetry, or central logs via Splunk for observability and traceability
- For request #3: write a script to copy the values of a given multi-select type field to another multi-select type
  field
  - Set up both "Multi-Select Source" and "Multi-Select Destination" custom fields, each with Value1, Value2, Value3
    - Set 7 issues' "Multi-Select Source" field with different combinations of the 3 values (Value1, Value2, and/or 
      Value3)
  - Be sure to understand who the change impacts and give them advanced notice per Service Level Agreements (SLAs)
    - If there were a large number of potential issues impacted, then one way to narrow the selection criteria is 
      determining how valuable it is to copy values for closed or done issues
      - If the value to customers is low, then adding a JQL clause such as `status != Done` could result in a more 
        focused, less impactful change
    - Used the assumption for this request that all issues needed to update the "Multi-Select Destination" field’s 
      values
  - After running a script that affects a larger number of issues, would want to know when the next scheduled 
    reindex occurs or schedule one (directly or via a request to the team managing that function)
    - Would also Depend on how the scripted change impacts performance for internal customers

## Investigation towards and then solving #1
- Reviewed included [REST API link](https://docs.atlassian.com/software/jira/docs/api/REST/7.3.1/) and found the 
  following endpoints of interest for solving both #1 & #2
  - `GET /rest/api/2/field`
  - `GET /rest/api/2/search`
- Started with `scripts/list_jira_custom_fields.py`
  - Wanted to understand the JSON returned from the `field` endpoint
  - After examining the response, decided to parse the `id` & `name` keys where the `custom` key is true
    - Output as CSV in a separate function
- Moved onto the `search` endpoint
  - Iterated on different combinations of `fields` query values
    - Eventually found `"*all","-comment"`, which enables parsing a response with custom field values for each issue
    - Since that is only a potential future request, focused on the requirements, for which `field` should be empty
  - For custom fields, JQL needs to use the first `clauseNames` with the second being the custom field name
  - Only need to parse the `total` key's value when JQL is successful
  - Through trial and error, each `schema.type` key value appears to have different JQL requirements, so settle on 2 
    patterns plus a special case for `cf[10000]` = Development
    - Would be interested to know if there is a better approach
  - Store CSV output in `scripts/custom_field_usage_report.csv` from `scripts/1_custom_field_usage.py`
    - Confirm CSV counts via the UI in Issues JQL search, here’s an [example](http://localhost:8080/browse/SCRUM-7?jql=%22Parent%20Link%22%20%20is%20not%20empty%20order%20by%20id)
  - Break the script into functions, add comments, move token to environment variable:
    - Execute `./1_custom_field_usage.py` after `cd scripts`
      - May need to run `chmod u+x *.py`
      - Should function if setup steps are complete and python binary exists here: `../.venv/bin/python`
    - See `scripts/1_custom_field_usage.out` for my local output and `scripts/1_custom_field_usage_report.csv` for CSV 
      results

## Solving #2
- Similar approach from #1
- However, first make use of `GET /rest/api/2/project` to get the list of project keys and names
- Then use the project key in the JQL call to `search`
- Review the CSV output to confirm it matches JQL Issue query results and aligns with #1’s CSV output
- Abstract common functions between both scripts into `scripts/utils/jira_utils.py`
- Execute `./2_custom_field_usage_by_project.py` after `cd scripts`
  - May need to run `chmod u+x *.py`
  - Should execute if setup steps are complete and python binary exists here: `../.venv/bin/python`
- See `scripts/2-custom_field_usage_by_project.out` for my local output and `scripts/2_custom_field_usage_by_project.
  csv` for CSV results

## Solving #3
- Took some setup steps for this item, described in the Background section above
- Since this script changes values, the first step saves the issues’ values
- Using the `GET /rest/api/2/search` & `Edit Issue: PUT /rest/api/2/issue/{issueIdOrKey}` endpoints
- Referenced [this article](https://confluence.atlassian.com/jirakb/how-to-retrieve-available-options-for-a-multi-select-customfield-via-jira-rest-api-815566715.html) 
  for how to get the destination field’s valid values
- High-level steps taken:
  - Create or overwrite the CSV file to log the current state of source and destination field values for issues
  - Use JQL to query issues containing values in the source custom multi-select field
    - Collect all relevant issues for further processing
  - Extract values for the source and destination fields from fetched issues
  - Append these values into the initialized CSV file for backup purposes
  - Retrieve the valid values for source and destination custom fields
    - Dynamically map source field option IDs to destination field option IDs based on matching values
  - Iterate through each issue to compute the desired state of the destination field using the mapping
    - Skip issues where the destination field would remain the same
    - The initial run of the script typically differs as described in the Background section above
  - Construct a JSON payload containing the updated destination field IDs
  - Send the update requests to Jira for the issues requiring changes
  - Handle and log API errors during fetch or update operations
  - Log successful updates and skips to the console
  - Confirm results in the UI with this JQL search: ["Multi-Select Destination" is not EMPTY order by id](http://localhost:8080/browse/SCRUM-23?jql=%22Multi-Select%20Destination%22%20is%20not%20EMPTY%20order%20by%20id)
    - Also via running the script a 2nd time –> see below directions
- Execute `./3_copy_multi-select_values_between_fields.py` after `cd scripts`
  - May need to run `chmod u+x *.py`
  - As long as Setup steps are complete and python binary exists here: `../.venv/bin/python`
- See `scripts/3_copy_multi-select_values_between_fields.out` for my local output before copying values & 
  `scripts/3-after_copy_multi-select_values_between_fields.out` for my local output after copying values
- Likewise, see `scripts/3_current_multi_select_fields.csv` & `scripts/3-after_current_multi_select_fields.csv` 
  for results before & after
