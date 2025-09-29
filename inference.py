from typing import Protocol, List
import torch
from create_model import InefficientModel

class InferenceRunner(Protocol):
    def predict_batch(self, batch_features: List[List[float]]) -> List[float]: ...

class TorchModelRunner:
    def __init__(self, model: InefficientModel) -> None:
        self.model = model.eval()

    def predict_batch(self, batch_features: List[List[float]]) -> List[float]:
        x = torch.tensor(batch_features, dtype=torch.float32)
        with torch.inference_mode():
            y = self.model(x)     # [B] or [B,1]
            y = y.reshape(-1)     # ensure [B]
        return y.detach().cpu().tolist()
