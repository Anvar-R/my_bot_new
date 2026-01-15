from PIL import Image
import os
import time


def DifferenceHash(theImage):

	# Convert the image to 8-bit grayscale.
	theImage = theImage.convert("L") # 8-bit grayscale

	# Squeeze it down to an 8x8 image.
	theImage = theImage.resize((8,8), Image.Resampling.LANCZOS)

	# Go through the image pixel by pixel.
	# Return 1-bits when a pixel is equal to or brighter than the previous
	# pixel, and 0-bits when it's below.

	# Use the 64th pixel as the 0th pixel.
	previousPixel = theImage.getpixel((0, 7))

	differenceHash = 0
	for row in range(0, 8, 2):

		# Go left to right on odd rows.
		for col in range(8):
			differenceHash <<= 1
			pixel = theImage.getpixel((col, row))
			differenceHash |= 1 * (pixel >= previousPixel)
			previousPixel = pixel

		row += 1

		# Go right to left on even rows.
		for col in range(7, -1, -1):
			differenceHash <<= 1
			pixel = theImage.getpixel((col, row))
			differenceHash |= 1 * (pixel >= previousPixel)
			previousPixel = pixel

	return differenceHash


if __name__ == '__main__':
    images_folder = 'photos/'
    start = time.monotonic()
    images_db = create_image_hash_db(images_folder)
    res = images_db.to_json('images_db.json', orient='records')
    input_img_path = 'photos//photo_32202_1.jpg'
    result_df = images_db[images_db['Hash'] == DifferenceHash(Image.open(input_img_path))]
    print(result_df.iloc[0])
    print(f'Total time: {time.monotonic() - start} seconds')
