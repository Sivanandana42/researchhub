from django.urls import path
from . import views

urlpatterns = [
    path('',                                          views.landing,            name='landing'),
    path('register/',                                 views.register_view,      name='register'),
    path('login/',                                    views.login_view,         name='login'),
    path('logout/',                                   views.logout_view,        name='logout'),

    path('dashboard/',                                views.dashboard,          name='dashboard'),
    path('upload/',                                   views.upload_paper,       name='upload'),
    path('paper/<int:paper_id>/',                     views.paper_detail,       name='paper_detail'),
    path('paper/<int:paper_id>/review/',              views.submit_review,      name='submit_review'),
    path('reviewer/',                                 views.reviewer_view,      name='reviewer'),
    path('mark-read/<int:alert_id>/',                 views.mark_read,          name='mark_read'),
    path('activity/',                                 views.my_activity,        name='my_activity'),

    path('admin-panel/',                              views.admin_panel,        name='admin_panel'),
    path('admin-panel/users/',                        views.admin_users,        name='admin_users'),
    path('admin-panel/users/<int:user_id>/',          views.admin_user_detail,  name='admin_user_detail'),
    path('admin-panel/users/delete/<int:user_id>/',   views.admin_delete_user,  name='admin_delete_user'),
    path('admin-panel/papers/',                       views.admin_papers,       name='admin_papers'),
    path('admin-panel/papers/delete/<int:paper_id>/', views.admin_delete_paper, name='admin_delete_paper'),
    path('admin-panel/alerts/',                       views.admin_alerts,       name='admin_alerts'),
    path('admin-panel/logs/',                         views.admin_logs,         name='admin_logs'),
    path('admin-panel/categories/',                   views.admin_categories,   name='admin_categories'),
    path('admin-panel/make-reviewer/<int:user_id>/',  views.admin_make_reviewer,name='admin_make_reviewer'),
    path('paper/<int:paper_id>/delete/', views.delete_paper, name='delete_paper'),
    path('paper/<int:paper_id>/export-pdf/', views.export_report_pdf, name='export_pdf'),
    path('review/<int:review_id>/delete/', views.delete_review, name='delete_review'),

]