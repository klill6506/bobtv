"""Doorbell on the TV. Nothing real is touched: Hyprland, Chromium and CEC are all mocked."""
import ipaddress
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import bobtv
import doorbell
import home_server
import windows

CAMERA = "0xcafe"
SHOW = "0xbeef"
HOME = "0xf00d"


class FakeDesktop:
    """A pretend Hyprland: windows appear when the camera opens and go when closed."""

    def __init__(self, active=SHOW, active_fullscreen=2, camera_appears=True, user_closes_camera=False):
        self.windows = {SHOW: {"address": SHOW, "fullscreen": active_fullscreen if active == SHOW else 0},
                        HOME: {"address": HOME, "fullscreen": 0}}
        self.active = active
        self.camera_appears = camera_appears
        self.user_closes_camera = user_closes_camera
        self.log = []

    def clients(self):
        return {a: dict(w) for a, w in self.windows.items()}

    def active_window(self):
        return dict(self.windows[self.active]) if self.active in self.windows else None

    def open_camera(self, url):
        self.log.append(("open", url))
        if self.camera_appears:
            self.windows[CAMERA] = {"address": CAMERA, "fullscreen": 2}

    def focus(self, address):
        self.log.append(("focus", address))
        self.active = address

    def make_fullscreen(self):
        self.log.append(("fullscreen", self.active))
        for w in self.windows.values():
            w["fullscreen"] = 0
        self.windows[self.active]["fullscreen"] = 2

    def close(self, address):
        self.log.append(("close", address))
        self.windows.pop(address, None)

    def sleep(self, seconds):
        self.log.append(("sleep", round(seconds)))
        if self.user_closes_camera and seconds > 1:
            self.windows.pop(CAMERA, None)


