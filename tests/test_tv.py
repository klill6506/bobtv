"""TV control over HDMI-CEC. No adapter is touched: cec-client is always mocked."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import bobtv


def fake_process(returncode=0, stderr=""):
    process = MagicMock()
    process.returncode = returncode
    process.stderr.read.return_value = stderr
    process.stdin = MagicMock()
    return process


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.config = bobtv.load_config(Path(bobtv.__file__).with_name("services.json"))

    def test_shipped_config_enables_the_tv(self):
        self.assertTrue(bobtv.tv_settings(self.config)["enabled"])
        self.assertEqual(bobtv.tv_settings(self.config)["address"], "0")

    def test_defaults_fill_in_missing_keys(self):
        settings = bobtv.tv_settings({"tv": {"enabled": True}})
        self.assertEqual(settings["hold_seconds"], bobtv.TV_DEFAULTS["hold_seconds"])
        self.assertIsNone(settings["device"])

    def test_config_without_a_tv_section_is_off(self):
        self.assertFalse(bobtv.tv_settings({})["enabled"])


class ConfigValidationTests(unittest.TestCase):
    def setUp(self):
        self.base = json.loads(Path(bobtv.__file__).with_name("services.json").read_text())
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def write(self, tv):
        config = dict(self.base)
        if tv is None:
            config.pop("tv", None)
        else:
            config["tv"] = tv
        path = Path(self.temp.name) / "services.json"
        path.write_text(json.dumps(config))
        return path

    def test_a_missing_tv_section_is_allowed(self):
        bobtv.load_config(self.write(None))

    def test_good_settings_load(self):
        bobtv.load_config(self.write({"enabled": True, "address": "0", "hold_seconds": 0, "device": "/dev/ttyACM0"}))

    def test_bad_settings_are_rejected(self):
        for tv in (
            {"enabled": "yes"},
            {"address": "00"},
            {"address": "z"},
            {"hold_seconds": -1},
            {"hold_seconds": 31},
            {"hold_seconds": True},
            {"device": "ttyACM0"},
            {"device": "/etc/passwd/../../dev/x"},
            {"typo": True},
            [],
        ):
            with self.subTest(tv=tv), self.assertRaises(bobtv.ActionError):
                bobtv.load_config(self.write(tv))


class CecTests(unittest.TestCase):
    def setUp(self):
        self.settings = {"enabled": True, "address": "0", "hold_seconds": 0, "device": None}

    @patch("bobtv.time.sleep")
    @patch("bobtv.subprocess.Popen")
    @patch("bobtv.shutil.which", return_value="/usr/bin/cec-client")
    def test_commands_are_written_then_the_connection_closes(self, which, popen, sleep):
        process = fake_process()
        popen.return_value = process
        bobtv.cec(self.settings, ["on 0", "as"])
        written = "".join(call.args[0] for call in process.stdin.write.call_args_list)
        self.assertEqual(written, "on 0\nas\nq\n")
        process.stdin.close.assert_called_once()
        self.assertEqual(popen.call_args[0][0], ["cec-client", "-d", "1"])

    @patch("bobtv.time.sleep")
    @patch("bobtv.subprocess.Popen")
    @patch("bobtv.shutil.which", return_value="/usr/bin/cec-client")
    def test_the_adapter_is_told_to_quit_so_it_never_lingers(self, which, popen, sleep):
        """cec-client keeps running on EOF; without the quit it is killed on a timeout."""
        process = fake_process()
        popen.return_value = process
        bobtv.cec(self.settings, ["as"])
        self.assertEqual(process.stdin.write.call_args_list[-1].args[0], "q\n")
        process.kill.assert_not_called()

    @patch("bobtv.time.sleep")
    @patch("bobtv.subprocess.Popen")
    @patch("bobtv.shutil.which", return_value="/usr/bin/cec-client")
    def test_the_claim_is_held_open(self, which, popen, sleep):
        popen.return_value = fake_process()
        bobtv.cec({**self.settings, "hold_seconds": 6}, ["as"])
        sleep.assert_called_once_with(6)

    @patch("bobtv.time.sleep")
    @patch("bobtv.subprocess.Popen")
    @patch("bobtv.shutil.which", return_value="/usr/bin/cec-client")
    def test_an_explicit_device_is_passed_through(self, which, popen, sleep):
        popen.return_value = fake_process()
        bobtv.cec({**self.settings, "device": "/dev/ttyACM1"}, ["as"])
        self.assertEqual(popen.call_args[0][0][-1], "/dev/ttyACM1")

    @patch("bobtv.shutil.which", return_value=None)
    def test_a_missing_cec_client_is_an_action_error(self, which):
        with self.assertRaises(bobtv.ActionError):
            bobtv.cec(self.settings, ["as"])

    @patch("bobtv.time.sleep")
    @patch("bobtv.subprocess.Popen")
    @patch("bobtv.shutil.which", return_value="/usr/bin/cec-client")
    def test_a_failing_adapter_is_an_action_error(self, which, popen, sleep):
        popen.return_value = fake_process(returncode=1, stderr="ERROR: no adapter\n")
        with self.assertRaises(bobtv.ActionError):
            bobtv.cec(self.settings, ["as"])

    @patch("bobtv.time.sleep")
    @patch("bobtv.subprocess.Popen")
    @patch("bobtv.shutil.which", return_value="/usr/bin/cec-client")
    def test_a_hung_adapter_is_killed_not_left_running(self, which, popen, sleep):
        process = fake_process()
        process.wait.side_effect = [subprocess.TimeoutExpired("cec-client", 20), 0]
        popen.return_value = process
        with self.assertRaises(bobtv.ActionError):
            bobtv.cec(self.settings, ["as"])
        process.kill.assert_called_once()


class TvActionTests(unittest.TestCase):
    def setUp(self):
        self.config = {"tv": {"enabled": True, "address": "0", "hold_seconds": 0}}

    @patch("bobtv.cec")
    def test_wake_turns_on_then_claims_the_input(self, cec):
        bobtv.tv_wake(self.config)
        self.assertEqual(cec.call_args[0][1], ["on 0", "as"])

    @patch("bobtv.cec")
    def test_standby_only_sends_standby(self, cec):
        bobtv.tv_standby(self.config)
        self.assertEqual(cec.call_args[0][1], ["standby 0"])

    @patch("bobtv.cec")
    def test_here_wakes_and_claims(self, cec):
        bobtv.tv_command(self.config, "here")
        self.assertEqual(cec.call_args[0][1], ["on 0", "as"])

    @patch("bobtv.cec")
    def test_on_does_not_steal_the_input(self, cec):
        bobtv.tv_command(self.config, "on")
        self.assertEqual(cec.call_args[0][1], ["on 0"])

    @patch("bobtv.cec")
    def test_the_configured_address_is_used(self, cec):
        bobtv.tv_command({"tv": {"enabled": True, "address": "4"}}, "off")
        self.assertEqual(cec.call_args[0][1], ["standby 4"])

    @patch("bobtv.cec")
    def test_tv_command_refuses_when_disabled(self, cec):
        with self.assertRaises(bobtv.ActionError):
            bobtv.tv_command({"tv": {"enabled": False}}, "here")
        cec.assert_not_called()


class PowerQueryTests(unittest.TestCase):
    def setUp(self):
        self.config = {"tv": {"enabled": True, "address": "0"}}

    def run_with(self, stdout):
        with patch("bobtv.shutil.which", return_value="/usr/bin/cec-client"), \
             patch("bobtv.subprocess.run") as run:
            run.return_value = MagicMock(stdout=stdout)
            return bobtv.tv_power(self.config), run

    def test_reads_on_and_standby(self):
        self.assertEqual(self.run_with("opening...\npower status: on\n")[0], "on")
        self.assertEqual(self.run_with("power status: standby\n")[0], "standby")

    def test_reads_transitions(self):
        text = "power status: in transition from standby to on\n"
        self.assertEqual(self.run_with(text)[0], "in transition from standby to on")

    def test_says_none_when_the_tv_will_not_answer(self):
        self.assertIsNone(self.run_with("opening a connection to the CEC adapter...\n")[0])

    def test_asks_the_configured_address_in_one_shot_mode(self):
        _, run = self.run_with("power status: on\n")
        self.assertEqual(run.call_args.kwargs["input"], "pow 0\n")
        self.assertIn("-s", run.call_args.args[0])

    def test_a_hung_query_is_an_action_error(self):
        with patch("bobtv.shutil.which", return_value="/usr/bin/cec-client"), \
             patch("bobtv.subprocess.run", side_effect=subprocess.TimeoutExpired("cec-client", 20)):
            with self.assertRaises(bobtv.ActionError):
                bobtv.tv_power(self.config)


class ToggleTests(unittest.TestCase):
    """The remote's power button."""

    def setUp(self):
        self.config = {"tv": {"enabled": True, "address": "0", "hold_seconds": 0}}

    def toggle_when(self, power):
        with patch("bobtv.tv_power", return_value=power), \
             patch("bobtv.tv_standby") as standby, patch("bobtv.tv_wake") as wake:
            bobtv.tv_command(self.config, "toggle")
        return standby, wake

    def test_an_on_tv_goes_to_standby(self):
        standby, wake = self.toggle_when("on")
        standby.assert_called_once()
        wake.assert_not_called()

    def test_a_tv_waking_up_is_treated_as_on(self):
        standby, wake = self.toggle_when("in transition from standby to on")
        standby.assert_called_once()
        wake.assert_not_called()

    def test_a_standby_tv_wakes_to_bobtv(self):
        standby, wake = self.toggle_when("standby")
        wake.assert_called_once()
        standby.assert_not_called()

    def test_a_tv_going_to_sleep_is_woken_again(self):
        standby, wake = self.toggle_when("in transition from on to standby")
        wake.assert_called_once()

    def test_a_silent_tv_is_woken_because_that_is_harmless(self):
        standby, wake = self.toggle_when(None)
        wake.assert_called_once()
        standby.assert_not_called()

    @patch("bobtv.tv_power")
    def test_toggle_refuses_when_disabled(self, power):
        with self.assertRaises(bobtv.ActionError):
            bobtv.tv_command({"tv": {"enabled": False}}, "toggle")
        power.assert_not_called()


