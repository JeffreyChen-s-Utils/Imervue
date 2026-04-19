"""
現代 OpenGL 渲染器
Shader-based renderer using VBO + GLSL, replacing deprecated immediate mode.
Falls back to immediate mode if shader compilation fails.
"""
from __future__ import annotations

import ctypes
import logging
import numpy as np
from OpenGL.GL import *  # noqa: F401, F403 — OpenGL uses hundreds of constants; explicit list impractical
from OpenGL.GL import shaders as gl_shaders

logger = logging.getLogger("Imervue.gl_renderer")

# ===========================
# Shader 源碼
# ===========================

_VERTEX_SHADER = """
#version 120
attribute vec2 a_position;
attribute vec2 a_texcoord;
varying vec2 v_texcoord;
uniform mat4 u_mvp;

void main() {
    gl_Position = u_mvp * vec4(a_position, 0.0, 1.0);
    v_texcoord = a_texcoord;
}
"""

_FRAGMENT_SHADER = """
#version 120
varying vec2 v_texcoord;
uniform sampler2D u_texture;
uniform vec4 u_color;
uniform int u_color_mode;  // 0=normal 1=grayscale 2=invert 3=sepia

void main() {
    vec4 sampled = texture2D(u_texture, v_texcoord);
    vec3 c = sampled.rgb;
    if (u_color_mode == 1) {
        // Grayscale using Rec. 709 luma coefficients
        float y = dot(c, vec3(0.2126, 0.7152, 0.0722));
        c = vec3(y, y, y);
    } else if (u_color_mode == 2) {
        // Invert (keep alpha)
        c = vec3(1.0) - c;
    } else if (u_color_mode == 3) {
        // Sepia — classic filter matrix
        float r = dot(c, vec3(0.393, 0.769, 0.189));
        float g = dot(c, vec3(0.349, 0.686, 0.168));
        float b = dot(c, vec3(0.272, 0.534, 0.131));
        c = clamp(vec3(r, g, b), 0.0, 1.0);
    }
    gl_FragColor = vec4(c, sampled.a) * u_color;
}
"""

_COLOR_VERTEX = """
#version 120
attribute vec2 a_position;
uniform mat4 u_mvp;

void main() {
    gl_Position = u_mvp * vec4(a_position, 0.0, 1.0);
}
"""

_COLOR_FRAGMENT = """
#version 120
uniform vec4 u_color;

void main() {
    gl_FragColor = u_color;
}
"""


def _ortho(left, right, bottom, top, near, far):
    """Build a 4x4 orthographic projection matrix (column-major for OpenGL)."""
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = 2.0 / (right - left)
    m[1, 1] = 2.0 / (top - bottom)
    m[2, 2] = -2.0 / (far - near)
    m[3, 0] = -(right + left) / (right - left)
    m[3, 1] = -(top + bottom) / (top - bottom)
    m[3, 2] = -(far + near) / (far - near)
    m[3, 3] = 1.0
    return m


