from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BudgetViewSet, TransactionViewSet, CategorieViewSet, DepensesParCategorie, ImporterExcel, PrevisionsDepensesView, OptimisationBudgetView, AnalyseTendancesView

router = DefaultRouter()
router.register(r'budgets', BudgetViewSet)
router.register(r'transactions', TransactionViewSet)
router.register(r'categories', CategorieViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('depenses-par-categorie/', DepensesParCategorie.as_view(), name='depenses_par_categorie'),
    path('importer-excel/', ImporterExcel.as_view(), name='importer_excel'),
    path('previsions-depenses/', PrevisionsDepensesView.as_view(), name='previsions-depenses'),
    path('optimisation-budget/', OptimisationBudgetView.as_view(), name='optimisation-budget'),
    path('analyse-tendances/', AnalyseTendancesView.as_view(), name='analyse-tendances'),
]
