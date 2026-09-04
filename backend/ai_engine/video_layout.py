from typing import Optional

# Vertical canvas every layout renders into
CANVAS_W = 1080
CANVAS_H = 1920


class VideoLayout:
    """
    Builds the ffmpeg filter that turns a landscape source into a 9:16 clip.

    Two strategies, and they fail in opposite directions:

    - "fit" keeps the whole frame and fills the empty space with a blurred,
      dimmed copy of itself. Nothing is ever cut off, which matters for
      football, gameplay, screen shares or any wide shot where the subject
      moves. The subject ends up smaller.
    - "crop" fills the screen by cutting a vertical column out of the frame.
      The subject is large, but everything outside that column is lost.
    """

    FIT = "fit"
    CROP = "crop"

    def __init__(
        self,
        mode: str = FIT,
        blur_strength: int = 28,
        # Sit the video above centre so captions get a clean band underneath
        video_top: int = 420,
    ):
        self.mode = mode
        self.blur_strength = blur_strength
        self.video_top = video_top

    def filter_complex(self, crop_center: Optional[float] = None) -> str:
        """Return the -filter_complex value for this layout."""
        if self.mode == self.CROP:
            return self._crop_filter(crop_center)
        return self._fit_filter()

    def _fit_filter(self) -> str:
        return (
            "[0:v]split=2[bg][fg];"
            # Background: fill the canvas, blur it, and pull the brightness
            # down so it never competes with the real footage.
            "[bg]scale=%d:%d:force_original_aspect_ratio=increase,"
            "crop=%d:%d,gblur=sigma=%d,eq=brightness=-0.06[bg];"
            # Foreground: full width, aspect preserved, nothing cropped.
            "[fg]scale=%d:-2[fg];"
            "[bg][fg]overlay=(W-w)/2:%d"
            % (
                CANVAS_W, CANVAS_H,
                CANVAS_W, CANVAS_H,
                self.blur_strength,
                CANVAS_W,
                self.video_top,
            )
        )

    def _crop_filter(self, crop_center: Optional[float]) -> str:
        if crop_center is None:
            return "[0:v]crop=ih*9/16:ih,scale=%d:%d" % (CANVAS_W, CANVAS_H)
        return (
            "[0:v]crop=ih*9/16:ih:"
            "'min(max(iw*%.4f-ih*9/32,0),iw-ih*9/16)':0,"
            "scale=%d:%d" % (crop_center, CANVAS_W, CANVAS_H)
        )

    @property
    def caption_margin(self) -> int:
        """
        Distance from the bottom of the canvas to the captions.

        In "fit" the video floats above a blurred band; captions belong in that
        band, not on top of the footage. In "crop" the footage fills the frame,
        so they sit over the lower third as usual.
        """
        if self.mode == self.CROP:
            return 420
        # Video occupies video_top .. video_top + (1080*9/16). Put captions
        # in the middle of whatever is left underneath it.
        video_bottom = self.video_top + int(CANVAS_W * 9 / 16)
        remaining = CANVAS_H - video_bottom
        return max(120, int(remaining / 2) - 40)
