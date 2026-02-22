from snakemake_logger_plugin_github_status import LogHandler
from snakemake_interface_logger_plugins.tests import TestLogHandlerBase


class TestPlugin(TestLogHandlerBase):
    """Concrete test using the actual rich plugin to verify the abstract test class works."""

    __test__ = True

    def get_log_handler_cls(self):
        """Return the log handler class."""
        return LogHandler

    def get_log_handler_settings(self):
        """Return the settings with default values for testing."""
        return None
