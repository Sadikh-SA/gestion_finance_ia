from django.db import models

# Create your models here.

class Categorie(models.Model):
    nom = models.CharField(max_length=100)  # Le nom de la catégorie (ex: Alimentation, Transports)
    description = models.TextField(blank=True)  # Optionnel, une description de la catégorie

    def __str__(self):
        return self.nom

class Transaction(models.Model):
    # Les types de transaction : "Dépense" ou "Revenu"
    CHOIX_TYPE_TRANSACTION = [
        ('depense', 'Dépense'),
        ('revenu', 'Revenu')
    ]

    montant = models.DecimalField(max_digits=10, decimal_places=2)  # Montant de la transaction
    type_transaction = models.CharField(max_length=10, choices=CHOIX_TYPE_TRANSACTION)  # Type de la transaction
    description = models.TextField(blank=True)  # Description optionnelle de la transaction
    date = models.DateTimeField(auto_now_add=True)  # Date de la transaction (auto-assignée à la date actuelle)
    categorie = models.ForeignKey(Categorie, on_delete=models.CASCADE, related_name='transactions')  # Relation avec la catégorie

    def __str__(self):
        return f"{self.montant} - {self.categorie.nom} ({self.type_transaction})"
    
class Budget(models.Model):
    categorie = models.ForeignKey(Categorie, on_delete=models.CASCADE, related_name='budgets')  # Catégorie liée
    montant = models.DecimalField(max_digits=10, decimal_places=2)  # Montant du budget
    date_debut = models.DateField()  # Date de début du budget
    date_fin = models.DateField()  # Date de fin du budget

    def __str__(self):
        return f"Budget de {self.categorie.nom} : {self.montant} du {self.date_debut} au {self.date_fin}"
