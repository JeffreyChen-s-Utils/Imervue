"""UI strings of the GPU Develop plugin in the five built-in languages."""
from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "English": {
        "gpu_develop_menu": "GPU Develop…",
        "gpu_develop_title": "GPU Develop",
        "gpu_develop_found": (
            "Batch Export can render Develop recipes on {gpu}. Choose it under "
            "“Render on” in the Batch Export dialog."),
        "gpu_develop_none": (
            "No discrete GPU was found. Integrated GPUs are not used, so Batch Export "
            "renders Develop recipes on the CPU."),
    },
    "Traditional_Chinese": {
        "gpu_develop_menu": "GPU 顯影…",
        "gpu_develop_title": "GPU 顯影",
        "gpu_develop_found": "批次匯出可以用 {gpu} 套用顯影設定。請在批次匯出對話框的「運算裝置」選擇它。",
        "gpu_develop_none": "找不到獨立顯示卡。內建顯示卡不會被使用，所以批次匯出會用 CPU 套用顯影設定。",
    },
    "Chinese": {
        "gpu_develop_menu": "GPU 显影…",
        "gpu_develop_title": "GPU 显影",
        "gpu_develop_found": "批量导出可以用 {gpu} 应用显影设置。请在批量导出对话框的“运算设备”中选择它。",
        "gpu_develop_none": "未找到独立显卡。集成显卡不会被使用，因此批量导出会用 CPU 应用显影设置。",
    },
    "Japanese": {
        "gpu_develop_menu": "GPU 現像…",
        "gpu_develop_title": "GPU 現像",
        "gpu_develop_found": (
            "一括エクスポートで {gpu} を使って現像設定を適用できます。一括エクスポートダイアログの"
            "「処理デバイス」で選択してください。"),
        "gpu_develop_none": (
            "専用 GPU が見つかりません。内蔵 GPU は使用しないため、一括エクスポートは CPU で"
            "現像設定を適用します。"),
    },
    "Korean": {
        "gpu_develop_menu": "GPU 현상…",
        "gpu_develop_title": "GPU 현상",
        "gpu_develop_found": (
            "일괄 내보내기에서 {gpu}(으)로 현상 설정을 적용할 수 있습니다. 일괄 내보내기 대화 상자의 "
            "“처리 장치”에서 선택하세요."),
        "gpu_develop_none": (
            "외장 GPU를 찾을 수 없습니다. 내장 GPU는 사용하지 않으므로 일괄 내보내기는 CPU로 "
            "현상 설정을 적용합니다."),
    },
}
