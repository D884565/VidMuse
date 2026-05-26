import os

import cv2
import numpy as np


width, height = 640, 480
fps = 30
seconds_per_transition = 2
output_file = os.path.join(os.path.dirname(__file__), "test_color_transition_video.mp4")

# OpenCV uses BGR color order.
colors = [
    (0, 0, 255),      # red
    (0, 255, 0),      # green
    (255, 0, 0),      # blue
    (255, 0, 255),    # purple
    (0, 0, 255),      # red
]

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))

frames_per_transition = fps * seconds_per_transition

for start_color, end_color in zip(colors, colors[1:]):
    start = np.array(start_color, dtype=np.float32)
    end = np.array(end_color, dtype=np.float32)

    for frame_index in range(frames_per_transition):
        ratio = frame_index / frames_per_transition
        color = ((1 - ratio) * start + ratio * end).astype(np.uint8)
        frame = np.full((height, width, 3), color, dtype=np.uint8)
        out.write(frame)

out.release()
print(f"video generated: {output_file}")
