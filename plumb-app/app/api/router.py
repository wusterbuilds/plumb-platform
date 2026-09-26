from fastapi import APIRouter

from app.api.deals import router as deals_router
from app.api.documents import router as documents_router
from app.api.extraction import router as extraction_router
from app.api.financial import router as financial_router
from app.api.images import router as images_router
from app.api.market import router as market_router
from app.api.om import router as om_router
from app.api.risk import router as risk_router
from app.auth.router import router as auth_router

# Sprint 1+
from app.api.metrics import router as metrics_router

# Sprint 2
from app.api.skills import skills_router, knowledge_router

# Sprint 3
from app.api.lenders import router as lenders_router, match_router, outcomes_router
from app.api.developers import router as developers_router
from app.api.episodes import router as episodes_router

# Sprint 4
from app.api.agents import router as agents_router

# Email integration (demo)
from app.api.email import router as email_router

# Expert feedback / redlines
from app.api.redlines import router as redlines_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(deals_router)
api_router.include_router(documents_router)
api_router.include_router(extraction_router)
api_router.include_router(market_router)
api_router.include_router(financial_router, prefix="/deals/{deal_id}/financial", tags=["financial"])
api_router.include_router(om_router, prefix="/deals/{deal_id}/om", tags=["om"])
api_router.include_router(risk_router, prefix="/deals/{deal_id}/risk", tags=["risk"])
api_router.include_router(images_router, prefix="/deals/{deal_id}/images", tags=["images"])

# Sprint 1: Metrics
api_router.include_router(metrics_router)

# Sprint 2: Skills + Knowledge
api_router.include_router(skills_router)
api_router.include_router(knowledge_router)

# Sprint 3: Lenders + Developers + Episodes + Deal Outcomes
api_router.include_router(lenders_router)
api_router.include_router(match_router)
api_router.include_router(outcomes_router)
api_router.include_router(developers_router)
api_router.include_router(episodes_router)

# Sprint 4: Agents
api_router.include_router(agents_router)

# Email integration (demo)
api_router.include_router(email_router)

# Expert feedback / redlines (mounts at root because routes are nested
# under /deals/{deal_id} and /deals/{deal_id}/om/versions/{version_id})
api_router.include_router(redlines_router, tags=["redlines"])
