import json
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import httpx
from sqlalchemy import and_, or_, select, update
from .models import *
from .store import get, DomainError
from .services import generate_questions
from .providers import Provider, GradeOutput, validate_grade


class Worker:
    def __init__(self, store):
        self.store = store
        self.owner = uid()
        self.stopping = False

    def claim(self):
        t = time.time()
        eligible = and_(
            or_(
                Job.status == "queued",
                and_(Job.status == "running", Job.lease_until < t),
            ),
            Job.available_at <= t,
        )
        with self.store.session() as s:
            candidate = s.scalar(
                select(Job.id).where(eligible).order_by(Job.created_at).limit(1)
            )
            if not candidate:
                return None
            claimed = s.execute(
                update(Job)
                .where(Job.id == candidate, eligible)
                .values(
                    status="running",
                    lease_owner=uid(),
                    lease_until=t + 180,
                    attempts=Job.attempts + 1,
                    heartbeat_at=now(),
                )
            )
            if not claimed.rowcount:
                return None
            return get(s, Job, candidate)

    def _heartbeat(self, jid, owner, stop):
        while not stop.wait(10):
            with self.store.session() as s:
                s.execute(
                    update(Job)
                    .where(
                        Job.id == jid,
                        Job.status == "running",
                        Job.lease_owner == owner,
                    )
                    .values(lease_until=time.time() + 180, heartbeat_at=now())
                )

    def once(self):
        job = self.claim()
        if not job:
            return False
        stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat, args=(job.id, job.lease_owner, stop), daemon=True
        )
        heartbeat.start()
        try:
            if job.run_id:
                with self.store.session() as s:
                    run = get(s, Run, job.run_id)
                    if run.status == "cancelled":
                        self.finish(job, "cancelled")
                        return True
                    if run.status == "queued":
                        run.status = "evaluating"
            if job.kind == "generate":
                generate_questions(self.store, job)
            elif job.kind == "grade":
                self.grade(job)
            elif job.kind == "insights":
                self.insights(job)
            elif job.kind == "export":
                from .exports import build_export

                build_export(self.store, job.payload["export_id"])
            self.finish(job, "done")
        except Exception as exc:
            permanent = isinstance(
                exc, httpx.HTTPStatusError
            ) and exc.response.status_code in [400, 401, 403, 404]
            max_attempts = 2 if isinstance(exc, (ValueError, DomainError)) else 3
            retry = not permanent and job.attempts < max_attempts
            delay = min(2**job.attempts, 30)
            if isinstance(exc, httpx.HTTPStatusError):
                try:
                    delay = max(
                        delay, int(exc.response.headers.get("Retry-After", "0"))
                    )
                except ValueError:
                    pass
            code = (
                exc.code
                if isinstance(exc, DomainError)
                else (
                    f"http_{exc.response.status_code}"
                    if isinstance(exc, httpx.HTTPStatusError)
                    else type(exc).__name__
                )
            )
            with self.store.session() as s:
                current = get(s, Job, job.id)
                if current.lease_owner == job.lease_owner:
                    current.status = "queued" if retry else "failed"
                    current.error = code
                    current.available_at = time.time() + delay
                    current.lease_until = 0
                    if job.kind == "export" and not retry:
                        get(s, Export, job.payload["export_id"]).status = "failed"
                    if job.kind == "generate" and not retry:
                        get(s, Campaign, job.payload["campaign_id"]).status = "draft"
        finally:
            stop.set()
            heartbeat.join(timeout=1)
        if job.run_id:
            self.finalize(job.run_id)
        return True

    def finish(self, job, status):
        with self.store.session() as s:
            s.execute(
                update(Job)
                .where(
                    Job.id == job.id,
                    Job.lease_owner == job.lease_owner,
                    Job.status == "running",
                )
                .values(status=status, lease_until=0, heartbeat_at=now(), error=None)
            )

    def grade(self, job):
        with self.store.session() as s:
            if s.scalar(
                select(Evaluation.id).where(
                    Evaluation.run_id == job.run_id,
                    Evaluation.answer_id == job.payload["answer_id"],
                    Evaluation.pass_no == job.payload["pass_no"],
                )
            ):
                return
            answer = get(s, Answer, job.payload["answer_id"])
            q = get(s, Question, answer.question_id)
            payload = {
                "answer": answer.text,
                "question": q.prompt,
                "rubric": q.rubric,
                "reference_answer": q.reference,
                "evidence_type": (
                    "self_reported_experience"
                    if "EXPERIENCE" in q.reference
                    else "scenario_reasoning"
                ),
            }
        config = self.store.resolve(version_id=job.payload["profile_version"])
        provider = Provider(config, self.store.settings.allowed_hosts)
        start = time.monotonic()
        raw, usage = provider.complete(
            "grade", payload, GradeOutput.model_json_schema()
        )
        grade, score, flags = validate_grade(raw, answer.text, q.rubric)
        with self.store.session() as s:
            current = get(s, Job, job.id)
            if (
                current.lease_owner != job.lease_owner
                or current.status != "running"
                or current.lease_until < time.time()
            ):
                raise DomainError("lease_lost", "İş sahipliği değişti.")
            existing = s.scalar(
                select(Evaluation).where(
                    Evaluation.run_id == job.run_id,
                    Evaluation.answer_id == answer.id,
                    Evaluation.pass_no == job.payload["pass_no"],
                )
            )
            if not existing:
                e = Evaluation(
                    run_id=job.run_id,
                    answer_id=answer.id,
                    pass_no=job.payload["pass_no"],
                    status=grade.status,
                    score=score,
                    criteria=[c.model_dump() for c in grade.criteria],
                    flags=flags,
                    usage=usage,
                    review_status=(
                        "pending" if flags or grade.status != "scored" else "clear"
                    ),
                )
                s.add(e)
            s.add(
                Call(
                    job_id=job.id,
                    profile_version=config["version_id"],
                    model=config["model"],
                    latency_ms=(time.monotonic() - start) * 1000,
                    usage=usage,
                )
            )

    def finalize(self, rid):
        with self.store.session() as s:
            s.execute(update(Run).where(Run.id == rid).values(status=Run.status))
            run = get(s, Run, rid)
            if run.status in ["cancelled", "published"]:
                return
            jobs = list(
                s.scalars(select(Job).where(Job.run_id == rid, Job.kind == "grade"))
            )
            if any(j.status in ["queued", "running"] for j in jobs):
                return
            if any(j.status == "failed" for j in jobs):
                run.status = "failed"
                run.error = "Bazı yanıtlar değerlendirilemedi; başarısız işleri yeniden deneyin."
                return
            evaluations = list(
                s.scalars(select(Evaluation).where(Evaluation.run_id == rid))
            )
            primary = {e.answer_id: e for e in evaluations if e.pass_no == 1}
            for e in evaluations:
                if e.pass_no == 2:
                    p = primary.get(e.answer_id)
                    if (
                        p
                        and p.score is not None
                        and e.score is not None
                        and abs(p.score - e.score) > 15
                    ):
                        if "second_pass_disagreement" not in p.flags:
                            p.flags = p.flags + ["second_pass_disagreement"]
                            p.review_status = "pending"
            if any(e.review_status == "pending" for e in evaluations):
                run.status = "review_required"
                return
            insight = s.scalar(select(Job).where(Job.dedupe_key == f"insights:{rid}"))
            if not insight:
                s.add(
                    Job(
                        run_id=rid,
                        kind="insights",
                        dedupe_key=f"insights:{rid}",
                        payload={"profile_version": run.insight_profile_version},
                    )
                )
                run.status = "validating"
            elif insight.status in ["done", "failed"]:
                run.status = "ready_to_publish"
                run.finished_at = now()

    def insights(self, job):
        from .reporting import build_snapshot, metrics

        with self.store.session() as s:
            data = metrics(build_snapshot(s, job.run_id))
            data.pop("rows", None)
        config = self.store.resolve(version_id=job.payload["profile_version"])
        value, _ = Provider(config, self.store.settings.allowed_hosts).complete(
            "insights", data
        )
        if not isinstance(value.get("summary"), str) or not isinstance(
            value.get("actions"), list
        ):
            raise DomainError("invalid_insight", "Özet şeması geçersiz.")
        with self.store.session() as s:
            get(s, Run, job.run_id).insights = value

    def drain(self, limit=10000):
        n = 0
        while n < limit and self.once():
            n += 1
        return n

    def run(self):
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stopping", True))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "stopping", True))
        with ThreadPoolExecutor(max_workers=3) as pool:
            while not self.stopping:
                list(pool.map(lambda _: self.once(), range(3)))
                time.sleep(0.4)
