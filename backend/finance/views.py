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