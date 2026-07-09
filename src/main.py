"""FastAPI application for receiving Nuon webhooks and forwarding to DataDog."""

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .webhook_handler import WebhookHandler
from .config import Config

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="DataDog Actions Monitor",
    description="Webhook bridge for Nuon action failures to DataDog",
    version="0.1.0"
)

# Initialize webhook handler
webhook_handler = WebhookHandler()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "datadog-actions-monitor",
        "status": "healthy",
        "version": "0.1.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "datadog_configured": bool(Config.DATADOG_API_KEY and Config.DATADOG_APP_KEY),
        "webhook_secret_configured": bool(Config.NUON_WEBHOOK_SECRET)
    }


@app.post("/webhooks")
async def receive_webhook(request: Request):
    """
    Receive and process Nuon webhooks.
    
    This endpoint:
    1. Verifies the webhook signature (if secret is configured)
    2. Parses the CloudEvents payload
    3. Checks if it's an action failure
    4. Sends event to DataDog if it is
    
    Returns:
        JSON response with processing status
    """
    logger.info("Received webhook request")
    
    # COMPONENT TEST: Log webhook type and transition to test failure webhooks
    try:
        import json
        raw_body = await request.body()
        payload = json.loads(raw_body)
        interests = payload.get("interests", [])
        transition = payload.get("nuontransition", "unknown")
        kind = payload.get("nuonkind", "unknown")
        
        logger.info(f"WEBHOOK TEST - Kind: {kind}, Interests: {interests}, Transition: {transition}")
    except Exception as debug_error:
        logger.warning(f"Debug logging failed (non-critical): {debug_error}")
    
    try:
        result = await webhook_handler.process_webhook(request)
        return JSONResponse(
            status_code=200,
            content=result
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        # Re-raise to let FastAPI handle it with proper status code
        raise


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting DataDog Actions Monitor on port {Config.PORT}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=Config.PORT,
        log_level=Config.LOG_LEVEL.lower()
    )
