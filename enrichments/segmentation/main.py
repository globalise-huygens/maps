import os
import uuid
import json
from itertools import count

import torch
from segment_anything import sam_model_registry
from segment_anything import SamAutomaticMaskGenerator
from pycocotools import mask as mask_utils

from PIL import Image
import numpy as np

# import cv2

Image.MAX_IMAGE_PIXELS = None  # Disable DecompressionBombError

MODEL = "./model/sam_vit_l_0b3195.pth"  # large model
MODEL_TYPE = "vit_l"
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

# Thresholds
IOU = 0.9
STABILITY = 0.8
AREA_THRESHOLD = 100
BORDER_THRESHOLD = 0

ncounter = count()


def get_resized_images(image: Image, window_size: int, resize_factor: int = 2):
    # image_bgr = cv2.imread(image)
    # image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    width, height = image.size

    # height, width, _ = image_bgr.shape

    # Let's make sure the image's size is divisible by the resize factor,
    # then we can easily resize the image and transpose the masks. This works by cropping.
    while height % resize_factor != 0:
        image = image.crop((0, 0, width, height - 1))
        # image_rgb = image_rgb[:-1, :, :]
        height -= 1

    while width % resize_factor != 0:
        image = image.crop((0, 0, width - 1, height))
        # image_rgb = image_rgb[:, :-1, :]
        width -= 1

    # Get a minimum factor to resize the image to the window size
    f_min = min(window_size / width, window_size / height)

    n = 0

    original_width, original_height = width, height

    while width > window_size or height > window_size:

        # if n < 2:
        #     n += 1
        #     continue

        print(f"The image was {width}x{height}, ", end="")

        f = max(f_min, resize_factor**-n)

        # resized_image = cv2.resize(image_rgb, None, fx=f, fy=f)
        resized_image = image.resize(
            (int(original_width * f), int(original_height * f)),
            Image.Resampling.LANCZOS,
        )

        n += 1
        width, height = resized_image.size

        print(f"resizing to {f*100}%: {width}x{height}")
        yield f, resized_image


def get_image_cutouts(image: Image, window_size: int, step_size: int):
    width, height = image.size

    # rolling window
    for y in range(0, height, step_size):
        for x in range(0, width, step_size):
            # cropped_image = image[y : y + window_size, x : x + window_size]

            cropped_image = image.crop((x, y, x + window_size, y + window_size))

            yield x, y, cropped_image


