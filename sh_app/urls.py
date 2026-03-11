from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('event/', views.dashboard, name='dashboard'),
    path('add-record/', views.add_record, name='add_record'),
   
    path('logout/', views.logout_user, name='logout'),
    path('record/<int:pk>', views.sheep_record, name='record'),
    path('delete_record/<int:pk>', views.delete_record, name='delete_record'),
    path('update_record/<int:pk>', views.update_record, name='update_record'),
    
    path('selection/', views.breeding_selection, name='breeding_selection'),
    path('flash-rams/', views.flash_rams_state, name='flash_rams_state'),
    path('flash-ewes/', views.flash_ewes_state, name='flash_ewes_state'),
    path('breeding/flash/rams/', views.bulk_flash_rams, name='bulk_flash_rams'),
    path('breeding/flash/ewes/', views.bulk_flash_ewes, name='bulk_flash_ewes'),

    # path('breed-rams/', views.breed_rams_state, name='breed_rams_state'),
    path('breed-rams/', views.breed_rams_state, name='breed_rams_state'),

    path('debug_breeding/', views.debug_breeding_flow, name='debug_breeding'),

    path('breeding/create-cycle/', views.create_breeding_cycle, name='create_breeding_cycle'),

    path('breeding/breeding_info/', views.BreedingInfoView.as_view(), name='breeding_info'),
    path('breeding/task/', views.BreedingTaskView.as_view(), name='breeding_task'),

    path('breeding/process-selection/', views.process_ram_selection, name='process_ram_selection'),
    path('breeding/process-assignment/', views.process_assignment, name='process_assignment'),

    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),

    path('import-csv/', views.import_sheep_csv, name='import_sheep_csv'),
    path('breeding/history/', views.BreedingHistoryView.as_view(), name='breeding_history'),
   
    path('action/culling/', views.register_culling, name='register_culling'),
    path('action/mortality/', views.register_mortality, name='register_mortality'),
    path('action/distribution/', views.register_distribution, name='register_distribution'),
    path('records/history/', views.records_history, name='records_history'),
]