class ShowTests(unittest.TestCase):
    def setUp(self):
        self.config = {"tv": {"enabled": True, "address": "0", "hold_seconds": 0},
                       "doorbell": {"enabled": True, "url": "http://127.0.0.1:8123/bobtv-home/doorbell", "seconds": 30}}
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)

    def desktop_patches(self, desktop, playing=False):
        self.media_calls = []

        def media(action):
            self.media_calls.append(action)
            return "ok"

        return [patch.multiple("windows", clients=desktop.clients, active_window=desktop.active_window,
                               focus=desktop.focus, make_fullscreen=desktop.make_fullscreen, close=desktop.close),
                patch("doorbell.open_camera", side_effect=desktop.open_camera),
                patch("doorbell.media_playing", return_value=playing),
                patch("doorbell.media", side_effect=media)]

    def run_show(self, desktop, power="on", clock=None, playing=False):
        clock = clock or iter([100.0, 104.0]).__next__
        patches = self.desktop_patches(desktop, playing)
        for p in patches:
            p.start()
        try:
            with patch("bobtv.tv_power", return_value=power) as tv_power, \
                 patch("bobtv.tv_wake") as wake, patch("bobtv.tv_standby") as standby:
                result = doorbell.show(self.config, self.state, sleep=desktop.sleep, clock=clock)
        finally:
            for p in reversed(patches):
                p.stop()
        return result, wake, standby, tv_power

    def test_camera_goes_in_front_then_the_show_comes_back(self):
        desktop = FakeDesktop()
        result, wake, standby, _ = self.run_show(desktop)
        self.assertEqual(desktop.log[0], ("open", "http://127.0.0.1:8123/bobtv-home/doorbell"))
        self.assertIn(("focus", CAMERA), desktop.log)
        self.assertIn(("close", CAMERA), desktop.log)
        # The camera closes before the show is refocused, and only the camera is closed.
        self.assertLess(desktop.log.index(("close", CAMERA)), desktop.log.index(("focus", SHOW)))
        self.assertEqual([e for e in desktop.log if e[0] == "close"], [("close", CAMERA)])
        self.assertIn(SHOW, desktop.windows)
        self.assertEqual(desktop.windows[SHOW]["fullscreen"], 2, "a fullscreen show gets fullscreen back")
        wake.assert_called_once()
        standby.assert_not_called()
        self.assertEqual(result, "Showed the front door.")

    def test_display_time_counts_from_when_the_camera_is_up(self):
        desktop = FakeDesktop()
        # The camera comes up at t=100; the TV steps finish at t=104; 30 seconds total.
        self.run_show(desktop, clock=iter([100.0, 104.0]).__next__)
        self.assertIn(("sleep", 26), desktop.log)

    def test_a_window_that_was_not_fullscreen_is_not_made_fullscreen(self):
        desktop = FakeDesktop(active=HOME)
        self.run_show(desktop)
        self.assertIn(("focus", HOME), desktop.log)
        self.assertNotIn(("fullscreen", HOME), desktop.log)

    def test_a_tv_that_was_off_goes_back_to_standby(self):
        desktop = FakeDesktop()
        result, wake, standby, _ = self.run_show(desktop, power="standby")
        wake.assert_called_once()
        standby.assert_called_once()
        self.assertIn("standby", result)

    def test_a_tv_that_will_not_say_is_never_turned_off(self):
        desktop = FakeDesktop()
        _, _, standby, _ = self.run_show(desktop, power=None)
        standby.assert_not_called()

    def test_closing_the_camera_by_hand_leaves_everything_alone(self):
        desktop = FakeDesktop(user_closes_camera=True)
        result, _, standby, _ = self.run_show(desktop, power="standby")
        self.assertNotIn(("close", CAMERA), desktop.log)
        self.assertNotIn(("focus", SHOW), desktop.log)
        standby.assert_not_called()
        self.assertIn("by hand", result)

    def test_a_camera_that_never_appears_is_an_error_and_closes_nothing(self):
        desktop = FakeDesktop(camera_appears=False)
        with self.assertRaises(bobtv.ActionError):
            self.run_show(desktop)
        self.assertFalse([e for e in desktop.log if e[0] == "close"])

    def test_a_tv_that_will_not_answer_still_shows_the_camera(self):
        desktop = FakeDesktop()
        patches = self.desktop_patches(desktop)
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(patches)])
        with patch("bobtv.tv_power", side_effect=bobtv.ActionError("no adapter")), \
             patch("bobtv.tv_wake", side_effect=bobtv.ActionError("no adapter")), \
             patch("bobtv.tv_standby") as standby:
            result = doorbell.show(self.config, self.state, sleep=desktop.sleep,
                                   clock=iter([100.0, 101.0]).__next__)
        self.assertIn(("focus", CAMERA), desktop.log)
        self.assertIn(("close", CAMERA), desktop.log)
        standby.assert_not_called()
        self.assertEqual(result, "Showed the front door.")

    def test_tv_control_off_skips_the_tv_but_still_shows(self):
        self.config["tv"]["enabled"] = False
        desktop = FakeDesktop()
        _, wake, standby, tv_power = self.run_show(desktop)
        wake.assert_not_called()
        tv_power.assert_not_called()
        self.assertIn(("close", CAMERA), desktop.log)

    def test_a_second_ring_while_showing_does_nothing(self):
        desktop = FakeDesktop()
        import fcntl
        self.state.mkdir(exist_ok=True)
        with (self.state / "doorbell.lock").open("a+") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            result, wake, _, _ = self.run_show(desktop)
        self.assertEqual(desktop.log, [])
        wake.assert_not_called()
        self.assertIn("already", result)

    def test_disabled_refuses(self):
        self.config["doorbell"]["enabled"] = False
        with self.assertRaises(bobtv.ActionError):
            doorbell.show(self.config, self.state)

    def test_a_playing_show_is_paused_then_resumed(self):
        desktop = FakeDesktop()
        result, _, _, _ = self.run_show(desktop, playing=True)
        self.assertEqual(self.media_calls, ["pause", "play"])
        self.assertIn("resumed", result)

    def test_nothing_playing_means_nothing_resumed(self):
        desktop = FakeDesktop()
        self.run_show(desktop, playing=False)
        self.assertEqual(self.media_calls, [])

    def test_playback_resumes_even_when_the_camera_never_appears(self):
        desktop = FakeDesktop(camera_appears=False)
        with self.assertRaises(bobtv.ActionError):
            self.run_show(desktop, playing=True)
        self.assertEqual(self.media_calls, ["pause", "play"])

    def test_the_camera_is_remembered_while_up_and_forgotten_after(self):
        desktop = FakeDesktop()
        seen = []
        original = desktop.sleep
        marker = self.state / "doorbell-window"

        def sleep(seconds):
            seen.append(marker.read_text() if marker.exists() else None)
            original(seconds)

        desktop.sleep = sleep
        self.run_show(desktop)
        self.assertIn(CAMERA, seen)
        self.assertFalse(marker.exists())


