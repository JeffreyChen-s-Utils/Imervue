from Imervue.gpu_image_view.deep_zoom_priority import prioritize_tiles


def test_prioritize_tiles_prefers_view_center():
    tiles = [(0, 0), (2, 2), (4, 4)]
    ordered = prioritize_tiles(
        tiles,
        tile_size=100,
        scale_x=1,
        scale_y=1,
        offset_x=0,
        offset_y=0,
        canvas=(500, 500),
    )
    assert ordered[0] == (2, 2)


def test_prioritize_tiles_cursor_biases_order():
    tiles = [(0, 0), (4, 4)]
    ordered = prioritize_tiles(
        tiles,
        tile_size=100,
        scale_x=1,
        scale_y=1,
        offset_x=0,
        offset_y=0,
        canvas=(500, 500),
        cursor=(40, 40),
    )
    assert ordered[0] == (0, 0)

