from PIL import Image
import pandas as pd
import os
import dlib
import time

detector = dlib.get_frontal_face_detector()

def create_image_hash_db(images_folder: str) -> pd.DataFrame:
    data_dict = dict()
    list_dir = os.listdir(images_folder)
    print(f'{len(list_dir)} images found in the folder "{images_folder}"')
    for file_name in list_dir:
        image_path = os.path.join(images_folder, file_name)
        if os.path.isfile(image_path):
            if not detect_faces(image_path):
                continue
            theImage = Image.open(image_path)
            img_hash = DifferenceHash(theImage)
            data_dict[file_name] = img_hash
    print(f'{len(data_dict)} images appended to the database')           
    return pd.DataFrame(data_dict.items(), columns=['Image', 'Hash'])  

def detect_faces(img_path: str) -> bool:
    img = dlib.load_rgb_image(img_path)
    dets = detector(img, 1)
    return len(dets) > 0

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