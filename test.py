import os


def exract_date_from_filename(filename: str) -> str:
    date_part = filename[filename.find('@') + 1:filename.rfind('.')].split('_')[0]
    time_part = filename[filename.find('@') + 1:filename.rfind('.')].split('_')[1]
    return date_part + ' ' + time_part.split('-')[0] + ':' \
        + time_part.split('-')[1] + ':' + time_part.split('-')[2] \
        if len(time_part.split('-')) == 3 else date_part + ' ' + time_part


def create_database():
    imagePath = 'e:/python/photo'
    list_dir = os.listdir(imagePath)
    for file_name in list_dir:
        image_path = os.path.join(imagePath, file_name)
        if os.path.isfile(image_path):
            print(exract_date_from_filename(file_name))


if __name__ == "__main__":  
    create_database()

