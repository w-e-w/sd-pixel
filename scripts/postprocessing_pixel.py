from PIL import Image
from modules import scripts_postprocessing
import gradio as gr

try:
    if hasattr(scripts_postprocessing.ScriptPostprocessing, 'process_firstpass'):  # webui >= 1.7
        from modules.ui_components import InputAccordion
    else:
        InputAccordion = None
except ImportError:
    InputAccordion = None


class GoodInputAccordion:
    def __init__(self, value, label, row=None, **kwargs):
        self.value = value
        self.label = label
        self.kwargs = kwargs
        self.row: gr.Row = row

    def __enter__(self):
        self.accordion = InputAccordion(self.value, label=self.label) if InputAccordion else gr.Accordion(self.label, open=False)
        self.accordion.__enter__()

        if self.row:
            self.row = gr.Row()
            self.row.__enter__()

        return self.accordion if InputAccordion else gr.Checkbox(False, label='Enable')

    def __exit__(self, *args):
        if self.row:
            self.row.__exit__()
        self.accordion.__exit__(*args)


mode_dict = {
    "Nearest": Image.NEAREST,
    "Bicubic": Image.BICUBIC,
    "Bilinear": Image.BILINEAR,
    "Hamming": Image.HAMMING,
    "Lanczos": Image.LANCZOS
}


def downscale_image(img, scale, mode):
    width, height = img.size
    return img.resize(
        (int(width / scale), int(height / scale)),
        mode_dict[str(mode)],
    )


def palette_limit(img, palette_size=16):
    if palette_size > 1:
        img = img.quantize(colors=palette_size, dither=None)
    return img


def rescale_image(img, original_size):
    # rescale the image
    scaled_img = img.resize(original_size, Image.NEAREST)
    return scaled_img


def grayscale_limit(img, gray_limit=155):
    # Convert the image to grayscale
    img_gray = img.convert('L')

    # Create a new image with the same size as the grayscale image, filled with white color
    img_bw = Image.new('L', img_gray.size, color=255)

    # Get the pixel access object for both images
    pixels_gray = img_gray.load()
    pixels_bw = img_bw.load()

    # Loop through each pixel in the grayscale image
    for x in range(img_gray.width):
        for y in range(img_gray.height):
            # If the grayscale pixel is less than or equal to 128,
            # set the corresponding pixel in the black and white image to black
            if pixels_gray[x, y] <= gray_limit:
                pixels_bw[x, y] = 0

    return img_bw


class PostprocessingPixel(scripts_postprocessing.ScriptPostprocessing):
    name = "pixel"
    order = 20000

    def ui(self):
        with GoodInputAccordion(False, "Pixel") as enable:
            with gr.Row():
                # Pixelate and restore scale
                with GoodInputAccordion(False, "Pixelate and Rescale", True) as enable_pixelate:
                    with gr.Row():
                        downscale = gr.Slider(label="Downscale", minimum=1, maximum=32, step=1, value=8)
                        mode = gr.Dropdown(label="Mode", choices=list(mode_dict.keys()), value=list(mode_dict.keys())[0], multiselect=False)
                        rescale = gr.Checkbox(label="Rescale (keep resolution)", value=False)

                # Color palette limit
                with GoodInputAccordion(False, "Color Palette Limit", True) as enable_palette_limit:
                    with gr.Row():
                        palette_size = gr.Slider(label="Palette Size", minimum=0, maximum=256, step=1, value=1)

                # Gray limit
                with GoodInputAccordion(False, "Gray Limit", True) as enable_gray_limit:
                    gray_threshold = gr.Slider(label="Threshold", minimum=0, maximum=255, step=1, value=0)

            return {
                "enable": enable,
                "enable_pixelate": enable_pixelate, "rescale": rescale, "downscale": downscale, "mode": mode,
                "enable_palette_limit": enable_palette_limit, "palette_size": palette_size,
                "enable_gray_limit": enable_gray_limit, "gray_limit": gray_threshold,
            }

    def process(
            self, pp: scripts_postprocessing.PostprocessedImage, enable,
            enable_pixelate, rescale, downscale, mode,
            enable_palette_limit, palette_size,
            enable_gray_limit, gray_limit,
    ):
        if not enable:
            return

        # convert the image to RGBA if it is not already
        img = pp.image if pp.image.mode == 'RGBA' else pp.image.convert('RGBA')

        original_size = img.size
        applied_effects = ""

        if enable_pixelate and downscale > 1:
            img = downscale_image(img, downscale, mode)
            applied_effects += f"Downscale: {downscale}, Mode: {mode}, "

        if enable_palette_limit and palette_size > 1:
            img = palette_limit(img, palette_size)
            applied_effects += f"Color Palette Limit: {palette_size}, "

        if enable_gray_limit and gray_limit > 0:
            img = grayscale_limit(img, gray_limit)
            applied_effects += f"Gray Limit: {gray_limit}, "

        # Pass the original size and the image to the rescale_image function
        if rescale and enable_pixelate:
            img = rescale_image(img, original_size)
            applied_effects += f"rescale, "

        # Convert back to original mode
        pp.image = img.convert(pp.image.mode)

        # Send debug message if effects applied
        if len(applied_effects) > 2:
            print(f"Pixelate with {applied_effects[:-2]}")
