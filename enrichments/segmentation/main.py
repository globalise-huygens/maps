import os
import json
from itertools import count

import torch
from segment_anything import sam_model_registry
from segment_anything import SamAutomaticMaskGenerator
from pycocotools import mask as mask_utils

import cv2

MODEL = "./model/sam_vit_l_0b3195.pth"  # large model
MODEL_TYPE = "vit_l"
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

# Thresholds
IOU = 0.9
STABILITY = 0.75
AREA_THRESHOLD = 100
BORDER_THRESHOLD = 0

n = count()


def get_image_cutouts(image, window_size, step_size):
    image_bgr = cv2.imread(image)
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    height, width, _ = image_bgr.shape

    # rolling window
    for y in range(0, height, step_size):
        for x in range(0, width, step_size):
            cropped_image_rgb = image_rgb[y : y + window_size, x : x + window_size]

            yield x, y, cropped_image_rgb


def process_image(
    image,
    x,
    y,
    original_width,
    original_height,
    mask_generator,
    output_folder="",
    border_threshold=BORDER_THRESHOLD,
):

    width, height, _ = image.shape
    image_rgba = cv2.cvtColor(image, cv2.COLOR_BGR2RGBA)

    # start at 0
    width -= 1
    height -= 1

    data = {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "results": [],
    }

    results = mask_generator.generate(image)

    for r in results:

        # bbox coords
        r_x1, r_y1, r_w, r_h = r["bbox"]
        r_x2 = r_x1 + r_w
        r_y2 = r_y1 + r_h

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

        del r["crop_box"]
        data["results"].append(r)

        if output_folder:
            mask = mask_utils.decode(r["segmentation"])

            masked_image = cv2.bitwise_and(image_rgba, image_rgba, mask=mask)
            masked_image[:, :, 3] = mask * 255  # alpha channel

            cutout = masked_image[r_y1:r_y2, r_x1:r_x2]  # bbox

            cv2.imwrite(f"{output_folder}/{next(n)}.png", cutout)

    return data


def main(
    images: list,
    output_folder: str,
    window_size=1000,
    step_size=500,
    model=MODEL,
    model_type=MODEL_TYPE,
    device=DEVICE,
    iou=IOU,
    stability=STABILITY,
    area_threshold=AREA_THRESHOLD,
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

    data = []
    for image_path in images:

        image_name = os.path.basename(image_path)
        image_name_without_extension = os.path.splitext(image_name)[0]

        width, height, _ = cv2.imread(image_path).shape

        for x, y, cutout in get_image_cutouts(image_path, window_size, step_size):

            result = process_image(
                cutout,
                x=x,
                y=y,
                original_height=height,
                original_width=width,
                mask_generator=mask_generator,
                output_folder=output_folder,
            )

            result["image"] = [image_name]

            data.append(result)

        with open(
            f"{output_folder}/{image_name_without_extension}.json", "w"
        ) as outfile:
            json.dump(data, outfile, indent=1)


if __name__ == "__main__":
    EXAMPLE = "./example/7beaf613-68bf-4070-b79b-bb5c9282edcd.jpg"
    images = [EXAMPLE]

    main(images, "./example/output")
