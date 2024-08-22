import io
import os
import random
import turtle
import urllib.request
import urllib.request

import numpy as np
from PIL import Image


# 随机的美
def tt_draw_random():
    turtle.penup()
    turtle.fd(-100)
    turtle.pendown()
    for i in range(100):
        turtle.pensize(random.randint(1, 5))
        turtle.fd(random.randint(10, 50))
        turtle.seth(random.randint(1, 360))
        turtle.speed(random.randint(1, 20))
        turtle.circle(random.randint(1, 360), random.randint(0, 40))

    turtle.done()


def tt_draw_polyhedral():
    turtle.color('red')
    turtle.width(2)
    for x in range(100):
        turtle.fd(2 * x)
        turtle.left(58)

    turtle.done()


def fetch_image(url: str):
    """Fetch image from URL or local path."""
    try:
        if not os.access(url, os.R_OK):
            image_bytes = urllib.request.urlopen(url).read()
            url = io.BytesIO(image_bytes)
    except Exception as e:
        print(f"Error fetching image: {repr(e)}")
        return None
    return url


def resize_image(image, width_pixel: float, height_pixel: float):
    """Resize image based on given width and height multipliers."""
    width, height = image.size
    width, height = round(width * width_pixel), round(height * height_pixel)
    return image.resize((width, height))


def setup_turtle(width, height, pixel_size):
    """Setup turtle graphics environment."""
    turtle.speed(0)
    turtle.delay(0)
    turtle.setup(100 + width * pixel_size, 100 + height * pixel_size, 10, 10)

    turtle.penup()
    turtle.goto(-(width * pixel_size / 2), height * pixel_size / 2)
    turtle.pendown()
    turtle.pensize(pixel_size)
    turtle.tracer(0, 0)


def draw_image(im, width, height, pixel_size):
    """Draw the image using turtle graphics."""
    for i in range(height):
        turtle.penup()
        turtle.goto(-(width * pixel_size / 2), height * pixel_size / 2 - i * pixel_size)
        turtle.pendown()
        for j in range(width):
            r, g, b = im[i, j][:3]
            turtle.pencolor(r, g, b)
            turtle.fd(pixel_size)
        # 每行刷新,保持一些视觉效果
        turtle.update()
    turtle.done()


def tt_draw_picture(url: str, pixel_size: int = 5, width_pixel: float = 1.0, height_pixel: float = 1.0):
    """Main function to draw picture from URL or local path."""
    url = fetch_image(url)
    if not url:
        return

    with Image.open(url) as im:
        im = resize_image(im, width_pixel, height_pixel)
        im = np.array(im) / 255.0
        width, height = im.shape[1], im.shape[0]

        setup_turtle(width, height, pixel_size)
        draw_image(im, width, height, pixel_size)
