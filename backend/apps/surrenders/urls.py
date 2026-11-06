from rest_framework.routers import DefaultRouter
from .views import SurrenderViewSet

router = DefaultRouter()
router.register("", SurrenderViewSet, basename="surrender")
urlpatterns = router.urls
