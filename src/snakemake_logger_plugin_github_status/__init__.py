import time
from typing import Dict
from typing import Optional
from collections import defaultdict
import os
from logging import LogRecord
import subprocess as sp

from git import Repo
import requests

from snakemake_interface_logger_plugins.base import LogHandlerBase
from snakemake_interface_logger_plugins.common import LogEvent
from snakemake_interface_common.exceptions import WorkflowError


class LogHandler(LogHandlerBase):
    def __post_init__(self) -> None:
        try:
            self._github_token = os.environ["GITHUB_TOKEN"]
        except KeyError:
            try:
                res = sp.run(["gh", "auth", "token"], capture_output=True, text=True)
            except sp.CalledProcessError as e:
                raise WorkflowError(
                    f"Unable to retrieve $GITHUB_TOKEN. Either set one manually or authenticate using 'gh auth login'. Error: {e.stderr}"
                )
            self._github_token = res.stdout

        self._repo = Repo(os.getcwd())
        self._github_repo_name = "/".join(
            self._repo.remotes.origin.url.rstrip(".git").split(":")[1].split("/")[-2:]
        )
        self._repo.remotes.origin.fetch()
        branch = self._repo.active_branch
        tracking_branch = branch.tracking_branch()
        if tracking_branch is None:
            raise WorkflowError(
                f"No tracking branch of current git branch {branch}. Make sure that your local repo is pushed."
            )

        self._github_sha = tracking_branch.commit.hexsha
        self._errors: Dict[str, int] = defaultdict(int)
        self._progress_done: int = 0
        self._progress_total: Optional[int] = None
        self.state: Optional[str] = None
        self._last_emit_timestamp: Optional[float] = None
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @property
    def writes_to_stream(self) -> bool:
        # Whether this plugin writes to stderr/stdout.
        # If your plugin writes to stderr/stdout, return
        # true so that Snakemake disables its stderr logging.
        return False

    @property
    def writes_to_file(self) -> bool:
        # Whether this plugin writes to a file.
        # If your plugin writes log output to a file, return
        # true so that Snakemake can report your logfile path at workflow end.
        return False

    @property
    def has_filter(self) -> bool:
        # Whether this plugin attaches its own filter.
        # Return true if your plugin provides custom log filtering logic.
        # If false is returned, Snakemake's DefaultFilter will be attached see: https://github.com/snakemake/snakemake/blob/960f6a89eaa31da6014e810dfcf08f635ac03a6e/src/snakemake/logging.py#L372 # noqa: E501
        # See https://docs.python.org/3/library/logging.html#filter-objects for info on how to define and attach a Filter
        return False

    @property
    def has_formatter(self) -> bool:
        # Whether this plugin attaches its own formatter.
        # Return true if your plugin provides custom log formatting logic.
        # If false is returned, Snakemake's Defaultformatter will be attached see: https://github.com/snakemake/snakemake/blob/960f6a89eaa31da6014e810dfcf08f635ac03a6e/src/snakemake/logging.py#L132 # noqa: E501
        # See https://docs.python.org/3/library/logging.html#formatter-objects for info on how to define and attach a Formatter
        return True

    @property
    def needs_rulegraph(self) -> bool:
        # Whether this plugin requires the DAG rulegraph.
        # Return true if your plugin needs access to the workflow's
        # directed acyclic graph for logging purposes.
        return False

    def emit(self, record: LogRecord) -> None:
        event = getattr(record, "event", None)
        if event == LogEvent.PROGRESS:
            self._progress_done = record.done
            self._progress_total = record.total
        elif event == LogEvent.JOB_ERROR:
            self._errors[record.rule_name] += 1
        elif self.state is not None:
            # we already have reported that the workflow runs, thus we can ignore
            # any non-progress and non-error events, as they won't change the reported
            # state
            return

        top3 = sorted(
            self._errors.keys(),
            key=lambda rulename: self._errors[rulename],
            reverse=True,
        )[:3]
        dots = "..." if len(self._errors) > 3 else ""
        errors = " ".join(f"{rulename}={self._errors[rulename]}" for rulename in top3)

        if self._progress_total is not None:
            progress = (
                f"{self._progress_done}/{self._progress_total} "
                f"({self._progress_done / self._progress_total:.2%})\n"
            )
        else:
            progress = f"{self._progress_done}/n\n"

        description = f"{progress}errors: {errors} {dots}"
        if self._errors:
            self.state = "failed"
        elif self._progress_done == self._progress_total:
            self.state = "success"
        else:
            self.state = "pending"

        if (
            self._last_emit_timestamp is not None
            and time.time() - self._last_emit_timestamp < 5
            and not self.state == "success"
        ):
            # Avoid emitting too often, as this can cause rate-limiting issues with the GitHub API
            # Exception: we always emit on "success"
            return

        self._last_emit_timestamp = time.time()
        res = requests.post(
            f"https://api.github.com/repos/{self._github_repo_name}/statuses/{self._github_sha}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._github_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            data={
                "state": self.state,
                "context": "snakemake",
                "description": description,
            },
        )
        res.raise_for_status()