def process_image(
    image: Image,
    x: int,
    y: int,
    original_image: Image,
    original_width: int,
    original_height: int,
    resize_factor: float,
    mask_generator: SamAutomaticMaskGenerator,
    output_folder: str = "",
    border_threshold: int = BORDER_THRESHOLD,
    folder_prefix: str = "",
):

    f_i = 1 / resize_factor

    width, height = image.size
    # image_rgba = cv2.cvtColor(image, cv2.COLOR_BGR2RGBA)

    data = {
        "x": int(x * f_i),
        "y": int(y * f_i),
        "f": resize_factor,
        "width": int(width * f_i),
        "height": int(height * f_i),
        "results": [],
    }

    # start at 0
    width -= 1
    height -= 1

    print(f"Processing cutout {data['x']}x{data['y']}")

    # index_count = next(ncounter)

    # original image crop
    original_image_crop = original_image.crop(
        (data["x"], data["y"], data["x"] + data["width"], data["y"] + data["height"])
    )
    original_image_crop_rgba = original_image_crop.convert("RGBA")

    # image.save(os.path.join(output_folder, f"{folder_prefix}_{index_count}.png"))
    # original_image_crop_rgba.save(
    #     os.path.join(output_folder, f"{folder_prefix}_{index_count}_original.png")
    # )

    results = mask_generator.generate(np.array(image))

    for r in results:

        del r["crop_box"]

        r["uuid"] = str(uuid.uuid4())

        # bbox coords
        r_x1, r_y1, r_w, r_h = r["bbox"]

        r_x1 = int(r_x1)
        r_x2 = r_x1 + int(r_w)
        r_y1 = int(r_y1)
        r_y2 = r_y1 + int(r_h)

        if (  # Check if the object is too close to the border of the cutout
            r_x1 <= border_threshold
            or r_y1 <= border_threshold
            or r_x2 >= width - border_threshold
            or r_y2 >= height - border_threshold
        ) and not (  # it's fine if it's close to the border of the original image
            r_x1 + x == 0
            or r_y1 + y == 0
            or r_x2 + x == original_width
            or r_y2 + y == original_height
        ):
            continue

        # Only keep the mask for the bbox
        m = mask_utils.decode(r["segmentation"])
        # m = m[r_y1:r_y2, r_x1:r_x2]

        # # Transform according to the resize factor
        # m = cv2.resize(m, None, fx=f_i, fy=f_i)
        m = Image.fromarray(m, "L").resize(
            (int((width + 1) * f_i), int((height + 1) * f_i)), Image.Resampling.LANCZOS
        )

        # Transform the coordinates to the original image's size
        r["bbox"] = [  # bbox
            int(r_x1 * f_i),
            int(r_y1 * f_i),
            int(r_w * f_i),
            int(r_h * f_i),
        ]

        r["point_coords"] = [  # points
            [
                int((r[0] + x) * f_i),
                int((r[1] + y) * f_i),
            ]
            for r in r["point_coords"]
        ]

        # # m = mask_utils.decode(r["segmentation"])
        # m_height, m_width = m.shape
        # m_height, m_width = m.size

        # # Transform the cutout mask to the original image's size
        # mask = np.zeros((original_height, original_width), dtype=np.uint8)
        # mask[y : y + m_height, x : x + m_width] = m

        m_encoded = mask_utils.encode(np.asfortranarray(m))
        m_encoded["counts"] = m_encoded["counts"].decode("utf-8")
        r["segmentation"] = m_encoded

        data["results"].append(r)

        if output_folder:
            mask = mask_utils.decode(r["segmentation"])

            output_folder_prefix = os.path.join(output_folder, folder_prefix)
            os.makedirs(output_folder_prefix, exist_ok=True)

            # cv2
            # image_rgba = np.array(image.convert("RGBA"))

            # masked_image = cv2.bitwise_and(image_rgba, image_rgba, mask=mask)
            # masked_image[:, :, 3] = mask * 255  # alpha channel

            # cutout = masked_image[r_y1:r_y2, r_x1:r_x2]  # bbox
            # cutout = cv2.cvtColor(cutout, cv2.COLOR_BGR2RGBA)

            # cv2.imwrite(os.path.join(output_folder_prefix, f"{r['uuid']}.png"))", cutout)

            ## PIL
            masked_image_array = np.array(original_image_crop_rgba)

            masked_image_array[:, :, 3] = mask * 255  # alpha channel
            masked_image = Image.fromarray(masked_image_array, "RGBA")

            r_x1, r_y1, r_w, r_h = r["bbox"]

            r_x1 = int(r_x1)
            r_x2 = r_x1 + int(r_w)
            r_y1 = int(r_y1)
            r_y2 = r_y1 + int(r_h)

            cutout = masked_image.crop((r_x1, r_y1, r_x2, r_y2))  # bbox

            cutout.save(os.path.join(output_folder_prefix, f"{r['uuid']}.png"))

    return data


def main(
    images: list,
    output_folder: str,
    window_size: int = 1000,  # to take VRAM into account
    step_size: int = 500,
    model: str = MODEL,
    model_type: str = MODEL_TYPE,
    device: str = DEVICE,
    iou: float = IOU,
    stability: float = STABILITY,
    area_threshold: int = AREA_THRESHOLD,
):
    sam = sam_model_registry[model_type](checkpoint=model)
    sam.to(device=device)

    mask_generator = SamAutomaticMaskGenerator(
        sam,
        pred_iou_thresh=iou,
        stability_score_thresh=stability,
        min_mask_region_area=area_threshold,
        output_mode="coco_rle",
    )

    for image_path in images:
        image_name = os.path.basename(image_path)
        image_name_without_extension = os.path.splitext(image_name)[0]

        image_output_folder = os.path.join(output_folder, image_name_without_extension)
        os.makedirs(image_output_folder, exist_ok=True)

        # height, width, _ = cv2.imread(image_path).shape
        image = Image.open(image_path)
        width, height = image.size

        data = {
            "image": image_name,
            "height": height,
            "width": width,
            "cutouts": [],
        }

        resized_images = get_resized_images(image, window_size)

        for f, resized_image in resized_images:

            for x, y, cutout in get_image_cutouts(
                resized_image, window_size, step_size
            ):
                result = process_image(
                    cutout,
                    x=x,
                    y=y,
                    original_image=image,
                    original_height=height,
                    original_width=width,
                    resize_factor=f,
                    mask_generator=mask_generator,
                    output_folder=image_output_folder,
                    folder_prefix=f'{"%.4f" % f}',
                )

                data["cutouts"].append(result)

                # break

        with open(
            os.path.join(image_output_folder, f"{image_name_without_extension}.json"),
            "w",
        ) as outfile:
            json.dump(data, outfile, indent=1)

        # TODO: deduplicate results (due to overlapping windows)
        # TODO: merge or cluster overlapping results (IOU)


if __name__ == "__main__":
    OUTPUT_FOLDER = "./example/output"
    EXAMPLE = "./example/7beaf613-68bf-4070-b79b-bb5c9282edcd.jpg"
    images = [EXAMPLE]

    main(images, output_folder=OUTPUT_FOLDER)
