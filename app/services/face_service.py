import threading

import cv2
import numpy as np
from insightface.app import FaceAnalysis


class FaceService:
    """Wraps InsightFace. Model loading is deferred and shared (singleton)."""

    _instance: "FaceService | None" = None
    _lock = threading.Lock()

    def __new__(cls):
        # Keep a single shared instance across route modules.
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._lock = threading.Lock()
        self.app = None
        self.last_error: str | None = None
        self._init_model()

    def _init_model(self):
        try:
            self.app = FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])
            self.app.prepare(ctx_id=-1)
            self.last_error = None
        except Exception as exc:  # pragma: no cover - environment dependent
            self.app = None
            self.last_error = str(exc)

    @property
    def ready(self) -> bool:
        return self.app is not None

    def health(self) -> dict:
        return {
            "status": "ok" if self.ready else "error",
            "model": "buffalo_sc",
            "engine": "insightface + onnxruntime (CPU)",
            "error": self.last_error,
        }

    async def extract_embedding(self, image_bytes: bytes) -> list[float]:
        if not self.ready:
            raise RuntimeError(
                "Face recognition model is not available: " + (self.last_error or "unknown error")
            )
        np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image bytes into a valid image")

        with self._lock:
            faces = self.app.get(img)

        if len(faces) == 0:
            raise ValueError("No face detected in the image")

        return faces[0].embedding.tolist()

    async def extract_embeddings(self, image_bytes: bytes) -> list[list[float]]:
        """Extract embeddings for all detected faces in the image."""
        if not self.ready:
            raise RuntimeError(
                "Face recognition model is not available: " + (self.last_error or "unknown error")
            )
        np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image bytes into a valid image")

        with self._lock:
            faces = self.app.get(img)

        if len(faces) == 0:
            raise ValueError("No face detected in the image")

        return [face.embedding.tolist() for face in faces]

    @staticmethod
    def embedding_to_blob(embedding: list[float]) -> bytes:
        return np.array(embedding, dtype=np.float32).tobytes()


# Shared singleton used by all route modules.
face_service = FaceService()
