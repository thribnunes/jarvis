# teacher/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('process_input/', views.process_input, name='process_input'),
]
