
import logging
import signal
import sys
import time
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest
from tasks import classify_image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI()
shutdown_flag = False

REQUEST_COUNT = Counter("imagebot_requests_total", "Total prediction requests")
REQUEST_ERRORS = Counter("imagebot_errors_total", "Total prediction errors")
REQUEST_TIME = Histogram("imagebot_prediction_seconds", "Prediction time in seconds")

def handle_shutdown(sig, frame):
    global shutdown_flag
    shutdown_flag = True
    logger.info("Shutdown signal received")
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")

@app.post("/predict")
async def predict(file: UploadFile = File()):
    if shutdown_flag:
        raise HTTPException(status_code=503, detail="Server shutting down")

    REQUEST_COUNT.inc()
    start_time = time.time()

    try:
        image_bytes = await file.read()
        task = classify_image.delay(image_bytes)
        result = task.get(timeout=30)
        REQUEST_TIME.observe(time.time() - start_time)
        return {"class": result}
    except Exception as e:
        REQUEST_ERRORS.inc()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Prediction failed")
