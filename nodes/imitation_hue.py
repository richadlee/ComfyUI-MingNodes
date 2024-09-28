import numpy as np
import cv2
import torch


def image_stats(image):
    means = []
    stds = []
    for channel in range(1, 3):
        means.append(np.mean(image[:, :, channel]))
        stds.append(np.std(image[:, :, channel]))
    return means, stds


def is_skin_or_lips(l, a, b):
    is_skin = (l > 20) and (l < 250) and (a > 120) and (a < 180) and (b > 120) and (b < 190)
    is_lips = (l > 20) and (l < 200) and (a > 150) and (b > 140)
    return is_skin or is_lips


def tensor2cv2(image: torch.Tensor) -> np.array:
    if image.dim() == 4:
        image = image.squeeze()
    npimage = image.numpy()
    cv2image = np.uint8(npimage * 255 / npimage.max())
    return cv2.cvtColor(cv2image, cv2.COLOR_RGB2BGR)


def adjust_brightness(image, factor):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    v = np.clip(v * factor, 0, 255).astype(np.uint8)
    hsv = cv2.merge((h, s, v))
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def color_transfer(source, target, strength=0.8, skin_protection=0.7):
    source_brightness = np.mean(cv2.cvtColor(source, cv2.COLOR_BGR2GRAY))
    target_brightness = np.mean(cv2.cvtColor(target, cv2.COLOR_BGR2GRAY))
    source_lab = cv2.cvtColor(source, cv2.COLOR_BGR2LAB).astype(np.float32)
    target_lab = cv2.cvtColor(target, cv2.COLOR_BGR2LAB).astype(np.float32)
    target_l, target_a, target_b = cv2.split(target_lab)
    src_means, src_stds = image_stats(source_lab)
    tar_means, tar_stds = image_stats(target_lab)
    skin_lips_mask = np.apply_along_axis(lambda x: is_skin_or_lips(*x), 2, target_lab.astype(np.uint8)).astype(
        np.float32)
    skin_lips_mask = cv2.GaussianBlur(skin_lips_mask, (5, 5), 0)
    result_lab = np.zeros_like(target_lab)
    result_lab[:, :, 0] = target_l  # 保持亮度不变
    for i, channel in enumerate([target_a, target_b]):
        adjusted_channel = (channel - tar_means[i]) * (src_stds[i] / (tar_stds[i] + 1e-6)) + src_means[i]
        adjusted_channel = np.clip(adjusted_channel, 0, 255)
        result_channel = channel * skin_lips_mask * skin_protection + \
                         adjusted_channel * skin_lips_mask * (1 - skin_protection) + \
                         adjusted_channel * (1 - skin_lips_mask)

        result_lab[:, :, i + 1] = result_channel
    result_lab = np.clip(result_lab, 0, 255).astype(np.uint8)
    result_bgr = cv2.cvtColor(result_lab, cv2.COLOR_LAB2BGR)
    result_bgr = cv2.GaussianBlur(result_bgr, (3, 3), 0)
    final_result = cv2.addWeighted(target, 1 - strength, result_bgr, strength, 0)

    brightness_difference = source_brightness - target_brightness
    brightness_factor = 1.0
    if brightness_difference < 0:
        brightness_factor = 1.0 + brightness_difference / 255 * 0.3
    elif brightness_difference > 0:
        brightness_factor = 1.0 + brightness_difference / 255 * 0.3
    brightness_factor = np.clip(brightness_factor, 0.7, 1.3)
    final_result = adjust_brightness(final_result, brightness_factor)

    return final_result


class ImitationHueNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "imitation_image": ("IMAGE",),
                "target_image": ("IMAGE",),
                "strength": ("FLOAT", {"default": 0.8, "min": 0.1, "max": 1.0, "step": 0.1}),
                "skin_protection": ("FLOAT", {"default": 0.5, "min": 0.1, "max": 1.0, "step": 0.1}),
            }
        }

    CATEGORY = "MingNodes/Image Process"

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "imitation_hue"

    def imitation_hue(self, imitation_image, target_image, strength, skin_protection):
        for img in imitation_image:
            img_cv1 = tensor2cv2(img)

        for img in target_image:
            img_cv2 = tensor2cv2(img)

        result_img = color_transfer(img_cv1, img_cv2, strength, skin_protection)
        result_img = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
        rst = torch.from_numpy(result_img.astype(np.float32) / 255.0).unsqueeze(0)

        return (rst,)
