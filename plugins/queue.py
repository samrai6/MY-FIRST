import asyncio


# =========================
# GLOBAL JOB QUEUE
# =========================

job_queue = asyncio.Queue()

active_jobs = {}

queued_jobs = {}


# =========================
# ADD JOB
# =========================

async def add_job(user_id, job):

    await job_queue.put(
        (user_id, job)
    )

    queued_jobs[user_id] = job


# =========================
# GET NEXT JOB
# =========================

async def get_next_job():

    user_id, job = await job_queue.get()

    queued_jobs.pop(
        user_id,
        None
    )

    active_jobs[user_id] = job

    return user_id, job


# =========================
# FINISH JOB
# =========================

def finish_job(user_id):

    active_jobs.pop(
        user_id,
        None
    )

    try:
        job_queue.task_done()
    except Exception:
        pass


# =========================
# CHECK USER JOB
# =========================

def has_job(user_id):

    return (
        user_id in active_jobs
        or user_id in queued_jobs
    )


# =========================
# GET ACTIVE JOB
# =========================

def get_active_job(user_id):

    return active_jobs.get(
        user_id
    )


# =========================
# GET QUEUED JOB
# =========================

def get_queued_job(user_id):

    return queued_jobs.get(
        user_id
    )


# =========================
# REMOVE QUEUED JOB
# =========================

def remove_queued_job(user_id):

    return queued_jobs.pop(
        user_id,
        None
    )


# =========================
# QUEUE SIZE
# =========================

def queue_size():

    return job_queue.qsize()
