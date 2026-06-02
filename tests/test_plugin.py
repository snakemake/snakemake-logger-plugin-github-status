from snakemake_logger_plugin_github_status import LogHandlerSettings
from snakemake_logger_plugin_github_status import LogHandler
from snakemake_interface_logger_plugins.tests import TestLogHandlerBase


class TestPlugin(TestLogHandlerBase):
    __test__ = True

    def get_log_handler_cls(self):
        return LogHandler

    def get_log_handler_settings(self):
        return LogHandlerSettings()


class TestPluginWithRunName(TestPlugin):
    def get_log_handler_settings(self):
        return LogHandlerSettings(run_name="test_run")