class LaunchIntegrationTests(unittest.TestCase):
    """The TV must never be able to stop a service from opening."""

    def setUp(self):
        self.config = bobtv.load_config(Path(bobtv.__file__).with_name("services.json"))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        for target in ("bobtv.shutil.which", "bobtv.ensure_region", "bobtv.subprocess.Popen"):
            patcher = patch(target)
            self.addCleanup(patcher.stop)
            mock = patcher.start()
            if target.endswith("which"):
                mock.return_value = "/usr/bin/tool"
            if target.endswith("Popen"):
                mock.return_value.wait.return_value = 0

    @patch("bobtv.tv_wake")
    def test_launching_wakes_the_tv(self, wake):
        bobtv.launch(self.config, "bbc-iplayer", self.state)
        wake.assert_called_once()

    @patch("bobtv.ensure_region", side_effect=bobtv.ActionError("wrong country"))
    @patch("bobtv.tv_wake")
    def test_a_failed_region_check_leaves_the_tv_alone(self, wake, region):
        """A launch that never opens must not light up the room."""
        with self.assertRaises(bobtv.ActionError):
            bobtv.launch(self.config, "bbc-iplayer", self.state)
        wake.assert_not_called()

    @patch("bobtv.tv_wake", side_effect=bobtv.ActionError("no adapter"))
    def test_a_dead_adapter_still_opens_the_service(self, wake):
        bobtv.launch(self.config, "bbc-iplayer", self.state)
        wake.assert_called_once()

    @patch("bobtv.tv_wake", side_effect=OSError("unplugged"))
    def test_an_unplugged_adapter_still_opens_the_service(self, wake):
        bobtv.launch(self.config, "bbc-iplayer", self.state)

    @patch("bobtv.tv_wake")
    def test_check_only_never_touches_the_tv(self, wake):
        bobtv.launch(self.config, "bbc-iplayer", self.state, check_only=True)
        wake.assert_not_called()

    @patch("bobtv.tv_wake")
    def test_the_tv_is_left_alone_when_disabled(self, wake):
        config = dict(self.config)
        config["tv"] = {"enabled": False}
        bobtv.launch(config, "bbc-iplayer", self.state)
        wake.assert_not_called()


if __name__ == "__main__":
    unittest.main()
