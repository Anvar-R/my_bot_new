import torch
from torchvision import transforms
from fastervit import create_model
import cv2
import io

torch.set_num_threads(1)
torch.set_num_interop_threads(1)

model = create_model('faster_vit_0_224',pretrained=False)
num_classes = 4
model.head = torch.nn.Linear(model.head.in_features, num_classes)
model = model.to('cpu')
model.load_state_dict(torch.load('/home/anvar/my_bot/api/fastervit_vit_0_224.pth', map_location='cpu', weights_only=True))
model.eval()

transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((256)),
    transforms.CenterCrop((224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

classes = ["Equip", "Other", "Report", "Selfie"]

def predict_bytes(image_bytes):
    image = cv2.imread(image_bytes)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = transform(image)
    image = transform(image).unsqueeze(0)

    with torch.no_grad():
        outputs = model(image)
        _, predicted = torch.max(outputs, 1)
    print(classes[predicted.item()])
    return classes[predicted.item()]
