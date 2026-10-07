"""Workflow choices are ordered, explicit and independent of display filters."""
import pytest

from Imervue.library.photo_workflow import PhotoWorkflow


def test_empty_single_duplicates_cross_folder_add_and_reject_choices():
    flow = PhotoWorkflow()
    assert flow.targets() == flow.visible_paths() == ()
    flow.add(["a/x.jpg", "a/x.jpg", ""], {"a/x.jpg": "pick"})
    flow.choose("a/x.jpg", False)
    flow.add(["a/x.jpg", "b/x.jpg", "c/x.jpg"], {"b/x.jpg": "reject"})
    assert flow.paths == ("a/x.jpg", "b/x.jpg", "c/x.jpg")
    assert flow.targets() == ("c/x.jpg",)
    flow.choose("b/x.jpg", True)
    assert flow.targets() == ("c/x.jpg",)
    flow.mark(["b/x.jpg"], "pick")
    assert flow.targets() == ("b/x.jpg", "c/x.jpg")


def test_filter_and_back_preserve_order_hidden_choices_and_presets():
    flow = PhotoWorkflow()
    flow.add(["first", "second", "third"])
    flow.mark(["first"], "pick")
    flow.mark(["second"], "reject")
    flow.develop_preset, flow.export_preset = "Portrait", "web_1600"
    flow.set_filter("pick")
    assert flow.visible_paths() == ("first",)
    assert flow.targets() == ("first", "third")
    flow.set_filter("all")
    assert flow.visible_paths() == flow.paths
    assert flow.targets() == ("first", "third")
    assert (flow.develop_preset, flow.export_preset) == ("Portrait", "web_1600")


@pytest.mark.parametrize("operation", ["add", "choose", "mark", "filter", "unknown_mark"])
def test_invalid_operations_are_atomic(operation):
    flow = PhotoWorkflow()
    flow.add(["first"])
    with pytest.raises((ValueError, KeyError)):
        if operation == "add":
            flow.add(["second"], {"second": "bad"})
        elif operation == "choose":
            flow.choose("missing", True)
        elif operation == "mark":
            flow.mark(["first"], "bad")
        elif operation == "filter":
            flow.set_filter("bad")
        else:
            flow.mark(["first", "missing"], "reject")
    assert flow.paths == flow.targets() == ("first",)
    assert flow.states == {"first": "unflagged"} and flow.filter == "all"
