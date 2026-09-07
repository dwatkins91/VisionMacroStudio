"""Dependency-light persistence and YOLO-export smoke test.

Run from the project root with: python tests/smoke_test.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import sys
from types import ModuleType

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.projects import ProjectManager  # noqa: E402
from app.automation.control import (  # noqa: E402
    destination_steps,
    object_names,
    randomized_point,
    randomized_seconds,
)
from app.automation.coordinates import (  # noqa: E402
    absolute_region_from_normalized,
    find_window_by_title,
    normalized_region_from_absolute,
    point_from_relative,
    relative_point,
    resolve_step_coordinate,
)
from app.automation.debugger import analyze_step, step_needs_detection  # noqa: E402
from app.automation.macro_io import (  # noqa: E402
    MacroFormatError,
    delete_step_preserving_destinations,
    duplicate_step_preserving_destinations,
    export_macro_file,
    has_absolute_coordinate_steps,
    has_coordinate_steps,
    import_macro_file,
    insert_step_preserving_destinations,
    referenced_objects,
    reorder_steps_preserving_destinations,
    unique_macro_name,
)
from app.automation.validator import analyze_macro, issue_counts  # noqa: E402
from app.vision.dataset import automatic_split, class_counts, export_yolo  # noqa: E402
from app.vision.model_manager import (  # noqa: E402
    accept_model,
    delete_model,
    register_model,
    training_source_label,
)
from app.vision.detector import Detector, class_name_key, to_ultralytics_source  # noqa: E402


def exercise_stability_engine() -> None:
    """Exercise stability state without requiring GUI/capture packages in CI."""

    if importlib.util.find_spec("PySide6") is None:
        pyside = ModuleType("PySide6")
        qtcore = ModuleType("PySide6.QtCore")

        class TestSignal:
            def __init__(self, *args) -> None:
                self.values = []

            def emit(self, *args) -> None:
                self.values.append(args)

        class TestQObject:
            pass

        def test_slot(*args, **kwargs):
            return lambda function: function

        qtcore.QObject = TestQObject
        qtcore.Signal = TestSignal
        qtcore.Slot = test_slot
        pyside.QtCore = qtcore
        sys.modules["PySide6"] = pyside
        sys.modules["PySide6.QtCore"] = qtcore
    if importlib.util.find_spec("mss") is None:
        mss_module = ModuleType("mss")
        mss_module.mss = lambda: None
        sys.modules["mss"] = mss_module

    from app.automation.engine import MacroWorker

    detection = {
        "class_name": "Target",
        "confidence": 0.91,
        "bbox": [100, 100, 40, 40],
    }
    worker = MacroWorker({"name": "Stability Test", "steps": []}, None)
    worker._interruptible_sleep = lambda _seconds: False
    sequence = iter([detection, None, detection, detection])

    def fake_detect(*_args, **_kwargs):
        return next(sequence), (0, 0), 0

    worker._detect = fake_detect
    found, _origin = worker._wait_for(
        None,
        {
            "object": "Target",
            "timeout": 0,
            "required_consecutive_detections": 2,
            "max_detection_attempts": 10,
        },
        True,
    )
    assert found is detection

    worker = MacroWorker({"name": "Attempt Test", "steps": []}, None)
    worker._interruptible_sleep = lambda _seconds: False
    checks = {"count": 0}

    def never_detect(*_args, **_kwargs):
        checks["count"] += 1
        return None, (0, 0), 0

    worker._detect = never_detect
    found, _origin = worker._wait_for(
        None,
        {
            "object": "Target",
            "timeout": 0,
            "required_consecutive_detections": 1,
            "max_detection_attempts": 3,
            "on_timeout": "continue",
        },
        True,
    )
    assert found is None and checks["count"] == 3

    worker = MacroWorker({"name": "Cooldown Test", "steps": []}, None)
    worker._remember_detection_click(detection, (0, 0), "Target", 5)
    nearby = dict(detection)
    far_away = dict(detection, bbox=[500, 500, 40, 40])
    allowed, ignored = worker._filter_recent_detection_clicks(
        [nearby, far_away], (0, 0), True
    )
    assert ignored == 1 and allowed == [far_away]

    from app.capture import grabber

    requested_bounds = []

    class FakeRaw:
        def __init__(self, width: int, height: int) -> None:
            self.size = (width, height)
            self.bgra = bytes((0, 0, 0, 255)) * width * height

    class FakeCapture:
        monitors = [
            {"left": 0, "top": 0, "width": 300, "height": 120},
            {"left": 100, "top": 20, "width": 200, "height": 100},
        ]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def grab(self, bounds):
            requested_bounds.append(dict(bounds))
            return FakeRaw(int(bounds["width"]), int(bounds["height"]))

    original_mss = grabber.mss.mss
    try:
        grabber.mss.mss = FakeCapture
        region_grab = grabber.grab_screen(
            1, {"x": 0.25, "y": 0.2, "width": 0.5, "height": 0.5}
        )
    finally:
        grabber.mss.mss = original_mss
    assert requested_bounds[-1] == {
        "left": 150,
        "top": 40,
        "width": 100,
        "height": 50,
    }
    assert (region_grab.left, region_grab.top) == (150, 40)
    assert region_grab.image.size == (100, 50)
    assert region_grab.source_bounds == {
        "left": 100,
        "top": 20,
        "width": 200,
        "height": 100,
    }


def main() -> None:
    exercise_stability_engine()
    assert object_names("Primary, Fallback") == ["Primary", "Fallback"]
    assert object_names([" Message_A ", "Message_B"]) == [
        "Message_A",
        "Message_B",
    ]
    assert destination_steps("3, 0, 1") == [3, 0, 1]
    assert randomized_point(400, 300, 0) == (400, 300)
    for _ in range(100):
        offset_x, offset_y = randomized_point(400, 300, 7)
        assert 393 <= offset_x <= 407
        assert 293 <= offset_y <= 307
        wait_seconds = randomized_seconds(6, 9)
        assert 6 <= wait_seconds <= 9
    assert randomized_seconds(7, 7) == 7
    watch_bounds = {"left": 1920, "top": 0, "width": 1920, "height": 1080}
    assert relative_point(2400, 540, watch_bounds) == (0.25, 0.5)
    assert point_from_relative(
        1,
        1,
        {"left": -1920, "top": 0, "width": 1920, "height": 1080},
    ) == (-1, 1079)
    scaled_x, scaled_y, scaled_basis = resolve_step_coordinate(
        {
            "coordinate_mode": "watch_relative",
            "relative_x": 0.25,
            "relative_y": 0.5,
        },
        {"left": 0, "top": 0, "width": 2560, "height": 1440},
    )
    assert (scaled_x, scaled_y) == (640, 720)
    assert "scaled" in scaled_basis
    window_x, window_y, window_basis = resolve_step_coordinate(
        {
            "coordinate_mode": "window_relative",
            "relative_x": 0.5,
            "relative_y": 0.25,
            "window_title": "Target App",
        },
        watch_bounds,
        window_finder=lambda _title: {
            "title": "Target App",
            "left": 100,
            "top": 200,
            "width": 800,
            "height": 600,
        },
    )
    assert (window_x, window_y) == (500, 350)
    assert "Target App" in window_basis
    import app.automation.coordinates as coordinate_tools

    original_window_records = coordinate_tools._window_records
    try:
        coordinate_tools._window_records = lambda: [
            {
                "title": "Current Document - Target App",
                "class_name": "TargetWindowClass",
                "left": 0,
                "top": 0,
                "width": 800,
                "height": 600,
            }
        ]
        assert (
            find_window_by_title("Old Document - Target App", "TargetWindowClass")
            is not None
        )
    finally:
        coordinate_tools._window_records = original_window_records
    normalized_region = normalized_region_from_absolute(
        {"left": 2400, "top": 270, "width": 960, "height": 540},
        watch_bounds,
    )
    assert normalized_region == {
        "x": 0.25,
        "y": 0.25,
        "width": 0.5,
        "height": 0.5,
    }
    assert absolute_region_from_normalized(
        normalized_region,
        {"left": 0, "top": 0, "width": 2560, "height": 1440},
    ) == {"left": 640, "top": 360, "width": 1280, "height": 720}

    builder_steps = [
        {
            "enabled": True,
            "action": "WAIT_FOR_ANY_OBJECT",
            "objects": ["Primary", "Fallback"],
            "target_steps": [2, 4],
            "confidence": 0.7,
            "timeout": 5,
        },
        {"enabled": True, "action": "SECTION", "name": "Work"},
        {"enabled": True, "action": "WAIT", "duration": 1},
        {"enabled": True, "action": "GOTO_STEP", "target_step": 1},
    ]
    reordered = reorder_steps_preserving_destinations(builder_steps, 3, 1)
    assert reordered[0]["target_steps"] == [3, 2]
    assert reordered[1]["action"] == "GOTO_STEP"
    assert reordered[1]["target_step"] == 1
    duplicated = duplicate_step_preserving_destinations(builder_steps, 1)
    assert duplicated[0]["target_steps"] == [2, 5]
    assert duplicated[2]["action"] == "SECTION"
    duplicated_branch = duplicate_step_preserving_destinations(builder_steps, 0)
    assert duplicated_branch[0]["target_steps"] == [3, 5]
    assert duplicated_branch[1]["target_steps"] == [3, 5]
    inserted = insert_step_preserving_destinations(
        builder_steps,
        1,
        {"enabled": True, "action": "SECTION", "name": "Inserted"},
    )
    assert inserted[0]["target_steps"] == [3, 5]
    deleted = delete_step_preserving_destinations(builder_steps, 1)
    assert deleted[0]["target_steps"] == [4, 3]

    validation_macro = {
        "name": "Validation Check",
        "steps": [
            {"enabled": True, "action": "GOTO_STEP", "target_step": 2},
            {"enabled": False, "action": "WAIT", "duration": 1},
            {
                "enabled": True,
                "action": "WAIT_FOR_OBJECT",
                "object": "Missing_Class",
                "confidence": 0.7,
                "timeout": 0,
                "timeout_max": 0,
                "max_detection_attempts": 0,
            },
        ],
    }
    validation_issues = analyze_macro(validation_macro, ["Known_Class"])
    validation_codes = {issue.code for issue in validation_issues}
    assert "disabled_destination" in validation_codes
    assert "missing_class" in validation_codes
    assert "unbounded_wait" in validation_codes
    assert issue_counts(validation_issues)["error"] >= 1
    closed_loop_issues = analyze_macro(
        {
            "name": "Closed Loop",
            "steps": [
                {"enabled": True, "action": "GOTO_STEP", "target_step": 1}
            ],
        },
        [],
    )
    assert any(issue.code == "closed_loop" for issue in closed_loop_issues)
    bounded_loop_issues = analyze_macro(
        {
            "name": "Bounded Loop",
            "time_limit_minutes": 10,
            "steps": [
                {"enabled": True, "action": "GOTO_STEP", "target_step": 1}
            ],
        },
        [],
    )
    assert not any(issue.code == "closed_loop" for issue in bounded_loop_issues)
    assert not analyze_macro(
        {
            "name": "Organized Macro",
            "steps": [
                {
                    "enabled": True,
                    "action": "SECTION",
                    "name": "Gathering",
                    "comment": "Visual organization only",
                },
                {"enabled": True, "action": "STOP", "name": "Finished"},
            ],
        },
        [],
    )
    section_report = analyze_step(
        {
            "enabled": True,
            "action": "SECTION",
            "name": "Banking",
            "comment": "Organization only",
        },
        2,
        5,
    )
    assert "section divider" in section_report["decision"]
    assert any("Organization only" in detail for detail in section_report["details"])
    unnamed_section_issues = analyze_macro(
        {"name": "Unnamed Section", "steps": [{"action": "SECTION"}]},
        [],
    )
    assert any(
        issue.code == "format" and "section title" in issue.message
        for issue in unnamed_section_issues
    )
    try:
        destination_steps("three")
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid destination text should be rejected")
    rgb_pixel = Image.new("RGB", (1, 1), (10, 20, 30))
    converted = to_ultralytics_source(rgb_pixel)
    assert converted[0, 0].tolist() == [30, 20, 10]
    detections = [
        {"class_name": "Time_Sprite_Message", "confidence": 0.42, "bbox": [0, 0, 1, 1]}
    ]
    assert class_name_key(" time-sprite message ") == "time_sprite_message"
    assert Detector.best(detections, "time_sprite_message") is detections[0]
    assert Detector.best(detections, "TIME SPRITE MESSAGE", 0.40) is detections[0]
    assert Detector.best(detections, "time_sprite_message", 0.50) is None
    branch_detections = [
        {
            "class_name": "Remains",
            "confidence": 0.93,
            "bbox": [100, 120, 60, 40],
        },
        {
            "class_name": "Remains_Sprite",
            "confidence": 0.81,
            "bbox": [240, 180, 80, 60],
        },
    ]
    branch_step = {
        "action": "WAIT_FOR_ANY_OBJECT",
        "objects": ["Remains_Sprite", "Remains"],
        "target_steps": [2, 4],
        "confidence": 0.70,
        "timeout": 10,
        "required_consecutive_detections": 3,
        "max_detection_attempts": 40,
    }
    branch_report = analyze_step(branch_step, 0, 4, branch_detections)
    assert step_needs_detection(branch_step)
    assert "Remains_Sprite" in branch_report["decision"]
    assert "step 2" in branch_report["decision"]
    assert branch_report["decision"].startswith("FRAME MATCH 1 OF 3")
    assert any("at most 40" in detail for detail in branch_report["details"])
    low_report = analyze_step(
        {"action": "WAIT_FOR_OBJECT", "object": "Time_Sprite", "confidence": 0.9},
        2,
        4,
        [{"class_name": "Time_Sprite", "confidence": 0.84, "bbox": [1, 2, 3, 4]}],
    )
    assert low_report["decision"].startswith("WAIT")
    assert "84%" in low_report["decision"] and "90%" in low_report["decision"]
    coordinate_report = analyze_step(
        {"action": "RIGHT_CLICK", "x": 640, "y": 480, "random_offset": 4},
        4,
        5,
    )
    assert coordinate_report["marker"] == (640, 480)
    assert "No live action" not in coordinate_report["decision"]
    portable_coordinate_report = analyze_step(
        {
            "action": "CLICK",
            "coordinate_mode": "watch_relative",
            "relative_x": 0.75,
            "relative_y": 0.25,
        },
        4,
        5,
        watch_bounds={"left": 0, "top": 0, "width": 2000, "height": 1000},
    )
    assert portable_coordinate_report["marker"] == (1500, 250)
    assert "scaled" in portable_coordinate_report["decision"]
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        project = ProjectManager()
        project.create(root, "Smoke Project")
        for index in range(6):
            image = Image.new("RGB", (320, 200), (25 + index * 10, 40, 70))
            annotations = [
                {
                    "class_name": "Start_Button",
                    "bbox": [20 + index * 8, 30, 80, 40],
                }
            ]
            if index % 2 == 0:
                annotations.append({"class_name": "Enemy", "bbox": [180, 80, 45, 50]})
            project.add_screenshot(image, annotations, (0, 0))
        automatic_split(project, 80, seed=1)
        dataset_yaml = export_yolo(project)
        assert dataset_yaml.exists()
        assert class_counts(project)["Start_Button"] == 6
        assert any(s["split"] == "val" for s in project.data["screenshots"])
        project.rename_class("Enemy", "Target")
        assert class_counts(project)["Target"] == 3
        project.data["macros"].append(
            {
                "name": "Conditional Smoke Macro",
                "time_limit_minutes": 12.5,
                "detection_region": normalized_region,
                "steps": [
                    {
                        "enabled": True,
                        "action": "CLICK_FIRST_AVAILABLE",
                        "name": "Choose target",
                        "comment": "Primary target first, then fallback.",
                        "objects": ["Start_Button", "Target"],
                        "confidence": 0.3,
                        "required_consecutive_detections": 2,
                        "max_detection_attempts": 25,
                        "click_cooldown_seconds": 4,
                        "wait_after_click_until_disappears": True,
                        "post_click_disappear_timeout": 6,
                    },
                    {
                        "enabled": True,
                        "action": "WAIT_FOR_ANY_OBJECT",
                        "objects": ["Start_Button", "Target"],
                        "target_steps": [0, 1],
                        "confidence": 0.3,
                    },
                    {"enabled": True, "action": "GOTO_STEP", "target_step": 1},
                    {
                        "enabled": True,
                        "action": "RIGHT_CLICK_OBJECT",
                        "object": "Target",
                        "timeout": 8,
                        "timeout_max": 12,
                    },
                    {
                        "enabled": True,
                        "action": "WAIT",
                        "duration": 2,
                        "duration_max": 4,
                    },
                    {
                        "enabled": True,
                        "action": "CLICK",
                        "coordinate_mode": "watch_relative",
                        "relative_x": 0.25,
                        "relative_y": 0.75,
                        "x": 2400,
                        "y": 810,
                    },
                ],
            }
        )
        project.save()
        reopened = ProjectManager()
        reopened.open(project.project_file)
        saved_macro = reopened.data["macros"][0]
        assert saved_macro["time_limit_minutes"] == 12.5
        assert saved_macro["detection_region"] == normalized_region
        assert saved_macro["steps"][0]["objects"] == ["Start_Button", "Target"]
        assert saved_macro["steps"][0]["name"] == "Choose target"
        assert saved_macro["steps"][0]["comment"].startswith("Primary target")
        assert saved_macro["steps"][0]["required_consecutive_detections"] == 2
        assert saved_macro["steps"][0]["max_detection_attempts"] == 25
        assert saved_macro["steps"][0]["click_cooldown_seconds"] == 4
        assert saved_macro["steps"][0]["wait_after_click_until_disappears"] is True
        assert saved_macro["steps"][0]["post_click_disappear_timeout"] == 6
        assert saved_macro["steps"][1]["target_steps"] == [0, 1]
        assert saved_macro["steps"][2]["target_step"] == 1
        assert saved_macro["steps"][3]["action"] == "RIGHT_CLICK_OBJECT"
        assert saved_macro["steps"][3]["timeout_max"] == 12
        assert saved_macro["steps"][4]["duration_max"] == 4
        assert saved_macro["steps"][5]["coordinate_mode"] == "watch_relative"
        macro_file = root / "shared_macro.vmsmacro.json"
        export_macro_file(
            macro_file,
            saved_macro,
            "test-version",
            [{"left": 0, "top": 0, "width": 1920, "height": 1080}],
        )
        shared_macro, metadata = import_macro_file(macro_file)
        assert shared_macro == saved_macro
        assert metadata["format_version"] == 2
        assert metadata["app_version"] == "test-version"
        assert metadata["screen_layout"][0]["width"] == 1920
        assert referenced_objects(shared_macro) == ["Start_Button", "Target"]
        assert has_coordinate_steps(shared_macro)
        assert not has_absolute_coordinate_steps(shared_macro)
        assert unique_macro_name("Test", ["Test", "Test (Imported)"]) == (
            "Test (Imported 2)"
        )
        raw_coordinate_macro = root / "raw_coordinate_macro.json"
        raw_coordinate_macro.write_text(
            '{"name":"Coordinate","steps":[{"action":"CLICK","x":12,"y":34}]}',
            encoding="utf-8",
        )
        coordinate_macro, _metadata = import_macro_file(raw_coordinate_macro)
        assert has_coordinate_steps(coordinate_macro)
        assert has_absolute_coordinate_steps(coordinate_macro)
        legacy_macro_file = root / "legacy_v1_macro.json"
        legacy_macro_file.write_text(
            '{"format":"vision-macro-studio/macro","format_version":1,'
            '"macro":{"name":"Legacy","steps":[{"action":"CLICK",'
            '"x":12,"y":34}]}}',
            encoding="utf-8",
        )
        legacy_macro, legacy_metadata = import_macro_file(legacy_macro_file)
        assert legacy_macro["name"] == "Legacy"
        assert legacy_metadata["format_version"] == 1
        invalid_macro = root / "invalid_macro.json"
        invalid_macro.write_text(
            '{"name":"Invalid","steps":[{"action":"NOT_REAL"}]}',
            encoding="utf-8",
        )
        try:
            import_macro_file(invalid_macro)
        except MacroFormatError:
            pass
        else:
            raise AssertionError("Unsupported imported actions should be rejected")
        invalid_stability_macro = root / "invalid_stability_macro.json"
        invalid_stability_macro.write_text(
            '{"name":"Invalid Stability","steps":[{"action":"WAIT_FOR_OBJECT",'
            '"object":"Target","required_consecutive_detections":0}]}',
            encoding="utf-8",
        )
        try:
            import_macro_file(invalid_stability_macro)
        except MacroFormatError:
            pass
        else:
            raise AssertionError("Invalid stability limits should be rejected")
        invalid_region_macro = root / "invalid_region_macro.json"
        invalid_region_macro.write_text(
            '{"name":"Invalid Region","detection_region":'
            '{"x":0.8,"y":0.2,"width":0.4,"height":0.5},"steps":[]}',
            encoding="utf-8",
        )
        try:
            import_macro_file(invalid_region_macro)
        except MacroFormatError:
            pass
        else:
            raise AssertionError("Out-of-bounds detection regions should be rejected")
        dummy_model = project.path("models/Smoke_Model_v1.pt")
        dummy_model.write_bytes(b"test model placeholder")
        first_model = register_model(
            project,
            "Smoke_Model_v1",
            "models/Smoke_Model_v1.pt",
            list(project.data["classes"]),
            {"mAP50": 0.75},
            {
                "source": {"type": "pretrained", "model_file": "yolo11n.pt"},
                "epochs": 50,
            },
        )
        assert training_source_label(first_model) == "yolo11n.pt"
        assert first_model["training"]["epochs"] == 50
        accept_model(project, "Smoke_Model_v1")
        assert project.data["models"][0]["accepted"] is True
        continued_model = {
            "training": {
                "source": {
                    "type": "project_model",
                    "model_id": "Smoke_Model_v1",
                    "name": "Smoke_Model_v1",
                }
            }
        }
        assert training_source_label(continued_model) == "Smoke_Model_v1"
        assert training_source_label({}) == "Pretrained base"
        delete_model(project, "Smoke_Model_v1")
        assert not project.data["models"] and not dummy_model.exists()
        exported = project.export_zip(root / "smoke_project.zip")
        assert exported.exists() and exported.stat().st_size > 0
        imported_parent = root / "imported"
        imported_parent.mkdir()
        imported = ProjectManager()
        imported.import_zip(exported, imported_parent)
        assert imported.data["name"] == "Smoke Project"
        assert len(imported.data["screenshots"]) == 6
    print("Vision Macro Studio persistence/dataset smoke test: PASS")


if __name__ == "__main__":
    main()
