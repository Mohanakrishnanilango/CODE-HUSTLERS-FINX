"""
Faster R-CNN Inference Service for Side-Scan Sonar Imagery.
SIH26057 - Underwater Marine Debris & Anomaly Detection System.
"""
from pathlib import Path
from typing import List, Dict, Any
import torch
import torchvision
from PIL import Image

CLASS_NAMES = {
    0: "background",
    1: "fishing_gear",
    2: "ghost_net",
    3: "pipeline",
    4: "shipwreck",
    5: "mine_cylinder",
}

class FasterRCNNDetectorService:
    def __init__(self, checkpoint_path: str = None, conf_threshold: float = 0.50):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.conf_threshold = conf_threshold
        self.model = None
        self.checkpoint_path = checkpoint_path
        self._init_model()

    def _init_model(self):
        try:
            from torchvision.models.detection import fasterrcnn_resnet50_fpn, FasterRCNN_ResNet50_FPN_Weights
            from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

            # Build Faster R-CNN with ResNet-50 FPN backbone
            weights = FasterRCNN_ResNet50_FPN_Weights.DEFAULT
            self.model = fasterrcnn_resnet50_fpn(weights=weights, min_size=320, max_size=640)
            in_features = self.model.roi_heads.box_predictor.cls_score.in_features
            self.model.roi_heads.box_predictor = FastRCNNPredictor(in_features, len(CLASS_NAMES))

            if self.checkpoint_path and Path(self.checkpoint_path).exists():
                checkpoint = torch.load(self.checkpoint_path, map_location=self.device)
                if "model_state" in checkpoint:
                    self.model.load_state_dict(checkpoint["model_state"])
                else:
                    self.model.load_state_dict(checkpoint)
                print(f"[FasterRCNN] Loaded weights from {self.checkpoint_path}")

            self.model.to(self.device)
            self.model.eval()
            print(f"[FasterRCNN] Inference engine initialized on {self.device}")
        except Exception as e:
            print(f"[FasterRCNN] Initialization note: {e}")

    def predict_image(self, image_path: str) -> List[Dict[str, Any]]:
        """Runs Faster R-CNN inference on a side-scan sonar image."""
        if self.model is None:
            return []

        img = Image.open(image_path).convert("RGB")
        to_tensor = torchvision.transforms.ToTensor()
        tensor = to_tensor(img).to(self.device).unsqueeze(0)

        with torch.no_grad():
            predictions = self.model(tensor)[0]

        results = []
        boxes = predictions["boxes"].cpu().numpy()
        scores = predictions["scores"].cpu().numpy()
        labels = predictions["labels"].cpu().numpy()

        for box, score, label in zip(boxes, scores, labels):
            if score >= self.conf_threshold:
                cls_name = CLASS_NAMES.get(int(label), "unknown")
                # Format box: [x, y, width, height]
                x1, y1, x2, y2 = box
                results.append({
                    "object_class": cls_name,
                    "confidence": float(score),
                    "bbox": [float(x1), float(y1), float(x2 - x1), float(y2 - y1)]
                })

        return results