class AddressTests(unittest.TestCase):
    """Window addresses are spliced into Hyprland commands, so only real ones pass."""

    @patch("windows.hyprctl")
    def test_real_addresses_pass(self, hyprctl):
        windows.focus("0x64e29a7619a0")
        windows.close("0x64e29a7619a0")
        self.assertIn('address:0x64e29a7619a0', hyprctl.call_args.args[1])

    @patch("windows.hyprctl")
    def test_anything_else_is_refused(self, hyprctl):
        for bad in ('0x1" }) hl.exec_cmd("rm', "", None, "cafe", "0xZZ"):
            with self.subTest(bad=bad), self.assertRaises(bobtv.ActionError):
                windows.close(bad)
        hyprctl.assert_not_called()


class RememberTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "show-window"

    def test_close_remembered_closes_only_that_window_and_forgets_it(self):
        windows.remember(self.path, SHOW)
        with patch("windows.clients", return_value={SHOW: {}, HOME: {}}), patch("windows.close") as close:
            self.assertTrue(windows.close_remembered(self.path))
        close.assert_called_once_with(SHOW)
        self.assertFalse(self.path.exists())

    def test_a_window_already_gone_is_just_forgotten(self):
        windows.remember(self.path, SHOW)
        with patch("windows.clients", return_value={HOME: {}}), patch("windows.close") as close:
            self.assertFalse(windows.close_remembered(self.path))
        close.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_nothing_remembered_closes_nothing(self):
        with patch("windows.close") as close:
            self.assertFalse(windows.close_remembered(self.path))
        close.assert_not_called()

    def test_only_real_addresses_are_remembered(self):
        with self.assertRaises(bobtv.ActionError):
            windows.remember(self.path, "not-an-address")


class MediaTests(unittest.TestCase):
    def test_playing_is_read_from_omarchy_status(self):
        with patch("doorbell.media", return_value='{"hasPlayer": true, "playing": true}'):
            self.assertTrue(doorbell.media_playing())
        for status in ('{"playing": false}', None, "not json", '{"playing": "yes"}'):
            with self.subTest(status=status), patch("doorbell.media", return_value=status):
                self.assertFalse(doorbell.media_playing())

    def test_pause_only_when_something_plays(self):
        with patch("doorbell.media_playing", return_value=False), patch("doorbell.media") as media:
            self.assertFalse(doorbell.pause_playback())
        media.assert_not_called()
        with patch("doorbell.media_playing", return_value=True), patch("doorbell.media", return_value="ok") as media:
            self.assertTrue(doorbell.pause_playback())
        media.assert_called_once_with("pause")
        with patch("doorbell.media_playing", return_value=True), patch("doorbell.media", return_value="unhandled"):
            self.assertFalse(doorbell.pause_playback())


class SecretTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "doorbell.json"

    def test_a_good_secret_loads(self):
        self.path.write_text(json.dumps({"secret": "s" * 43}))
        self.assertEqual(doorbell.load_secret(self.path), "s" * 43)

    def test_missing_short_or_broken_secrets_are_none(self):
        self.assertIsNone(doorbell.load_secret(self.path))
        for text in ('{"secret": "short"}', "not json", "[]", '{"secret": 12345}'):
            with self.subTest(text=text):
                self.path.write_text(text)
                self.assertIsNone(doorbell.load_secret(self.path))


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.base = json.loads(Path(bobtv.__file__).with_name("services.json").read_text())
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def write(self, bell):
        config = dict(self.base)
        if bell is None:
            config.pop("doorbell", None)
        else:
            config["doorbell"] = bell
        path = Path(self.temp.name) / "services.json"
        path.write_text(json.dumps(config))
        return path

    def test_shipped_config_enables_the_doorbell(self):
        config = bobtv.load_config(Path(bobtv.__file__).with_name("services.json"))
        self.assertTrue(bobtv.doorbell_settings(config)["enabled"])

    def test_missing_section_is_off(self):
        config = bobtv.load_config(self.write(None))
        self.assertFalse(bobtv.doorbell_settings(config)["enabled"])

    def test_only_a_local_home_assistant_page_may_open(self):
        for url in ("https://evil.example/", "http://127.0.0.1:8765/", "http://127.0.0.1:8123/../../x",
                    "http://127.0.0.1:8123/a b", "file:///etc/passwd", 7):
            with self.subTest(url=url), self.assertRaises(bobtv.ActionError):
                bobtv.load_config(self.write({"url": url}))
        bobtv.load_config(self.write({"url": "http://127.0.0.1:8123/bobtv-home/doorbell"}))

    def test_bad_settings_are_rejected(self):
        for bell in ({"enabled": "yes"}, {"seconds": 1}, {"seconds": 301}, {"seconds": True},
                     {"typo": 1}, []):
            with self.subTest(bell=bell), self.assertRaises(bobtv.ActionError):
                bobtv.load_config(self.write(bell))


class EndpointTests(unittest.TestCase):
    SECRET = "x" * 43

    def setUp(self):
        with patch("home_server._tailscale_ips", return_value=[]):
            self.server = home_server.make_server(Path("services.json"), port=0)
        self.base = "http://127.0.0.1:" + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        secret = patch("doorbell.load_secret", return_value=self.SECRET)
        self.addCleanup(secret.stop)
        secret.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def ring(self, secret=None, headers=None):
        extra = {"X-BobTV-Doorbell": self.SECRET if secret is None else secret}
        extra.update(headers or {})
        return urlopen(Request(self.base + "/api/doorbell", data=b"", headers=extra, method="POST"))

    @patch("doorbell.run_quietly")
    def test_the_right_secret_shows_the_door_in_the_background(self, run):
        with self.ring() as response:
            self.assertEqual(response.status, 202)
        for _ in range(50):
            if run.called:
                break
            threading.Event().wait(0.02)
        run.assert_called_once()

    @patch("doorbell.run_quietly")
    def test_a_wrong_or_missing_secret_is_refused(self, run):
        for secret in ("wrong", ""):
            with self.subTest(secret=secret), self.assertRaises(HTTPError) as error:
                self.ring(secret=secret)
            self.assertEqual(error.exception.code, 403)
        run.assert_not_called()

    @patch("doorbell.run_quietly")
    def test_no_secret_configured_refuses_everything(self, run):
        with patch("doorbell.load_secret", return_value=None), self.assertRaises(HTTPError) as error:
            self.ring()
        self.assertEqual(error.exception.code, 403)
        run.assert_not_called()

    @patch("doorbell.run_quietly")
    def test_a_client_off_this_machine_is_refused_even_with_the_secret(self, run):
        # Same technique as test_home: make the caller look like a tailnet device.
        tailnet = ipaddress.ip_address("100.73.27.12")
        with patch("home_server.ipaddress.ip_address", return_value=tailnet), self.assertRaises(HTTPError) as error:
            self.ring()
        self.assertEqual(error.exception.code, 403)
        run.assert_not_called()

    @patch("doorbell.run_quietly")
    def test_the_launch_token_is_not_needed_and_does_not_help(self, run):
        # A web page's launch token is not the doorbell secret.
        with urlopen(self.base + "/api/catalog") as response:
            token = json.load(response)["token"]
        with self.assertRaises(HTTPError) as error:
            self.ring(secret="", headers={"X-BobTV-Token": token, "Origin": self.base})
        self.assertEqual(error.exception.code, 403)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
