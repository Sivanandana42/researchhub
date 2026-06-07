from django.db import models
from django.contrib.auth.models import User


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Profile(models.Model):
    ROLE_CHOICES = (
        ('user',     'User'),
        ('reviewer', 'Reviewer'),
        ('admin',    'Admin'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class ResearchPaper(models.Model):
    STATUS_CHOICES = (
        ('pending',  'Pending Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('revise',   'Needs Revision'),
    )
    title       = models.CharField(max_length=200)
    abstract    = models.TextField(blank=True)
    keywords    = models.CharField(max_length=300, blank=True)
    file        = models.FileField(upload_to='papers/')
    category    = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='papers')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return self.title


class PlagiarismReport(models.Model):
    paper        = models.OneToOneField(ResearchPaper, on_delete=models.CASCADE)
    score        = models.FloatField()
    matched_text = models.TextField(blank=True)
    keywords     = models.CharField(max_length=500, blank=True)
    summary      = models.TextField(blank=True)
    checked_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.paper.title} - {self.score}%"


class Alert(models.Model):
    ALERT_TYPES = (
        ('plagiarism', 'Plagiarism Detected'),
        ('suspicious', 'Suspicious Activity'),
        ('review',     'Review Update'),
        ('system',     'System'),
    )
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    paper      = models.ForeignKey(ResearchPaper, on_delete=models.CASCADE, null=True, blank=True)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES, default='system')
    message    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read    = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.alert_type} alert for {self.user.username}"


class ActivityLog(models.Model):
    ACTION_CHOICES = (
        ('login',    'Login'),
        ('logout',   'Logout'),
        ('upload',   'Upload Paper'),
        ('download', 'Download Paper'),
        ('delete',   'Delete Paper'),
        ('search',   'Search'),
        ('view',     'View Paper'),
    )
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    action     = models.CharField(max_length=20, choices=ACTION_CHOICES)
    detail     = models.CharField(max_length=300, blank=True)
    ip_address = models.CharField(max_length=50, blank=True)
    timestamp  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.action}"


class Review(models.Model):
    DECISION_CHOICES = (
        ('pending',  'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('revise',   'Needs Revision'),
    )
    paper      = models.ForeignKey(ResearchPaper, on_delete=models.CASCADE, related_name='reviews')
    reviewer   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    comment    = models.TextField()
    decision   = models.CharField(max_length=10, choices=DECISION_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.reviewer.username} on {self.paper.title}"
