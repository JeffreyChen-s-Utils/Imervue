"""Imeru's motions and expressions, keyed with eased cubic segments."""

from __future__ import annotations

from Imervue.puppet.document import Expression, ExpressionParam, Motion, MotionSegment, MotionTrack


def track(param: str, *keys: tuple[float, float]) -> MotionTrack:
    """A track through *keys* ``(time, value)``, easing in and out of every key."""
    segments = []
    for (t0, v0), (t1, v1) in zip(keys, keys[1:], strict=False):
        third = (t1 - t0) / 3.0
        segments.append(
            MotionSegment(
                type="cubic-bezier",
                p0=(t0, v0),
                p1=(t1, v1),
                c0=(t0 + third, v0),
                c1=(t1 - third, v1),
            )
        )
    return MotionTrack(param_id=param, segments=segments)


def both(fmt: str, *keys) -> list[MotionTrack]:
    return [track(fmt.format(side), *keys) for side in ("L", "R")]


def motions() -> list[Motion]:
    blink = ((0, 1), (2.9, 1), (3.0, 0), (3.1, 0), (3.24, 1), (6, 1))
    return [
        Motion(
            name="idle_breath",
            duration=4.0,
            loop=True,
            group="Idle",
            fade_in_duration=0.6,
            tracks=[
                track("ParamBreath", (0, 0.2), (2, 0.9), (4, 0.2)),
                track("ParamBodyAngleX", (0, 0), (2, 0.14), (4, 0)),
                track("ParamAngleZ", (0, 0), (2, 0.12), (4, 0)),
                track("ParamAngleY", (0, 0), (2, 0.06), (4, 0)),
                track("ParamArmRA", (0, 0), (2, 0.03), (4, 0)),
                track("ParamArmLA", (0, 0.03), (2, 0), (4, 0.03)),
            ],
        ),
        Motion(
            name="idle_look",
            duration=6.0,
            loop=True,
            group="Idle",
            fade_in_duration=0.6,
            tracks=[
                track(
                    "ParamAngleX",
                    (0, 0),
                    (1.2, 0.55),
                    (2.6, 0.55),
                    (3.8, -0.45),
                    (5.0, -0.45),
                    (6, 0),
                ),
                track(
                    "ParamEyeBallX",
                    (0, 0),
                    (1.0, 0.8),
                    (2.6, 0.8),
                    (3.6, -0.8),
                    (5.0, -0.8),
                    (6, 0),
                ),
                track("ParamAngleY", (0, 0), (1.2, 0.15), (3.8, -0.1), (6, 0)),
                track("ParamBreath", (0, 0.3), (3, 0.85), (6, 0.3)),
                *both("ParamEye{}Open", *blink),
            ],
        ),
        Motion(
            name="tap_head",
            duration=2.4,
            group="TapHead",
            fade_in_duration=0.2,
            fade_out_duration=0.4,
            tracks=[
                track("ParamAngleZ", (0, 0), (0.35, 0.7), (1.2, 0.6), (1.8, -0.2), (2.4, 0)),
                *both("ParamEye{}Smile", (0, 0), (0.25, 1), (1.8, 1), (2.4, 0)),
                track("ParamMouthForm", (0, 0), (0.3, 1), (1.9, 1), (2.4, 0)),
                track("ParamMouthOpenY", (0, 0), (0.3, 0.35), (1.6, 0.3), (2.4, 0)),
                track("ParamCheek", (0, 0), (0.4, 1), (2.0, 0.8), (2.4, 0)),
                *both("ParamBrow{}Y", (0, 0), (0.3, 0.4), (2.4, 0)),
            ],
        ),
        Motion(
            name="greet",
            duration=2.8,
            group="Gesture",
            fade_in_duration=0.2,
            fade_out_duration=0.4,
            tracks=[
                track(
                    "ParamAngleY", (0, 0), (0.4, -0.55), (0.8, 0.1), (1.2, -0.3), (1.6, 0), (2.8, 0)
                ),
                track(
                    "ParamMouthOpenY",
                    (0, 0),
                    (0.3, 0.7),
                    (0.5, 0.2),
                    (0.7, 0.8),
                    (0.9, 0.2),
                    (1.1, 0.6),
                    (1.4, 0),
                    (2.8, 0),
                ),
                track("ParamMouthForm", (0, 0.4), (2.8, 0.8)),
                *both("ParamEye{}Smile", (0, 0), (1.4, 0), (1.8, 1), (2.5, 1), (2.8, 0)),
                track("ParamAngleZ", (0, 0), (1.6, 0.3), (2.8, 0)),
                track("ParamCheek", (0, 0), (1.6, 0.6), (2.8, 0)),
            ],
        ),
        Motion(
            name="wave",
            duration=3.2,
            group="Gesture",
            fade_in_duration=0.2,
            fade_out_duration=0.4,
            tracks=[
                track("ParamArmRA", (0, 0), (0.6, 1), (2.6, 1), (3.2, 0)),
                track(
                    "ParamArmRB",
                    (0, 0),
                    (0.35, 0.75),
                    (0.6, 0.86),
                    (0.9, 0.78),
                    (1.2, 1.0),
                    (1.5, 0.78),
                    (1.8, 1.0),
                    (2.1, 0.78),
                    (2.4, 0.95),
                    (2.6, 0.86),
                    (2.85, 0.75),
                    (3.2, 0),
                ),
                track("ParamAngleZ", (0, 0), (0.5, -0.35), (2.6, -0.3), (3.2, 0)),
                track("ParamBodyAngleX", (0, 0), (0.5, -0.25), (2.6, -0.2), (3.2, 0)),
                *both("ParamEye{}Smile", (0, 0), (0.4, 1), (2.6, 1), (3.2, 0)),
                track(
                    "ParamMouthOpenY",
                    (0, 0),
                    (0.4, 0.6),
                    (0.7, 0.3),
                    (1.0, 0.6),
                    (1.3, 0.2),
                    (2.6, 0.2),
                    (3.2, 0),
                ),
                track("ParamMouthForm", (0, 0), (0.4, 1), (3.2, 0)),
                track("ParamCheek", (0, 0), (0.6, 0.7), (3.2, 0)),
            ],
        ),
        Motion(
            name="surprised",
            duration=2.2,
            group="Gesture",
            fade_in_duration=0.1,
            fade_out_duration=0.4,
            tracks=[
                *both("ParamBrow{}Y", (0, 0), (0.15, 1), (1.6, 1), (2.2, 0)),
                track("ParamMouthOpenY", (0, 0), (0.15, 0.8), (1.5, 0.6), (2.2, 0)),
                track("ParamMouthForm", (0, 0), (0.15, -0.4), (2.2, 0)),
                track("ParamAngleY", (0, 0), (0.15, 0.35), (1.5, 0.2), (2.2, 0)),
                track("ParamBodyAngleY", (0, 0), (0.12, 0.6), (0.4, 0), (2.2, 0)),
                track("ParamEyeBallY", (0, 0), (0.15, 0.3), (2.2, 0)),
            ],
        ),
        Motion(
            name="shy",
            duration=3.2,
            group="TapBody",
            fade_in_duration=0.3,
            fade_out_duration=0.5,
            tracks=[
                track("ParamCheek", (0, 0), (0.5, 1), (2.6, 1), (3.2, 0)),
                track("ParamAngleX", (0, 0), (0.6, -0.45), (2.6, -0.45), (3.2, 0)),
                track("ParamAngleY", (0, 0), (0.6, -0.35), (2.6, -0.3), (3.2, 0)),
                track("ParamEyeBallX", (0, 0), (0.5, 0.8), (2.6, 0.8), (3.2, 0)),
                track("ParamEyeBallY", (0, 0), (0.5, -0.5), (3.2, 0)),
                track("ParamMouthForm", (0, 0), (0.6, 0.5), (3.2, 0)),
                track("ParamAngleZ", (0, 0), (0.6, 0.35), (3.2, 0)),
                *both("ParamBrow{}Angle", (0, 0), (0.5, 0.5), (3.2, 0)),
            ],
        ),
        Motion(
            name="sleepy",
            duration=4.0,
            group="Gesture",
            fade_in_duration=0.3,
            fade_out_duration=0.5,
            tracks=[
                *both(
                    "ParamEye{}Open", (0, 1), (1, 0.35), (2.2, 0.3), (2.6, 0), (3.4, 0.4), (4, 1)
                ),
                track(
                    "ParamMouthOpenY", (0, 0), (1.0, 0), (1.6, 1.0), (2.4, 0.9), (3.0, 0), (4, 0)
                ),
                track("ParamAngleZ", (0, 0), (1.6, -0.6), (3.0, -0.5), (4, 0)),
                track("ParamAngleY", (0, 0), (1.6, 0.3), (3.0, 0), (4, 0)),
                *both("ParamBrow{}Y", (0, 0), (1.0, 0), (1.6, 0.5), (3.0, 0), (4, 0)),
            ],
        ),
    ]


