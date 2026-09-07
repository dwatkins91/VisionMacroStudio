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
from app.automation.debugger import analyze_step, step_needs_detection  # noqa: E402
from app.automation.macro_io import (  # noqa: E402
    MacroFormatError,
    export_macro_file,
    has_coordinate_steps,
    import_macro_file,
    referenced_objects,
    unique_macro_name,
)
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
                "steps": [
                    {
                        "enabled": True,
                        "action": "CLICK_FIRST_AVAILABLE",
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
                ],
            }
        )
        project.save()
        reopened = ProjectManager()
        reopened.open(project.project_file)
        saved_macro = reopened.data["macros"][0]
        assert saved_macro["time_limit_minutes"] == 12.5
        assert saved_macro["steps"][0]["objects"] == ["Start_Button", "Target"]
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
        macro_file = root / "shared_macro.vmsmacro.json"
        export_macro_file(
            macro_file,
            saved_macro,
            "test-version",
            [{"left": 0, "top": 0, "width": 1920, "height": 1080}],
        )
        shared_macro, metadata = import_macro_file(macro_file)
        assert shared_macro == saved_macro
        assert metadata["app_version"] == "test-version"
        assert metadata["screen_layout"][0]["width"] == 1920
        assert referenced_objects(shared_macro) == ["Start_Button", "Target"]
        assert not has_coordinate_steps(shared_macro)
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
