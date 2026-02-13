import math


class DeepZoomImage:
    def __init__(self, image_array):
        self.levels = []
        self.build_pyramid(image_array)

    def build_pyramid(self, image):
        current = image
        self.levels.append(current)

        while min(current.shape[:2]) > 512:
            current = current[::2, ::2]
            self.levels.append(current)

    def get_level(self, zoom):
        # zoom 1.0 = full res
        level = int(max(0, min(len(self.levels)-1, -math.log2(zoom))))
        return level, self.levels[level]
