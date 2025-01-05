from django.contrib import admin
from .models import Categorie, Transaction, Budget

# Enregistrer les modèles dans l'admin
admin.site.register(Categorie)
admin.site.register(Transaction)
admin.site.register(Budget)
