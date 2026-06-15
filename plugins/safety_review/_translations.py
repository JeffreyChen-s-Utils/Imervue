"""Translation strings for the safety_review plugin.

Extracted from the plugin shell to keep ``safety_review.py`` focused on
coordination. Loaded by ``SafetyReviewPlugin.get_translations``.
"""
from __future__ import annotations

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "English": {
        "safety_review_title": "Safety Review \u2014 Auto Mosaic",
        "safety_review_batch_title": "Batch Safety Review",
        "safety_review_scan_all": "Safety Review \u2014 Scan All Images",
        "safety_review_scan_all_title": "Safety Review \u2014 Scan All",
        "safety_review_scan_all_confirm":
            "This will scan {count} image(s) and mosaic any detected "
            "genitalia directly on the original files.\n\n"
            "Nipples will NOT be mosaiced.\n\n"
            "Continue?",
        "safety_review_scan_all_info":
            "Scanning {count} images \u2014 genitalia will be mosaiced, "
            "nipples will NOT be touched.",
        "safety_review_scan_all_done":
            "Done \u2014 {success}/{total} images processed, "
            "{regions} region(s) mosaiced, {failed} failed.",
        "safety_review_quick": "Safety Review \u2014 Quick Mosaic",
        "safety_review_source": "Source:",
        "safety_review_info":
            "Detects and mosaics exposed genitalia (male & female). "
            "Nipples are NOT mosaiced.",
        "safety_review_block_size": "Mosaic block size (px):",
        "safety_review_padding": "Padding around region (px):",
        "safety_review_overwrite":
            "Overwrite original files (no backup!)",
        "safety_review_overwrite_single": "Overwrite original file",
        "safety_review_output_dir": "Output folder:",
        "safety_review_run": "Apply Mosaic",
        "safety_review_done": "Done! Saved to: {path}",
        "safety_review_done_short": "Mosaic applied!",
        "safety_review_nothing":
            "No genitalia detected \u2014 image unchanged.",
        "safety_review_batch_done":
            "Processed {success}/{total} image(s)",
        "safety_review_close": "Close",
        "safety_review_time":
            "Elapsed: {elapsed}    ETA: {eta}    (~{speed:.1f}s / image)",
        "safety_review_mode": "Detection mode:",
        "safety_review_mode_real": "Real Photo",
        "safety_review_mode_anime": "Anime / Illustration",
        "safety_review_confidence": "Min confidence:",
        "safety_review_start": "Start",
        "safety_review_installing": "Installing dependencies...",
        "safety_review_expand_pct": "Expand detection box (%):",
        "safety_review_scan_folder": "Source folder:",
        "safety_review_scan_folder_hint":
            "Choose a folder to scan for images",
        "safety_review_mode_auto": "Auto-detect",
        "safety_review_style": "Censor style:",
        "safety_review_style_mosaic": "Mosaic",
        "safety_review_style_blur": "Gaussian Blur",
        "safety_review_style_black": "Black Bar",
        "safety_review_categories": "Detection categories:",
        "safety_review_cat_genitalia": "Genitalia (penis / vagina)",
        "safety_review_cat_anus": "Anus",
        "safety_review_cat_nipple": "Nipple / Breast",
        "safety_review_cat_sexual_act": "Sexual Act (anime only)",
    },
    "Traditional_Chinese": {
        "safety_review_title":
            "\u5b89\u5168\u5be9\u6838 \u2014 \u81ea\u52d5\u6253\u78bc",
        "safety_review_batch_title":
            "\u6279\u6b21\u5b89\u5168\u5be9\u6838",
        "safety_review_scan_all":
            "\u5b89\u5168\u5be9\u6838 \u2014 \u6383\u63cf\u6240\u6709\u5716\u7247",
        "safety_review_scan_all_title":
            "\u5b89\u5168\u5be9\u6838 \u2014 \u6383\u63cf\u5168\u90e8",
        "safety_review_scan_all_confirm":
            "\u5c07\u6383\u63cf {count} \u5f35\u5716\u7247\uff0c"
            "\u5075\u6e2c\u5230\u7684\u751f\u6b96\u5668\u6703\u76f4\u63a5\u6253\u78bc"
            "\u5728\u539f\u59cb\u6a94\u6848\u4e0a\u3002\n\n"
            "\u7537\u5973\u4e73\u982d\u90fd\u4e0d\u6703\u88ab\u6253\u78bc\u3002\n\n"
            "\u7e7c\u7e8c\uff1f",
        "safety_review_scan_all_info":
            "\u6b63\u5728\u6383\u63cf {count} \u5f35\u5716\u7247"
            " \u2014 \u751f\u6b96\u5668\u6703\u88ab\u6253\u78bc\uff0c"
            "\u4e73\u982d\u4e0d\u6703\u88ab\u8655\u7406\u3002",
        "safety_review_scan_all_done":
            "\u5b8c\u6210 \u2014 \u5df2\u8655\u7406 {success}/{total}"
            " \u5f35\u5716\u7247\uff0c"
            "\u6253\u78bc {regions} \u500b\u5340\u57df\uff0c"
            "{failed} \u5f35\u5931\u6557\u3002",
        "safety_review_quick":
            "\u5b89\u5168\u5be9\u6838 \u2014 \u5feb\u901f\u6253\u78bc",
        "safety_review_source": "\u4f86\u6e90\uff1a",
        "safety_review_info":
            "\u5075\u6e2c\u4e26\u6253\u78bc\u88f8\u9732\u7684"
            "\u751f\u6b96\u5668\uff08\u7537\u5973\uff09\u3002"
            "\u4e73\u982d\u4e0d\u6703\u88ab\u6253\u78bc\u3002",
        "safety_review_block_size":
            "\u99ac\u8cfd\u514b\u5927\u5c0f (px)\uff1a",
        "safety_review_padding":
            "\u5340\u57df\u5916\u64f4 (px)\uff1a",
        "safety_review_overwrite":
            "\u8986\u84cb\u539f\u59cb\u6a94\u6848\uff08\u4e0d\u5099\u4efd\uff01\uff09",
        "safety_review_overwrite_single":
            "\u8986\u84cb\u539f\u59cb\u6a94\u6848",
        "safety_review_output_dir":
            "\u8f38\u51fa\u8cc7\u6599\u593e\uff1a",
        "safety_review_run": "\u57f7\u884c\u6253\u78bc",
        "safety_review_done":
            "\u5b8c\u6210\uff01\u5df2\u5132\u5b58\u81f3\uff1a{path}",
        "safety_review_done_short": "\u6253\u78bc\u5b8c\u6210\uff01",
        "safety_review_nothing":
            "\u672a\u5075\u6e2c\u5230\u751f\u6b96\u5668"
            " \u2014 \u5716\u7247\u672a\u8b8a\u66f4\u3002",
        "safety_review_batch_done":
            "\u5df2\u8655\u7406 {success}/{total} \u5f35\u5716\u7247",
        "safety_review_close": "\u95dc\u9589",
        "safety_review_time":
            "\u5df2\u7d93\u904e: {elapsed}    \u9810\u8a08: {eta}    (~{speed:.1f}\u79d2 / \u5f35)",
        "safety_review_mode": "\u5075\u6e2c\u6a21\u5f0f\uff1a",
        "safety_review_mode_real": "\u771f\u4eba\u7167\u7247",
        "safety_review_mode_anime": "\u52d5\u756b / \u63d2\u756b",
        "safety_review_confidence": "\u6700\u4f4e\u4fe1\u5fc3\u5ea6\uff1a",
        "safety_review_start": "\u958b\u59cb",
        "safety_review_installing": "\u6b63\u5728\u5b89\u88dd\u76f8\u4f9d\u5957\u4ef6\u2026",
        "safety_review_expand_pct": "\u5075\u6e2c\u6846\u64f4\u5f35 (%)\uff1a",
        "safety_review_scan_folder": "\u4f86\u6e90\u8cc7\u6599\u593e\uff1a",
        "safety_review_scan_folder_hint":
            "\u9078\u64c7\u8981\u6383\u63cf\u7684\u8cc7\u6599\u593e",
        "safety_review_mode_auto": "\u81ea\u52d5\u5224\u65b7",
        "safety_review_style": "\u6253\u78bc\u6a23\u5f0f\uff1a",
        "safety_review_style_mosaic": "\u99ac\u8cfd\u514b",
        "safety_review_style_blur": "\u9ad8\u65af\u6a21\u7cca",
        "safety_review_style_black": "\u9ed1\u689d\u906e\u64cb",
        "safety_review_categories": "\u5075\u6e2c\u985e\u5225\uff1a",
        "safety_review_cat_genitalia": "\u751f\u6b96\u5668 (\u9670\u8396 / \u9670\u9053)",
        "safety_review_cat_anus": "\u809b\u9580",
        "safety_review_cat_nipple": "\u4e73\u982d / \u4e73\u623f",
        "safety_review_cat_sexual_act": "\u6027\u884c\u70ba (\u50c5\u52d5\u756b)",
    },
    "Chinese": {
        "safety_review_title":
            "\u5b89\u5168\u5ba1\u6838 \u2014 \u81ea\u52a8\u6253\u7801",
        "safety_review_batch_title":
            "\u6279\u91cf\u5b89\u5168\u5ba1\u6838",
        "safety_review_scan_all":
            "\u5b89\u5168\u5ba1\u6838 \u2014 \u626b\u63cf\u6240\u6709\u56fe\u7247",
        "safety_review_scan_all_title":
            "\u5b89\u5168\u5ba1\u6838 \u2014 \u626b\u63cf\u5168\u90e8",
        "safety_review_scan_all_confirm":
            "\u5c06\u626b\u63cf {count} \u5f20\u56fe\u7247\uff0c"
            "\u68c0\u6d4b\u5230\u7684\u751f\u6b96\u5668\u4f1a\u76f4\u63a5\u6253\u7801"
            "\u5728\u539f\u59cb\u6587\u4ef6\u4e0a\u3002\n\n"
            "\u7537\u5973\u4e73\u5934\u90fd\u4e0d\u4f1a\u88ab\u6253\u7801\u3002\n\n"
            "\u7ee7\u7eed\uff1f",
        "safety_review_scan_all_info":
            "\u6b63\u5728\u626b\u63cf {count} \u5f20\u56fe\u7247"
            " \u2014 \u751f\u6b96\u5668\u4f1a\u88ab\u6253\u7801\uff0c"
            "\u4e73\u5934\u4e0d\u4f1a\u88ab\u5904\u7406\u3002",
        "safety_review_scan_all_done":
            "\u5b8c\u6210 \u2014 \u5df2\u5904\u7406 {success}/{total}"
            " \u5f20\u56fe\u7247\uff0c"
            "\u6253\u7801 {regions} \u4e2a\u533a\u57df\uff0c"
            "{failed} \u5f20\u5931\u8d25\u3002",
        "safety_review_quick":
            "\u5b89\u5168\u5ba1\u6838 \u2014 \u5feb\u901f\u6253\u7801",
        "safety_review_source": "\u6765\u6e90\uff1a",
        "safety_review_info":
            "\u68c0\u6d4b\u5e76\u6253\u7801\u88f8\u9732\u7684"
            "\u751f\u6b96\u5668\uff08\u7537\u5973\uff09\u3002"
            "\u4e73\u5934\u4e0d\u4f1a\u88ab\u6253\u7801\u3002",
        "safety_review_block_size":
            "\u9a6c\u8d5b\u514b\u5927\u5c0f (px)\uff1a",
        "safety_review_padding":
            "\u533a\u57df\u5916\u6269 (px)\uff1a",
        "safety_review_overwrite":
            "\u8986\u76d6\u539f\u59cb\u6587\u4ef6\uff08\u4e0d\u5907\u4efd\uff01\uff09",
        "safety_review_overwrite_single":
            "\u8986\u76d6\u539f\u59cb\u6587\u4ef6",
        "safety_review_output_dir":
            "\u8f93\u51fa\u6587\u4ef6\u5939\uff1a",
        "safety_review_run": "\u6267\u884c\u6253\u7801",
        "safety_review_done":
            "\u5b8c\u6210\uff01\u5df2\u4fdd\u5b58\u81f3\uff1a{path}",
        "safety_review_done_short": "\u6253\u7801\u5b8c\u6210\uff01",
        "safety_review_nothing":
            "\u672a\u68c0\u6d4b\u5230\u751f\u6b96\u5668"
            " \u2014 \u56fe\u7247\u672a\u53d8\u66f4\u3002",
        "safety_review_batch_done":
            "\u5df2\u5904\u7406 {success}/{total} \u5f20\u56fe\u7247",
        "safety_review_close": "\u5173\u95ed",
        "safety_review_time":
            "\u5df2\u7ecf\u8fc7: {elapsed}    \u9884\u8ba1: {eta}    (~{speed:.1f}\u79d2 / \u5f20)",
        "safety_review_mode": "\u68c0\u6d4b\u6a21\u5f0f\uff1a",
        "safety_review_mode_real": "\u771f\u4eba\u7167\u7247",
        "safety_review_mode_anime": "\u52a8\u6f2b / \u63d2\u753b",
        "safety_review_confidence": "\u6700\u4f4e\u7f6e\u4fe1\u5ea6\uff1a",
        "safety_review_start": "\u5f00\u59cb",
        "safety_review_installing": "\u6b63\u5728\u5b89\u88c5\u4f9d\u8d56\u5305\u2026",
        "safety_review_expand_pct": "\u68c0\u6d4b\u6846\u6269\u5f20 (%)\uff1a",
        "safety_review_scan_folder": "\u6e90\u6587\u4ef6\u5939\uff1a",
        "safety_review_scan_folder_hint":
            "\u9009\u62e9\u8981\u626b\u63cf\u7684\u6587\u4ef6\u5939",
        "safety_review_mode_auto": "\u81ea\u52a8\u5224\u65ad",
        "safety_review_style": "\u6253\u7801\u6837\u5f0f\uff1a",
        "safety_review_style_mosaic": "\u9a6c\u8d5b\u514b",
        "safety_review_style_blur": "\u9ad8\u65af\u6a21\u7cca",
        "safety_review_style_black": "\u9ed1\u6761\u906e\u6321",
        "safety_review_categories": "\u68c0\u6d4b\u7c7b\u522b\uff1a",
        "safety_review_cat_genitalia": "\u751f\u6b96\u5668 (\u9634\u830e / \u9634\u9053)",
        "safety_review_cat_anus": "\u809b\u95e8",
        "safety_review_cat_nipple": "\u4e73\u5934 / \u4e73\u623f",
        "safety_review_cat_sexual_act": "\u6027\u884c\u4e3a (\u4ec5\u52a8\u6f2b)",
    },
    "Japanese": {
        "safety_review_title":
            "\u5b89\u5168\u5be9\u67fb \u2014 \u81ea\u52d5\u30e2\u30b6\u30a4\u30af",
        "safety_review_batch_title":
            "\u4e00\u62ec\u5b89\u5168\u5be9\u67fb",
        "safety_review_scan_all":
            "\u5b89\u5168\u5be9\u67fb \u2014 \u5168\u753b\u50cf\u30b9\u30ad\u30e3\u30f3",
        "safety_review_scan_all_title":
            "\u5b89\u5168\u5be9\u67fb \u2014 \u5168\u30b9\u30ad\u30e3\u30f3",
        "safety_review_scan_all_confirm":
            "{count}\u679a\u306e\u753b\u50cf\u3092\u30b9\u30ad\u30e3\u30f3\u3057\u3001"
            "\u691c\u51fa\u3055\u308c\u305f\u6027\u5668\u3092\u539f\u30d5\u30a1\u30a4\u30eb\u306b"
            "\u76f4\u63a5\u30e2\u30b6\u30a4\u30af\u3057\u307e\u3059\u3002\n\n"
            "\u4e73\u9996\u306f\u30e2\u30b6\u30a4\u30af\u3055\u308c\u307e\u305b\u3093\u3002\n\n"
            "\u7d9a\u884c\u3057\u307e\u3059\u304b\uff1f",
        "safety_review_scan_all_info":
            "{count}\u679a\u306e\u753b\u50cf\u3092\u30b9\u30ad\u30e3\u30f3\u4e2d"
            " \u2014 \u6027\u5668\u306f\u30e2\u30b6\u30a4\u30af\u3001"
            "\u4e73\u9996\u306f\u305d\u306e\u307e\u307e\u3002",
        "safety_review_scan_all_done":
            "\u5b8c\u4e86 \u2014 {success}/{total}\u679a\u51e6\u7406\u3001"
            "{regions}\u7b87\u6240\u30e2\u30b6\u30a4\u30af\u3001"
            "{failed}\u679a\u5931\u6557\u3002",
        "safety_review_quick":
            "\u5b89\u5168\u5be9\u67fb \u2014 \u30af\u30a4\u30c3\u30af\u30e2\u30b6\u30a4\u30af",
        "safety_review_source": "\u30bd\u30fc\u30b9\uff1a",
        "safety_review_info":
            "\u9732\u51fa\u3057\u305f\u6027\u5668\uff08\u7537\u5973\uff09\u3092"
            "\u691c\u51fa\u3057\u3066\u30e2\u30b6\u30a4\u30af\u3057\u307e\u3059\u3002"
            "\u4e73\u9996\u306f\u30e2\u30b6\u30a4\u30af\u3055\u308c\u307e\u305b\u3093\u3002",
        "safety_review_block_size":
            "\u30e2\u30b6\u30a4\u30af\u30b5\u30a4\u30ba (px)\uff1a",
        "safety_review_padding":
            "\u9818\u57df\u62e1\u5f35 (px)\uff1a",
        "safety_review_overwrite":
            "\u5143\u30d5\u30a1\u30a4\u30eb\u3092\u4e0a\u66f8\u304d"
            "\uff08\u30d0\u30c3\u30af\u30a2\u30c3\u30d7\u306a\u3057\uff01\uff09",
        "safety_review_overwrite_single":
            "\u5143\u30d5\u30a1\u30a4\u30eb\u3092\u4e0a\u66f8\u304d",
        "safety_review_output_dir":
            "\u51fa\u529b\u30d5\u30a9\u30eb\u30c0\uff1a",
        "safety_review_run": "\u30e2\u30b6\u30a4\u30af\u9069\u7528",
        "safety_review_done":
            "\u5b8c\u4e86\uff01\u4fdd\u5b58\u5148\uff1a{path}",
        "safety_review_done_short":
            "\u30e2\u30b6\u30a4\u30af\u5b8c\u4e86\uff01",
        "safety_review_nothing":
            "\u6027\u5668\u672a\u691c\u51fa"
            " \u2014 \u753b\u50cf\u672a\u5909\u66f4\u3002",
        "safety_review_batch_done":
            "{success}/{total}\u679a\u306e\u753b\u50cf\u3092\u51e6\u7406\u3057\u307e\u3057\u305f",
        "safety_review_close": "\u9589\u3058\u308b",
        "safety_review_time":
            "\u7d4c\u904e: {elapsed}    \u6b8b\u308a: {eta}    (~{speed:.1f}\u79d2 / \u679a)",
        "safety_review_mode": "\u691c\u51fa\u30e2\u30fc\u30c9\uff1a",
        "safety_review_mode_real": "\u5b9f\u5199\u771f",
        "safety_review_mode_anime": "\u30a2\u30cb\u30e1 / \u30a4\u30e9\u30b9\u30c8",
        "safety_review_confidence": "\u6700\u4f4e\u4fe1\u983c\u5ea6\uff1a",
        "safety_review_start": "\u958b\u59cb",
        "safety_review_installing":
            "\u4f9d\u5b58\u30d1\u30c3\u30b1\u30fc\u30b8\u3092\u30a4\u30f3\u30b9\u30c8\u30fc\u30eb\u4e2d\u2026",
        "safety_review_expand_pct":
            "\u691c\u51fa\u30dc\u30c3\u30af\u30b9\u62e1\u5f35 (%)\uff1a",
        "safety_review_scan_folder": "\u30bd\u30fc\u30b9\u30d5\u30a9\u30eb\u30c0\uff1a",
        "safety_review_scan_folder_hint":
            "\u30b9\u30ad\u30e3\u30f3\u3059\u308b\u30d5\u30a9\u30eb\u30c0\u3092\u9078\u629e",
        "safety_review_mode_auto": "\u81ea\u52d5\u5224\u5b9a",
        "safety_review_style": "\u30e2\u30b6\u30a4\u30af\u30b9\u30bf\u30a4\u30eb\uff1a",
        "safety_review_style_mosaic": "\u30e2\u30b6\u30a4\u30af",
        "safety_review_style_blur": "\u30ac\u30a6\u30b7\u30a2\u30f3\u30d6\u30e9\u30fc",
        "safety_review_style_black": "\u9ed2\u30d0\u30fc",
        "safety_review_categories": "\u691c\u51fa\u30ab\u30c6\u30b4\u30ea\uff1a",
        "safety_review_cat_genitalia": "\u6027\u5668 (\u30da\u30cb\u30b9 / \u30f4\u30a1\u30ae\u30ca)",
        "safety_review_cat_anus": "\u808b\u9580",
        "safety_review_cat_nipple": "\u4e73\u9996 / \u4e73\u623f",
        "safety_review_cat_sexual_act": "\u6027\u884c\u70ba (\u30a2\u30cb\u30e1\u306e\u307f)",
    },
    "Korean": {
        "safety_review_title":
            "\uc548\uc804 \uac80\ud1a0 \u2014 \uc790\ub3d9 \ubaa8\uc790\uc774\ud06c",
        "safety_review_batch_title":
            "\uc77c\uad04 \uc548\uc804 \uac80\ud1a0",
        "safety_review_scan_all":
            "\uc548\uc804 \uac80\ud1a0 \u2014 \ubaa8\ub4e0 \uc774\ubbf8\uc9c0 \uc2a4\uca94",
        "safety_review_scan_all_title":
            "\uc548\uc804 \uac80\ud1a0 \u2014 \uc804\uccb4 \uc2a4\ucafc",
        "safety_review_scan_all_confirm":
            "{count}\uac1c\uc758 \uc774\ubbf8\uc9c0\ub97c \uc2a4\ucafc\ud558\uace0 "
            "\uac10\uc9c0\ub41c \uc131\uae30\ub97c \uc6d0\ubcf8 \ud30c\uc77c\uc5d0 "
            "\uc9c1\uc811 \ubaa8\uc790\uc774\ud06c\ud569\ub2c8\ub2e4.\n\n"
            "\uc720\ub450\ub294 \ubaa8\uc790\uc774\ud06c\ub418\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.\n\n"
            "\uacc4\uc18d\ud558\uc2dc\uaca0\uc2b5\ub2c8\uae4c?",
        "safety_review_scan_all_info":
            "{count}\uac1c \uc774\ubbf8\uc9c0 \uc2a4\ucafc \uc911"
            " \u2014 \uc131\uae30 \ubaa8\uc790\uc774\ud06c, "
            "\uc720\ub450 \ubbf8\ucc98\ub9ac.",
        "safety_review_scan_all_done":
            "\uc644\ub8cc \u2014 {success}/{total}\uac1c \ucc98\ub9ac, "
            "{regions}\uac1c \uc601\uc5ed \ubaa8\uc790\uc774\ud06c, "
            "{failed}\uac1c \uc2e4\ud328.",
        "safety_review_quick":
            "\uc548\uc804 \uac80\ud1a0 \u2014 \ube60\ub978 \ubaa8\uc790\uc774\ud06c",
        "safety_review_source": "\uc18c\uc2a4:",
        "safety_review_info":
            "\ub178\ucd9c\ub41c \uc131\uae30(\ub0a8\ub140)\ub97c "
            "\uac10\uc9c0\ud558\uc5ec \ubaa8\uc790\uc774\ud06c\ud569\ub2c8\ub2e4. "
            "\uc720\ub450\ub294 \ubaa8\uc790\uc774\ud06c\ub418\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
        "safety_review_block_size":
            "\ubaa8\uc790\uc774\ud06c \ud06c\uae30 (px):",
        "safety_review_padding":
            "\uc601\uc5ed \ud655\uc7a5 (px):",
        "safety_review_overwrite":
            "\uc6d0\ubcf8 \ud30c\uc77c \ub36e\uc5b4\uc4f0\uae30"
            " (\ubc31\uc5c5 \uc5c6\uc74c!)",
        "safety_review_overwrite_single":
            "\uc6d0\ubcf8 \ud30c\uc77c \ub36e\uc5b4\uc4f0\uae30",
        "safety_review_output_dir":
            "\ucd9c\ub825 \ud3f4\ub354:",
        "safety_review_run": "\ubaa8\uc790\uc774\ud06c \uc801\uc6a9",
        "safety_review_done":
            "\uc644\ub8cc! \uc800\uc7a5 \uc704\uce58: {path}",
        "safety_review_done_short":
            "\ubaa8\uc790\uc774\ud06c \uc644\ub8cc!",
        "safety_review_nothing":
            "\uc131\uae30 \ubbf8\uac10\uc9c0"
            " \u2014 \uc774\ubbf8\uc9c0 \ubcc0\uacbd \uc5c6\uc74c.",
        "safety_review_batch_done":
            "{success}/{total}\uac1c \uc774\ubbf8\uc9c0 \ucc98\ub9ac \uc644\ub8cc",
        "safety_review_close": "\ub2eb\uae30",
        "safety_review_time":
            "\uacbd\uacfc: {elapsed}    \ub0a8\uc740 \uc2dc\uac04: {eta}    (~{speed:.1f}\ucd08 / \uc7a5)",
        "safety_review_mode": "\uac10\uc9c0 \ubaa8\ub4dc:",
        "safety_review_mode_real": "\uc2e4\uc0ac\uc9c4",
        "safety_review_mode_anime": "\uc560\ub2c8\uba54\uc774\uc158 / \uc77c\ub7ec\uc2a4\ud2b8",
        "safety_review_confidence": "\ucd5c\uc18c \uc2e0\ub8b0\ub3c4:",
        "safety_review_start": "\uc2dc\uc791",
        "safety_review_installing":
            "\uc758\uc874\uc131 \ud328\ud0a4\uc9c0 \uc124\uce58 \uc911\u2026",
        "safety_review_expand_pct":
            "\uac10\uc9c0 \ubc15\uc2a4 \ud655\uc7a5 (%)\uff1a",
        "safety_review_scan_folder": "\uc18c\uc2a4 \ud3f4\ub354:",
        "safety_review_scan_folder_hint":
            "\uc2a4\ucafc\ud560 \ud3f4\ub354\ub97c \uc120\ud0dd\ud558\uc138\uc694",
        "safety_review_mode_auto": "\uc790\ub3d9 \uac10\uc9c0",
        "safety_review_style": "\ubaa8\uc790\uc774\ud06c \uc2a4\ud0c0\uc77c:",
        "safety_review_style_mosaic": "\ubaa8\uc790\uc774\ud06c",
        "safety_review_style_blur": "\uac00\uc6b0\uc2dc\uc548 \ube14\ub7ec",
        "safety_review_style_black": "\uac80\uc740 \ub9c9\ub300",
        "safety_review_categories": "\uac10\uc9c0 \uce74\ud14c\uace0\ub9ac:",
        "safety_review_cat_genitalia": "\uc131\uae30 (\uc74c\uacbd / \uc9c8)",
        "safety_review_cat_anus": "\ud56d\ubb38",
        "safety_review_cat_nipple": "\uc720\ub450 / \uc720\ubc29",
        "safety_review_cat_sexual_act": "\uc131\ud589\uc704 (\uc560\ub2c8\uba54\uc774\uc158\ub9cc)",
    },
}
