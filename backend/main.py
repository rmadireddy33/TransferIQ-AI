from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

from backend.api.routes import router, health_router
from backend.api.judging import router as judging_router, catalog
from backend.api.public_limits import PublicLimits
from backend.api.demo_execution import router as demo_execution_router
from backend.services.demo_runs import DemoRuns
from backend.api.reconciliation import router as reconciliation_router
from backend.api.documents import router as document_router
from backend.api.upload_limit import UploadBodyLimit
from backend.services.document_storage import recover_pending_documents
from backend.core.config import Settings
from backend.core.runtime import runtime_storage, validate_runtime_environment
from backend.database.migrations import initialize_database, SCHEMA_VERSION
from backend.database.session import create_database_engine, session_factory

logger = logging.getLogger('transferiq.application')


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = None
        demo_runs = None
        phase = 'configuration'
        app.state.ready = False
        try:
            configuration = settings if settings is not None else Settings.from_environment()
            validate_runtime_environment(configuration)
            phase = 'storage'
            with runtime_storage(configuration):
                engine = create_database_engine(configuration)
                phase = 'schema'
                initialize_database(engine)
                logger.info('schema_ready', extra={'schema_version': SCHEMA_VERSION})
                app.state.settings = configuration
                app.state.engine = engine
                app.state.session_factory = session_factory(engine)
                if configuration.public_demo_enabled:
                    phase = 'public_demo_catalog'
                    catalog()
                if configuration.demo_execution_enabled:
                    phase = 'demo_registry'
                    demo_runs = DemoRuns(configuration)
                    app.state.demo_runs = demo_runs
                phase = 'document_recovery'
                recover_pending_documents(app.state.session_factory, configuration)
                if configuration.seed_demo_data:
                    from backend.database.seed import seed_demo
                    from backend.database.seed_documents import seed_missing_documents
                    phase = 'demo_records'
                    count = seed_demo(app.state.session_factory, include_scenarios=True)
                    phase = 'demo_documents'
                    documents = seed_missing_documents(app.state.session_factory, configuration)
                    logger.info('fictional_demo_seed_complete', extra={'seed_rows': count, 'seed_documents': documents})
                app.state.ready = True
                logger.info('application_ready')
                phase = 'serving'
                yield
        except Exception as exc:
            logger.error('startup_failed' if phase != 'serving' else 'lifecycle_failed',
                         extra={'phase': phase, 'error_type': type(exc).__name__})
            raise RuntimeError(f'Application lifecycle failed during {phase}; data was not reset') from None
        finally:
            app.state.ready = False
            if engine is not None:
                engine.dispose()
            if demo_runs is not None:
                demo_runs.engine.dispose()
            logger.info('application_stopped')

    application = FastAPI(title="TransferIQ AI", version="0.4.0", lifespan=lifespan,
        description="Fictional demonstration only. Receiving positions are staging records, not settled custody holdings.")
    application.state.ready = False
    from backend.api.resolution import router as review_router, private_router as private_review_router
    application.include_router(router)
    application.include_router(review_router)
    application.include_router(private_review_router)
    application.include_router(health_router)
    application.include_router(judging_router)
    application.include_router(demo_execution_router)
    application.include_router(reconciliation_router)
    application.include_router(document_router)
    application.add_middleware(UploadBodyLimit)
    application.add_middleware(PublicLimits)

    @application.exception_handler(OSError)
    async def storage_error(request: Request, exc: OSError):
        logger.error('storage_unavailable', extra={'error_type': type(exc).__name__})
        return JSONResponse(status_code=503, content={"detail": {
            "code": "storage_unavailable", "message": "Persistent file storage is unavailable"}})

    @application.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError):
        logger.warning('data_conflict', extra={'error_type': type(exc).__name__})
        return JSONResponse(status_code=409, content={"detail": {
            "code": "data_conflict", "message": "Operation conflicts with stored data or database constraints"}})

    @application.exception_handler(OperationalError)
    async def database_error(request: Request, exc: OperationalError):
        logger.error('database_unavailable', extra={'error_type': type(exc).__name__})
        # Do not return SQL, parameters, paths, or secrets to callers.
        return JSONResponse(status_code=503, headers={"Retry-After": "1"}, content={"detail": {
            "code": "database_unavailable", "message": "Database temporarily unavailable; retry with the same Idempotency-Key"}})

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.error('request_failed', extra={'error_type': type(exc).__name__})
        return JSONResponse(status_code=500, content={'detail': {
            'code': 'internal_error', 'message': 'Request could not be completed'}})

    return application


app = create_app()
