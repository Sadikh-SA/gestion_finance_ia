import openpyxl, os
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Budget, Transaction, Categorie
from .serializers import BudgetSerializer, TransactionSerializer, CategorieSerializer
from django.utils.dateparse import parse_date
from django.db.models import Sum
from datetime import datetime
from django.core.files.storage import FileSystemStorage
import pandas as pd
from django.conf import settings
from django.http import JsonResponse
from django.core.exceptions import ObjectDoesNotExist

class BudgetViewSet(viewsets.ModelViewSet):
    queryset = Budget.objects.all()
    serializer_class = BudgetSerializer

class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer

class CategorieViewSet(viewsets.ModelViewSet):
    queryset = Categorie.objects.all()
    serializer_class = CategorieSerializer

class DepensesParCategorie(APIView):
    def get(self, request, *args, **kwargs):
        # Récupérer les dates depuis les paramètres GET
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        # Convertir les dates en objets datetime
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        # Récupérer les dépenses par catégorie dans la période
        depenses = (
            Transaction.objects
            .filter(date__range=[start_date, end_date])
            .values('categorie__nom')  # On veut grouper par le nom de la catégorie
            .annotate(total_depense=Sum('montant'))  # Calculer la somme des montants
            .order_by('-total_depense')  # Trier par montant total décroissant
        )

        # Retourner la réponse en format JSON
        return Response({'depenses_par_categorie': list(depenses)}, status=status.HTTP_200_OK)
    
class ImporterExcel(APIView):
    def post(self, request, *args, **kwargs):
        fichier_excel = request.FILES.get('fichier')
        
        if not fichier_excel:
            return Response({"error": "Aucun fichier Excel fourni."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Enregistrer temporairement le fichier dans le répertoire 'media/'
        chemin_fichier = f"{settings.MEDIA_ROOT}/{fichier_excel.name}"
        
        with open(chemin_fichier, 'wb') as destination:
            for chunk in fichier_excel.chunks():
                destination.write(chunk)

        # Charger le fichier Excel dans un DataFrame
        try:
            df = pd.read_excel(chemin_fichier)
        except Exception as e:
            return Response({"error": f"Erreur lors du chargement du fichier Excel : {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        
        # S'assurer que les colonnes requises sont présentes (en-têtes)
        if 'Date' not in df.columns or 'Montant' not in df.columns or 'Catégorie' not in df.columns:
            return Response({"error": "Le fichier Excel doit contenir les colonnes 'Date', 'Montant', et 'Catégorie'."}, status=status.HTTP_400_BAD_REQUEST)

        # Traiter chaque ligne du DataFrame
        for _, row in df.iterrows():
            try:
                # Récupérer ou créer la catégorie associée à la transaction
                categorie_nom = row['Catégorie']
                categorie = Categorie.objects.get(nom=categorie_nom)
                
                # Créer une transaction
                transaction = Transaction(
                    date=row['Date'],
                    montant=row['Montant'],
                    categorie=categorie
                )
                transaction.save()
            except ObjectDoesNotExist:
                return Response({"error": f"La catégorie '{categorie_nom}' n'existe pas dans la base de données."}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"error": f"Erreur lors de l'importation de la ligne : {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({"message": "Importation réussie."}, status=status.HTTP_200_OK)
    
class PrevisionsDepenses:
    def __init__(self, start_date, end_date):
        self.start_date = start_date
        self.end_date = end_date

    def get_previsions(self):
        # Récupérer les transactions dans la plage de dates
        transactions = Transaction.objects.filter(date__range=[self.start_date, self.end_date])

        # Si aucune donnée, retourner un message d'erreur
        if not transactions:
            return {'error': 'Aucune donnée trouvée pour cette période.'}

        # Convertir en DataFrame
        df = pd.DataFrame(list(transactions.values('date', 'montant', 'categorie__nom')))

        # Agréger les dépenses par mois
        df['date'] = pd.to_datetime(df['date'])
        df['mois'] = df['date'].dt.to_period('M')
        depenses_mensuelles = df.groupby('mois')['montant'].sum()

        # Calcul de la moyenne mobile pour les prévisions futures
        depenses_mensuelles['prevision'] = depenses_mensuelles.rolling(window=3).mean()

        # Prendre la prévision pour le dernier mois comme estimation
        prevision = depenses_mensuelles['prevision'].iloc[-1] if len(depenses_mensuelles) > 2 else 0

        return {'prevision': prevision}
    
class PrevisionsDepensesView(APIView):
    def get(self, request):
        try:
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')

            # Vérifier que les dates sont présentes
            if not start_date or not end_date:
                return Response({'error': 'Les dates start_date et end_date sont nécessaires.'}, status=status.HTTP_400_BAD_REQUEST)

            # Initialiser la classe et appeler la fonction de prévision
            previsions = PrevisionsDepenses(start_date, end_date)
            result = previsions.get_previsions()

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class OptimisationBudget:
    def __init__(self, categorie, budget):
        self.categorie = categorie
        self.budget = budget

    def optimiser_budget(self):
        transactions = Transaction.objects.filter(categorie__nom=self.categorie)
        depenses_totales = transactions.aggregate(Sum('montant'))['montant__sum'] or 0

        # Calcul de l'optimisation du budget (en pourcentage)
        pourcentage_depenses = (depenses_totales / self.budget) * 100

        if pourcentage_depenses > 100:
            return f"Votre budget pour {self.categorie} est dépassé. Vous avez dépassé de {pourcentage_depenses - 100:.2f}%."
        elif pourcentage_depenses < 80:
            return f"Vous avez économisé sur votre budget {self.categorie}. Vous avez dépensé seulement {pourcentage_depenses:.2f}%, vous pourriez réduire votre budget."
        else:
            return f"Votre budget pour {self.categorie} est équilibré, vous avez utilisé {pourcentage_depenses:.2f}% de votre budget."
        
class OptimisationBudgetView(APIView):
    def get(self, request):
        try:
            categorie = request.query_params.get('categorie')
            budget = request.query_params.get('budget')

            # Vérifier que les paramètres sont présents
            if not categorie or not budget:
                return Response({'error': 'La catégorie et le budget sont nécessaires.'}, status=status.HTTP_400_BAD_REQUEST)

            # Initialiser la classe et appeler la fonction d'optimisation
            optimisation = OptimisationBudget(categorie, float(budget))
            result = optimisation.optimiser_budget()

            return Response({'result': result}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class AnalyseTendances:
    def __init__(self, start_date, end_date):
        self.start_date = start_date
        self.end_date = end_date

    def get_tendances(self):
        transactions = Transaction.objects.filter(date__range=[self.start_date, self.end_date])

        if not transactions:
            return {'error': 'Aucune donnée trouvée pour cette période.'}

        df = pd.DataFrame(list(transactions.values('date', 'montant')))
        df['date'] = pd.to_datetime(df['date'])
        df['mois'] = df['date'].dt.to_period('M')
        depenses_mensuelles = df.groupby('mois')['montant'].sum()

        # Créer un graphique ou des données analytiques
        tendances = depenses_mensuelles.to_dict()

        return {'tendances': tendances}
    
class AnalyseTendancesView(APIView):
    def get(self, request):
        try:
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')

            # Vérifier que les dates sont présentes
            if not start_date or not end_date:
                return Response({'error': 'Les dates start_date et end_date sont nécessaires.'}, status=status.HTTP_400_BAD_REQUEST)

            # Initialiser la classe et appeler la fonction d'analyse des tendances
            analyse = AnalyseTendances(start_date, end_date)
            result = analyse.get_tendances()

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
