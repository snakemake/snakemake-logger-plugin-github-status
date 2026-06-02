A Snakemake logger plugin that reports to the Github commit status.
The plugin assumes that it is used in combination with working directories that are controlled by git and associated to a Github repository.
It then reports logging events to the Github status API, such that Github displays the status of workflow runs attached to the current commit.
Github's status markers (running, success, failed) are thereby used to represent the state of the workflow execution, while the status messages are used to report on the number of completed and failed jobs.