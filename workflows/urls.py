from django.urls import path
from . import views

urlpatterns = [
    path('components/', views.list_components, name='list_components'),
    path('preview/', views.preview_workflow, name='preview_workflow'),
    path('example/<str:key>/', views.example_workflow, name='example_workflow'),
    path('save/', views.save_workflow, name='save_workflow'),
    path('workflow/<uuid:workflow_id>/', views.get_workflow, name='get_workflow'),
]