def _p(param: str, value: float, mode: str = "overwrite") -> ExpressionParam:
    return ExpressionParam(id=param, value=value, mode=mode)


def expressions() -> list[Expression]:
    return [
        Expression(
            name="smile", params=[_p("ParamMouthForm", 1.0), _p("ParamCheek", 0.3, "additive")]
        ),
        Expression(
            name="happy",
            params=[
                _p("ParamEyeLSmile", 1.0),
                _p("ParamEyeRSmile", 1.0),
                _p("ParamMouthForm", 1.0),
                _p("ParamMouthOpenY", 0.4),
                _p("ParamCheek", 0.6, "additive"),
            ],
        ),
        Expression(
            name="surprised",
            params=[
                _p("ParamBrowLY", 1.0),
                _p("ParamBrowRY", 1.0),
                _p("ParamMouthOpenY", 0.7),
                _p("ParamMouthForm", -0.3),
                _p("ParamEyeBallY", 0.2, "additive"),
            ],
        ),
        Expression(
            name="sad",
            params=[
                _p("ParamBrowLAngle", 1.0),
                _p("ParamBrowRAngle", 1.0),
                _p("ParamBrowLY", -0.2, "additive"),
                _p("ParamBrowRY", -0.2, "additive"),
                _p("ParamMouthForm", -1.0),
                _p("ParamEyeLOpen", 0.8, "multiply"),
                _p("ParamEyeROpen", 0.8, "multiply"),
            ],
        ),
        Expression(
            name="angry",
            params=[
                _p("ParamBrowLAngle", -1.0),
                _p("ParamBrowRAngle", -1.0),
                _p("ParamBrowLY", -0.5),
                _p("ParamBrowRY", -0.5),
                _p("ParamMouthForm", -0.7),
                _p("ParamEyeLOpen", 0.85, "multiply"),
                _p("ParamEyeROpen", 0.85, "multiply"),
            ],
        ),
        Expression(name="blush", params=[_p("ParamCheek", 1.0)]),
        Expression(
            name="sleepy",
            params=[
                _p("ParamEyeLOpen", 0.4, "multiply"),
                _p("ParamEyeROpen", 0.4, "multiply"),
                _p("ParamBrowLY", 0.3, "additive"),
                _p("ParamBrowRY", 0.3, "additive"),
            ],
        ),
    ]
