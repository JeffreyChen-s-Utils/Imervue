"""Tests for the VTube Studio Public API protocol handler.

Exercises ``VTubeStudioHandler.handle_message`` directly so the suite
doesn't need QtWebSockets or a real WebSocket connection. The Qt
server wrapper is covered indirectly by the same handler.
"""
from __future__ import annotations

import pytest

from puppet.canvas import PuppetCanvas
from puppet.document import Drawable, Parameter, PuppetDocument
from puppet.vts_api import (
    API_NAME,
    API_VERSION,
    VTubeStudioHandler,
)


def _doc_with_params() -> PuppetDocument:
    doc = PuppetDocument(size=(32, 32))
    doc.drawables = [Drawable(
        id="x", texture="textures/x.png",
        vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
        draw_order=0,
    )]
    doc.parameters = [
        Parameter(id="ParamAngleX", min=-1.0, max=1.0, default=0.0),
        Parameter(id="ParamMouthOpenY", min=0.0, max=1.0, default=0.0),
    ]
    return doc


def _request(message_type: str, data: dict | None = None, *, request_id: str = "r1") -> dict:
    return {
        "apiName": API_NAME,
        "apiVersion": API_VERSION,
        "requestID": request_id,
        "messageType": message_type,
        "data": data or {},
    }


# ---------------------------------------------------------------------------
# Envelope shape
# ---------------------------------------------------------------------------


def test_response_envelope_carries_request_id(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_params())
        handler = VTubeStudioHandler(canvas)
        response = handler.handle_message(_request("APIStateRequest", request_id="abc-123"))
        assert response["requestID"] == "abc-123"
        assert response["apiName"] == API_NAME
        assert response["messageType"] == "APIStateResponse"
    finally:
        canvas.deleteLater()


def test_unknown_message_type_returns_api_error(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_params())
        handler = VTubeStudioHandler(canvas)
        response = handler.handle_message(_request("NotAThing"))
        assert response["messageType"] == "APIError"
        assert response["data"]["errorID"] == 1
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Authentication flow
# ---------------------------------------------------------------------------


def test_api_state_unauthenticated_by_default(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_params())
        handler = VTubeStudioHandler(canvas)
        response = handler.handle_message(_request("APIStateRequest"))
        assert response["data"]["currentSessionAuthenticated"] is False
    finally:
        canvas.deleteLater()


def test_token_then_auth_grants_authenticated_state(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_params())
        handler = VTubeStudioHandler(canvas)
        token_resp = handler.handle_message(_request(
            "AuthenticationTokenRequest",
            {"pluginName": "Test", "pluginDeveloper": "Suite"},
        ))
        token = token_resp["data"]["authenticationToken"]
        assert isinstance(token, str) and len(token) > 16
        auth_resp = handler.handle_message(_request(
            "AuthenticationRequest",
            {"authenticationToken": token},
        ))
        assert auth_resp["data"]["authenticated"] is True
        assert handler.is_authenticated() is True
    finally:
        canvas.deleteLater()


def test_wrong_token_is_rejected(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_params())
        handler = VTubeStudioHandler(canvas)
        handler.handle_message(_request(
            "AuthenticationTokenRequest",
            {"pluginName": "X", "pluginDeveloper": "Y"},
        ))
        resp = handler.handle_message(_request(
            "AuthenticationRequest",
            {"authenticationToken": "definitely-not-the-token"},
        ))
        assert resp["data"]["authenticated"] is False
        assert handler.is_authenticated() is False
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Parameter list / read
# ---------------------------------------------------------------------------


def test_parameter_list_returns_documents_parameters(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_params())
        handler = VTubeStudioHandler(canvas)
        resp = handler.handle_message(_request("Live2DParameterListRequest"))
        names = {p["name"] for p in resp["data"]["parameters"]}
        assert {"ParamAngleX", "ParamMouthOpenY"} == names
    finally:
        canvas.deleteLater()


def test_parameter_value_requires_auth(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_params())
        handler = VTubeStudioHandler(canvas)
        resp = handler.handle_message(_request(
            "ParameterValueRequest", {"name": "ParamAngleX"},
        ))
        assert resp["messageType"] == "APIError"
        assert resp["data"]["errorID"] == 50
    finally:
        canvas.deleteLater()


def _authenticate(handler):
    token = handler.handle_message(_request(
        "AuthenticationTokenRequest",
        {"pluginName": "t", "pluginDeveloper": "t"},
    ))["data"]["authenticationToken"]
    handler.handle_message(_request(
        "AuthenticationRequest", {"authenticationToken": token},
    ))


def test_parameter_value_returns_current_after_auth(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_params())
        canvas.set_parameter_value("ParamAngleX", 0.42)
        handler = VTubeStudioHandler(canvas)
        _authenticate(handler)
        resp = handler.handle_message(_request(
            "ParameterValueRequest", {"name": "ParamAngleX"},
        ))
        assert resp["data"]["value"] == pytest.approx(0.42)
    finally:
        canvas.deleteLater()


def test_unknown_parameter_returns_error(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_params())
        handler = VTubeStudioHandler(canvas)
        _authenticate(handler)
        resp = handler.handle_message(_request(
            "ParameterValueRequest", {"name": "DoesNotExist"},
        ))
        assert resp["messageType"] == "APIError"
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Parameter injection (the headline feature)
# ---------------------------------------------------------------------------


def test_inject_writes_parameter_values_into_canvas(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_params())
        handler = VTubeStudioHandler(canvas)
        _authenticate(handler)
        resp = handler.handle_message(_request(
            "InjectParameterDataRequest",
            {
                "faceFound": True,
                "mode": "set",
                "parameterValues": [
                    {"id": "ParamAngleX", "value": 0.75},
                    {"id": "ParamMouthOpenY", "value": 1.0},
                ],
            },
        ))
        assert resp["data"]["parameterValuesApplied"] == 2
        values = canvas.parameter_values()
        assert values["ParamAngleX"] == pytest.approx(0.75)
        assert values["ParamMouthOpenY"] == pytest.approx(1.0)
    finally:
        canvas.deleteLater()


def test_inject_requires_authentication(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_params())
        handler = VTubeStudioHandler(canvas)
        resp = handler.handle_message(_request(
            "InjectParameterDataRequest",
            {"parameterValues": [{"id": "ParamAngleX", "value": 0.5}]},
        ))
        assert resp["messageType"] == "APIError"
        # Canvas wasn't touched.
        assert canvas.parameter_values()["ParamAngleX"] == pytest.approx(0.0)
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Parameter creation
# ---------------------------------------------------------------------------


def test_parameter_creation_adds_new_parameter(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_params())
        handler = VTubeStudioHandler(canvas)
        _authenticate(handler)
        resp = handler.handle_message(_request(
            "ParameterCreationRequest",
            {"parameterName": "ParamCustom", "min": 0.0, "max": 10.0, "defaultValue": 5.0},
        ))
        assert resp["messageType"] == "ParameterCreationResponse"
        ids = {p.id for p in canvas.document().parameters}
        assert "ParamCustom" in ids
    finally:
        canvas.deleteLater()


def test_parameter_creation_rejects_duplicate(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_params())
        handler = VTubeStudioHandler(canvas)
        _authenticate(handler)
        resp = handler.handle_message(_request(
            "ParameterCreationRequest",
            {"parameterName": "ParamAngleX"},
        ))
        assert resp["messageType"] == "APIError"
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_non_dict_message_returns_error(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_params())
        handler = VTubeStudioHandler(canvas)
        resp = handler.handle_message("not a dict")
        assert resp["messageType"] == "APIError"
    finally:
        canvas.deleteLater()
