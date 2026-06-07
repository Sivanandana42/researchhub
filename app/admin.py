from django.contrib import admin
from .models import Category, Profile, ResearchPaper, PlagiarismReport, Alert, ActivityLog, Review

admin.site.register(Category)
admin.site.register(Profile)
admin.site.register(ResearchPaper)
admin.site.register(PlagiarismReport)
admin.site.register(Alert)
admin.site.register(ActivityLog)
admin.site.register(Review)