from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import bobtv


UK = "Status: Connected\nCountry: United Kingdom\n"
CA = "Status: Connected\nCountry: Canada\n"


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.config = bobtv.load_config(Path(bobtv.__file__).with_name("services.json"))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)

    @patch("bobtv.shutil.which", return_value="/usr/bin/tool")
    @patch("bobtv.subprocess.Popen")
    @patch("bobtv.vpn", return_value=UK)
    def test_reuses_uk_connection(self, vpn, browser, which):
        browser.return_value.wait.return_value = 0
        bobtv.launch(self.config, "bbc-iplayer", self.state)
        vpn.assert_called_once_with("status")
        self.assertEqual(browser.call_args.args[0], ["chromium", "--new-window", "https://www.bbc.co.uk/iplayer"])

    @patch("bobtv.shutil.which", return_value="tool")
    @patch("bobtv.subprocess.Popen")
    @patch("bobtv.vpn", side_effect=[CA, "Connected", UK])
    def test_switches_and_verifies_before_open(self, vpn, browser, which):
        browser.return_value.wait.return_value = 0
        bobtv.launch(self.config, "bbc-iplayer", self.state)
        self.assertEqual([c.args for c in vpn.call_args_list], [("status",), ("connect", "United_Kingdom"), ("status",)])
        browser.assert_called_once()

    @patch("bobtv.shutil.which", return_value="tool")
    @patch("bobtv.subprocess.Popen")
    @patch("bobtv.time.sleep")
    @patch("bobtv.vpn", return_value=CA)
    def test_wrong_country_never_opens_browser(self, vpn, sleep, browser, which):
        with self.assertRaises(bobtv.ActionError):
            bobtv.launch(self.config, "bbc-iplayer", self.state)
        browser.assert_not_called()

    @patch("bobtv.shutil.which", return_value="tool")
    @patch("bobtv.subprocess.Popen")
    @patch("bobtv.vpn", side_effect=bobtv.ActionError("You're not logged in"))
    def test_login_failure_never_opens_browser(self, vpn, browser, which):
        with self.assertRaises(bobtv.ActionError):
            bobtv.launch(self.config, "bbc-iplayer", self.state)
        browser.assert_not_called()

    @patch("bobtv.vpn", side_effect=[UK, "Connected", CA])
    def test_other_country_is_configuration_driven(self, vpn):
        bobtv.ensure_region(self.config["regions"]["ca"])
        self.assertEqual(vpn.call_args_list[1].args, ("connect", "Canada"))

    def test_disconnected_and_missing_country_rejected(self):
        for output in ["Status: Disconnected\nCountry: United Kingdom", "Status: Connected", "You're not logged in"]:
            self.assertFalse(bobtv.is_connected(output, "United Kingdom"))

    @patch("bobtv.shutil.which", return_value="tool")
    @patch("bobtv.subprocess.Popen")
    @patch("bobtv.vpn", return_value=UK)
    def test_check_only_does_not_launch(self, vpn, browser, which):
        bobtv.launch(self.config, "bbc-iplayer", self.state, check_only=True)
        browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
