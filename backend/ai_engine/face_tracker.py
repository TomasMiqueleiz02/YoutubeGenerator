import logging
from typing import List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class FaceTracker:
    """
    Works out where to place a 9:16 crop so the speaker stays in frame.

    A fixed centre crop is wrong whenever the subject is off-centre, which is
    most interview, podcast and stage footage. This samples faces across the
    clip and returns a single horizontal offset, deliberately not a per-frame
    one: a crop window that chases every detection looks like a shaky camera.
    """

    def __init__(self, samples: int = 24):
        self.samples = samples
        self._cascade = None

    def _detector(self):
        if self._cascade is None:
            # Haar cascades ship with OpenCV, so this needs no model download
            # and runs fast enough on CPU for a couple of dozen frames.
            path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._cascade = cv2.CascadeClassifier(path)
        return self._cascade

    def find_crop_center(
        self, video_path: str, start_time: float, end_time: float
    ) -> Optional[float]:
        """
        Return where to centre the crop, as a 0..1 fraction of frame width.

        None means no face was found and the caller should keep its default.
        """
        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            return None

        try:
            fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
            width = capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0
            if not width:
                return None

            detector = self._detector()
            height = capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0
            centers: List[float] = []

            duration = max(0.1, end_time - start_time)
            step = duration / self.samples

            for i in range(self.samples):
                timestamp = start_time + i * step
                capture.set(cv2.CAP_PROP_POS_FRAMES, int(timestamp * fps))
                ok, frame = capture.read()
                if not ok:
                    continue

                # Detection accuracy does not need full resolution, and the
                # downscale is what keeps this fast.
                small = cv2.resize(frame, (480, int(480 * frame.shape[0] / frame.shape[1])))
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                faces = detector.detectMultiScale(gray, 1.15, 6, minSize=(36, 36))
                if len(faces) == 0:
                    continue

                # Only the largest face in each frame: averaging across every
                # detection lets blurry background faces in a crowd drag the
                # crop away from the speaker, which framed them worse than a
                # plain centre crop did.
                x, _y, w, _h = max(faces, key=lambda f: f[2] * f[3])
                centers.append((x + w / 2) / small.shape[1])

            if not centers:
                logger.info("No faces found in %.1f-%.1f", start_time, end_time)
                return None

            # Median over the mean: one bad frame should not move the crop.
            center = float(np.median(centers))

            spread = float(np.std(centers))
            if spread > 0.18:
                # Subjects moving across frame, or unstable detection. A fixed
                # off-centre crop would be a gamble, so decline instead.
                logger.info("Face positions too scattered (sd=%.2f); centring", spread)
                return None

            if not height:
                return center

            # The crop window is (height * 9/16) wide, so as a fraction of the
            # frame its half-width is that over the frame width. Clamping with
            # anything else lets the window run past the edge.
            half_window = (height * 9 / 16) / (2 * width)
            return min(max(center, half_window), 1 - half_window)

        finally:
            capture.release()

    @staticmethod
    def crop_filter(center_fraction: Optional[float]) -> str:
        """
        Build the ffmpeg crop+scale filter for a 9:16 vertical clip.

        Falls back to a centred crop when no face was located.
        """
        if center_fraction is None:
            return "crop=ih*9/16:ih,scale=1080:1920"

        # x is the crop's left edge: the face centre minus half the window,
        # clamped by ffmpeg so it can never run past the frame.
        return (
            "crop=ih*9/16:ih:"
            "'min(max(iw*%.4f-ih*9/32,0),iw-ih*9/16)':0,"
            "scale=1080:1920" % center_fraction
        )