class GLRenderer:
    """
    管理 shader program 和 VBO 繪圖。
    在 initializeGL 時建立，每個 GPUImageView 持有一個實例。
    如果 shader 建立失敗，use_shaders 會被設為 False，呼叫端繼續用 immediate mode。
    """

    def __init__(self):
        self.use_shaders = False
        self._tex_prog = None
        self._col_prog = None
        self._vbo = None
        self._mvp = np.eye(4, dtype=np.float32)
        # 0=normal 1=grayscale 2=invert 3=sepia
        self.color_mode: int = 0

    def init(self):
        """在有效的 GL context 中呼叫"""
        try:
            vs = gl_shaders.compileShader(_VERTEX_SHADER, GL_VERTEX_SHADER)
            fs = gl_shaders.compileShader(_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
            self._tex_prog = gl_shaders.compileProgram(vs, fs)

            vs2 = gl_shaders.compileShader(_COLOR_VERTEX, GL_VERTEX_SHADER)
            fs2 = gl_shaders.compileShader(_COLOR_FRAGMENT, GL_FRAGMENT_SHADER)
            self._col_prog = gl_shaders.compileProgram(vs2, fs2)

            # 建立共用 VBO（quad = 4 vertices × (2 pos + 2 tex) = 16 floats）
            self._vbo = glGenBuffers(1)

            self.use_shaders = True

            # 啟用各向異性過濾（如果支援）
            try:
                max_aniso = glGetFloatv(0x84FF)  # GL_MAX_TEXTURE_MAX_ANISOTROPY
                if max_aniso and max_aniso > 1.0:
                    self._max_anisotropy = min(max_aniso, 8.0)
                else:
                    self._max_anisotropy = 0
            except Exception:
                self._max_anisotropy = 0

        except Exception as e:
            logger.warning(f"Shader init failed, using immediate mode: {e}")
            self.use_shaders = False

    def set_ortho(self, w: float, h: float):
        self._mvp = _ortho(0, w, h, 0, -1, 1)

    def set_mvp(self, mvp: np.ndarray):
        self._mvp = mvp.astype(np.float32)

    def apply_anisotropy(self, tex_id):
        """為指定 texture 啟用各向異性過濾"""
        if not self.use_shaders or not hasattr(self, '_max_anisotropy') or self._max_anisotropy <= 0:
            return
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameterf(GL_TEXTURE_2D, 0x84FE, self._max_anisotropy)  # GL_TEXTURE_MAX_ANISOTROPY

    def draw_textured_quad(self, x0, y0, x1, y1, tex_id, opacity=1.0):
        """用 shader 繪製貼圖四邊形"""
        if not self.use_shaders:
            return self._draw_textured_quad_legacy(x0, y0, x1, y1, tex_id, opacity)

        prog = self._tex_prog
        glUseProgram(prog)

        # MVP
        mvp_loc = glGetUniformLocation(prog, "u_mvp")
        glUniformMatrix4fv(mvp_loc, 1, GL_FALSE, self._mvp)

        # Color
        col_loc = glGetUniformLocation(prog, "u_color")
        glUniform4f(col_loc, 1, 1, 1, opacity)

        # Color mode (grayscale/invert/sepia)
        mode_loc = glGetUniformLocation(prog, "u_color_mode")
        if mode_loc != -1:
            glUniform1i(mode_loc, int(self.color_mode))

        # Texture
        tex_loc = glGetUniformLocation(prog, "u_texture")
        glUniform1i(tex_loc, 0)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, tex_id)

        # VBO data: pos(x,y) + tex(s,t)
        data = np.array([
            x0, y1, 0, 1,   # bottom-left
            x1, y1, 1, 1,   # bottom-right
            x1, y0, 1, 0,   # top-right
            x0, y0, 0, 0,   # top-left
        ], dtype=np.float32)

        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_DYNAMIC_DRAW)

        pos_loc = glGetAttribLocation(prog, "a_position")
        tex_loc_a = glGetAttribLocation(prog, "a_texcoord")

        glEnableVertexAttribArray(pos_loc)
        glVertexAttribPointer(pos_loc, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(0))
        glEnableVertexAttribArray(tex_loc_a)
        glVertexAttribPointer(tex_loc_a, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(8))

        glDrawArrays(GL_TRIANGLE_FAN, 0, 4)

        glDisableVertexAttribArray(pos_loc)
        glDisableVertexAttribArray(tex_loc_a)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glUseProgram(0)

    def draw_colored_rect(self, x0, y0, x1, y1, r, g, b, a, filled=True):
        """用 shader 繪製純色矩形"""
        if not self.use_shaders:
            return self._draw_colored_rect_legacy(x0, y0, x1, y1, r, g, b, a, filled)

        prog = self._col_prog
        glUseProgram(prog)

        mvp_loc = glGetUniformLocation(prog, "u_mvp")
        glUniformMatrix4fv(mvp_loc, 1, GL_FALSE, self._mvp)

        col_loc = glGetUniformLocation(prog, "u_color")
        glUniform4f(col_loc, r, g, b, a)

        data = np.array([x0, y0, x1, y0, x1, y1, x0, y1], dtype=np.float32)

        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_DYNAMIC_DRAW)

        pos_loc = glGetAttribLocation(prog, "a_position")
        glEnableVertexAttribArray(pos_loc)
        glVertexAttribPointer(pos_loc, 2, GL_FLOAT, GL_FALSE, 0, ctypes.c_void_p(0))

        if filled:
            glDrawArrays(GL_TRIANGLE_FAN, 0, 4)
        else:
            glDrawArrays(GL_LINE_LOOP, 0, 4)

        glDisableVertexAttribArray(pos_loc)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glUseProgram(0)

    # ===========================
    # Immediate mode fallback
    # ===========================

    @staticmethod
    def _draw_textured_quad_legacy(x0, y0, x1, y1, tex_id, opacity=1.0):
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glColor4f(1, 1, 1, opacity)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 1); glVertex2f(x0, y1)
        glTexCoord2f(1, 1); glVertex2f(x1, y1)
        glTexCoord2f(1, 0); glVertex2f(x1, y0)
        glTexCoord2f(0, 0); glVertex2f(x0, y0)
        glEnd()

    @staticmethod
    def _draw_colored_rect_legacy(x0, y0, x1, y1, r, g, b, a, filled=True):
        glColor4f(r, g, b, a)
        if filled:
            glBegin(GL_QUADS)
        else:
            glBegin(GL_LINE_LOOP)
        glVertex2f(x0, y0)
        glVertex2f(x1, y0)
        glVertex2f(x1, y1)
        glVertex2f(x0, y1)
        glEnd()
