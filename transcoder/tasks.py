from celery import shared_task
from celery.utils.log import get_task_logger
from google.api_core import exceptions as google_exceptions
from transcoder.models import Stream, StreamStatus
from transcoder.services.transcode_task import task_instance

logger = get_task_logger(__name__)

NON_RETRYABLE_ERRORS = (
    google_exceptions.InvalidArgument,
    google_exceptions.PermissionDenied,
    google_exceptions.NotFound,
)

@shared_task(bind=True, max_retries=120, default_retry_delay=30, acks_late=True, reject_on_worker_lost=True)  # 1h max
def check_transcode_status(self, stream_id):
    stream = Stream.objects.filter(id=stream_id).first()
    if stream is None or not stream.job_name:
        logger.error("Missing stream or job_name with id %s ", stream_id)
        return
    if stream.status != StreamStatus.PROCESSING:
        return
    try:
        state = task_instance.get_job(stream.job_name).state.name
    except NON_RETRYABLE_ERRORS as exc:
        task_instance.mark_failed(stream_id , f"Status check failed {exc}")
        return
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            task_instance.mark_failed(stream_id , f"Status check failed {exc}")
            return
        raise self.retry(exc=exc)

    if state == "SUCCEEDED":
        task_instance.mark_completed(stream_id)
        logger.info("Stream %s: transcode completed", stream_id)
    elif state == "FAILED":
        task_instance.mark_failed(stream_id, "Transcoder job failed")
        logger.error("Stream %s: transcode failed", stream_id)
    elif self.request.retries >= self.max_retries:
        task_instance.mark_failed(stream_id, "Timed out waiting for transcoder job")
    else:
        raise self.retry()
    
@shared_task(bind=True, max_retries=6, default_retry_delay=30, acks_late=True, reject_on_worker_lost=True)
def create_transcode_job(self, stream_id):
    stream = Stream.objects.filter(id=stream_id).first()
    if stream is None:
        logger.error("Stream %s: not found", stream_id)
        return
    if stream.job_name:  
        check_transcode_status.apply_async(args=[stream_id], countdown=30)
        return

    try:
        task_instance.create_job(stream_id, stream.gcs_uri, stream.output_folder, str(stream.id))
    except NON_RETRYABLE_ERRORS as exc:
        task_instance.mark_failed(stream_id, f"Job creation failed: {exc}")
        return
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            task_instance.mark_failed(stream_id, f"Job creation failed: {exc}")
            return
    
        raise self.retry(exc=exc, countdown=min(30 * 2 ** self.request.retries, 600))

    check_transcode_status.apply_async(args=[stream_id], countdown=30)