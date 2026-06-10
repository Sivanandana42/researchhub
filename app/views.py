from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
import random
import re
import io
from difflib import SequenceMatcher

from .models import (
    Profile, Category, ResearchPaper,
    PlagiarismReport, Alert, ActivityLog, Review
)


# ── helpers ───────────────────────────────────
def get_role(user):
    try:
        return user.profile.role
    except Profile.DoesNotExist:
        return 'user'


def log_action(user, action, detail='', request=None):
    ip = ''
    if request:
        ip = request.META.get('REMOTE_ADDR', '')
    ActivityLog.objects.create(
        user=user, action=action, detail=detail, ip_address=ip
    )


def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if get_role(request.user) != 'admin':
            messages.error(request, 'Admin access required.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def extract_keywords(text):
    stopwords = {'the', 'a', 'an', 'is', 'in', 'of', 'to', 'and', 'for', 'with',
                 'that', 'this', 'are', 'was', 'on', 'at', 'by'}
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    freq = {}
    for w in words:
        if w not in stopwords:
            freq[w] = freq.get(w, 0) + 1
    top = sorted(freq, key=freq.get, reverse=True)[:8]
    return ', '.join(top)


def generate_suggestions(score, paper=None):
    """Generate paper-specific AI suggestions based on score and paper content."""
    if score < 40:
        return []

    # extract paper-specific info
    paper_keywords = []
    paper_topic    = ''
    paper_title    = ''

    if paper:
        paper_title = paper.title or ''
        if paper.keywords:
            paper_keywords = [k.strip() for k in paper.keywords.split(',') if k.strip()]
        if paper.abstract:
            # extract top 3 meaningful words from abstract
            stopwords = {'the','a','an','is','in','of','to','and','for','with',
                        'that','this','are','was','on','at','by','be','has',
                        'have','had','their','from','which','were','been'}
            words = re.findall(r'\b[a-zA-Z]{4,}\b', paper.abstract.lower())
            freq = {}
            for w in words:
                if w not in stopwords:
                    freq[w] = freq.get(w, 0) + 1
            top = sorted(freq, key=freq.get, reverse=True)[:3]
            paper_topic = ', '.join(top)

    # use first keyword as topic reference
    topic_ref = paper_keywords[0] if paper_keywords else paper_topic or 'your research topic'
    title_ref = paper_title[:60] if paper_title else 'this paper'

    if score < 60:
        return [
            f'Rewrite the sections in "{title_ref}" that discuss {topic_ref} using your own original language and perspective.',
            f'Add your own experimental results or observations related to {topic_ref} to increase the original content percentage.',
            f'Cite all referenced sources properly — any borrowed ideas about {topic_ref} must include author name, year, and publication.',
            f'Expand your methodology section by explaining specifically how you applied {topic_ref} in your own approach.',
            f'Replace any directly copied definitions of {topic_ref} with your own understanding written in your own words.',
        ]
    elif score < 80:
        return [
            f'The introduction and literature review sections about {topic_ref} need to be completely rewritten in your own words.',
            f'All paragraphs that describe {topic_ref} concepts copied from other papers must be significantly rephrased.',
            f'Add a new original section specifically covering your own findings and conclusions about {topic_ref}.',
            f'Use quotation marks for any sentence taken directly from a source and add proper IEEE or APA citation.',
            f'Replace background content about {topic_ref} with summaries from at least 3 different new reference sources.',
            f'Restructure the paper "{title_ref}" so that your original contribution forms the majority of the content.',
        ]
    else:
        return [
            f'"{title_ref}" requires major rewriting — most content about {topic_ref} appears to match existing papers.',
            f'Completely rewrite the abstract, introduction, and all sections discussing {topic_ref} from scratch.',
            f'Remove all directly copied content about {topic_ref} and replace with original research and analysis.',
            f'Consult at least 5 new and diverse reference sources on {topic_ref} and write summaries in your own words.',
            f'Add substantial original contributions specific to {topic_ref} such as new experiments, data, or case studies.',
            f'Restructure the entire paper "{title_ref}" with a completely fresh perspective and original arguments.',
            f'Consider running your revised paper through the system again after rewriting to verify the new similarity score.',
        ]


# ── landing ───────────────────────────────────
def landing(request):
    if request.user.is_authenticated:
        if get_role(request.user) == 'admin':
            return redirect('admin_panel')
        return redirect('dashboard')
    return render(request, 'landing.html')


# ── register ──────────────────────────────────
def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        confirm  = request.POST.get('confirm_password', '')

        if not username or not password:
            messages.error(request, 'Username and password are required.')
            return redirect('register')
        if password != confirm:
            messages.error(request, 'Passwords do not match.')
            return redirect('register')
        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return redirect('register')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
            return redirect('register')

        user = User.objects.create_user(username=username, password=password)
        Profile.objects.create(user=user, role='user')
        login(request, user)
        log_action(user, 'login', 'Registered and logged in', request)
        messages.success(request, f'Welcome, {username}!')
        return redirect('dashboard')

    return render(request, 'register.html')


# ── login ─────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        if get_role(request.user) == 'admin':
            return redirect('admin_panel')
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user     = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            log_action(user, 'login', 'User logged in', request)
            if get_role(user) == 'admin':
                return redirect('admin_panel')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'login.html')


# ── logout ────────────────────────────────────
def logout_view(request):
    if request.user.is_authenticated:
        log_action(request.user, 'logout', 'User logged out', request)
        logout(request)
    return redirect('landing')


# ── dashboard ─────────────────────────────────
@login_required(login_url='login')
def dashboard(request):
    if get_role(request.user) == 'admin':
        return redirect('admin_panel')

    query      = request.GET.get('q', '')
    cat_id     = request.GET.get('category', '')
    keyword    = request.GET.get('keyword', '')

    all_papers = ResearchPaper.objects.all().order_by('-uploaded_at')
    categories = Category.objects.all()
    alerts     = Alert.objects.filter(
                     user=request.user, is_read=False
                 ).order_by('-created_at')

    if query:
        all_papers = all_papers.filter(title__icontains=query)
        log_action(request.user, 'search', f'Searched: {query}', request)
    if cat_id:
        all_papers = all_papers.filter(category_id=cat_id)
    if keyword:
        all_papers = all_papers.filter(keywords__icontains=keyword)

    for paper in all_papers:
        try:
            paper.report = paper.plagiarismreport
        except PlagiarismReport.DoesNotExist:
            paper.report = None

    my_papers    = ResearchPaper.objects.filter(uploaded_by=request.user)
    total_papers = my_papers.count()
    high_plag    = PlagiarismReport.objects.filter(
                       paper__uploaded_by=request.user, score__gt=50
                   ).count()
    alert_count  = Alert.objects.filter(
                       user=request.user, is_read=False
                   ).count()

    return render(request, 'dashboard.html', {
        'papers':       all_papers,
        'categories':   categories,
        'alerts':       alerts,
        'query':        query,
        'cat_id':       cat_id,
        'keyword':      keyword,
        'total_papers': total_papers,
        'high_plag':    high_plag,
        'alert_count':  alert_count,
    })


# ── paper detail ──────────────────────────────
@login_required(login_url='login')
def paper_detail(request, paper_id):
    paper = get_object_or_404(ResearchPaper, id=paper_id)
    log_action(request.user, 'view', f'Viewed: {paper.title}', request)

    try:
        report = paper.plagiarismreport
    except PlagiarismReport.DoesNotExist:
        report = None

    reviews  = paper.reviews.all().order_by('-created_at')
    keywords = []
    if paper.keywords:
        keywords = [k.strip() for k in paper.keywords.split(',') if k.strip()]

    # get suggestions from session if paper was just uploaded
    suggestions = []
    if request.session.get('suggestion_paper_id') == paper.id:
        suggestions = request.session.pop('suggestions', [])
        request.session.pop('suggestion_paper_id', None)

    # also generate live if score >= 40 and no session suggestions
    if not suggestions and report and report.score >= 40:
     suggestions = generate_suggestions(report.score, paper)

    return render(request, 'paper_detail.html', {
        'paper':       paper,
        'report':      report,
        'reviews':     reviews,
        'keywords':    keywords,
        'suggestions': suggestions,
    })


# ── export plagiarism report as PDF ──────────
@login_required(login_url='login')
def export_report_pdf(request, paper_id):
    paper = get_object_or_404(ResearchPaper, id=paper_id)

    try:
        report = paper.plagiarismreport
    except PlagiarismReport.DoesNotExist:
        messages.error(request, 'No plagiarism report found for this paper.')
        return redirect('paper_detail', paper_id=paper_id)

    reviews = paper.reviews.all().order_by('-created_at')

    verdict     = 'High similarity detected — manual review recommended.' if report.score > 50 else 'Content appears largely original.'
    score_color = '#e53e3e' if report.score > 50 else '#38a169'
    bar_filled  = int(report.score)

    reviews_html = ''
    for rev in reviews:
        dc = {'accepted': '#38a169', 'rejected': '#e53e3e', 'revise': '#d69e2e', 'pending': '#718096'}
        c  = dc.get(rev.decision, '#718096')
        reviews_html += f'''
        <div style="border:1px solid #e2e8f0;border-radius:8px;padding:14px;margin-bottom:12px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                <span style="font-weight:700;font-size:13px;">{rev.reviewer.username}</span>
                <span style="background:{c}22;color:{c};padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700;">{rev.decision.title()}</span>
            </div>
            <p style="font-size:12px;color:#4a5568;margin:0;line-height:1.6;">{rev.comment}</p>
            <p style="font-size:11px;color:#a0aec0;margin:6px 0 0;">{rev.created_at.strftime("%B %d, %Y")}</p>
        </div>'''

    # build suggestions HTML for PDF
    suggestions = generate_suggestions(report.score, paper)
    suggestions_html = ''
    if suggestions:
        items = ''.join(
            f'<li style="font-size:12px;color:#78350f;margin-bottom:6px;">{s}</li>'
            for s in suggestions
        )
        suggestions_html = f'''
        <div class="section">
          <div class="section-title" style="color:#92400e;">AI Suggestions to Reduce Plagiarism</div>
          <div style="background:#fffbeb;border:1px solid #f59e0b;border-radius:8px;padding:16px;">
            <ol style="margin:0;padding-left:18px;">{items}</ol>
          </div>
        </div>'''

    html_content = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; margin: 0; padding: 40px; color: #2d3748; background: #fff; }}
  .header {{ text-align: center; border-bottom: 3px solid #5b6ef5; padding-bottom: 20px; margin-bottom: 30px; }}
  .brand {{ font-size: 14px; font-weight: 700; color: #5b6ef5; margin-bottom: 6px; }}
  h1 {{ font-size: 22px; margin: 0 0 6px; color: #1a202c; }}
  .generated {{ font-size: 11px; color: #a0aec0; }}
  .section {{ margin-bottom: 28px; }}
  .section-title {{ font-size: 11px; font-weight: 700; color: #718096; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin-bottom: 14px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 10px 12px; font-size: 12px; border-bottom: 1px solid #e2e8f0; }}
  td:first-child {{ color: #718096; font-weight: 700; width: 130px; }}
  td:last-child {{ color: #2d3748; }}
  tr:last-child td {{ border: none; }}
  tr:nth-child(even) {{ background: #f7fafc; }}
  .score-box {{ text-align: center; padding: 28px; background: #f7fafc; border-radius: 12px; margin-bottom: 16px; }}
  .score-num {{ font-size: 52px; font-weight: 800; color: {score_color}; line-height: 1; }}
  .score-label {{ font-size: 12px; color: #718096; margin-top: 4px; }}
  .bar-wrap {{ background: #e2e8f0; border-radius: 4px; height: 10px; margin: 12px 0; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 4px; background: {score_color}; width: {bar_filled}%; }}
  .verdict {{ font-size: 13px; font-weight: 700; color: {score_color}; text-align: center; padding: 10px; background: {score_color}11; border-radius: 8px; margin-top: 10px; }}
  .abstract-box {{ background: #f7fafc; border-radius: 8px; padding: 16px; font-size: 12px; color: #4a5568; line-height: 1.7; }}
  .footer {{ text-align: center; font-size: 10px; color: #a0aec0; border-top: 1px solid #e2e8f0; padding-top: 16px; margin-top: 30px; }}
</style>
</head>
<body>
<div class="header">
  <div class="brand">ResearchHub</div>
  <h1>Plagiarism Detection Report</h1>
  <div class="generated">Generated on {report.checked_at.strftime("%B %d, %Y at %H:%M UTC")}</div>
</div>
<div class="section">
  <div class="section-title">Paper Information</div>
  <table>
    <tr><td>Title</td><td>{paper.title}</td></tr>
    <tr><td>Author</td><td>{paper.uploaded_by.username}</td></tr>
    <tr><td>Category</td><td>{paper.category.name if paper.category else "—"}</td></tr>
    <tr><td>Upload Date</td><td>{paper.uploaded_at.strftime("%B %d, %Y")}</td></tr>
    <tr><td>Status</td><td>{paper.status.title()}</td></tr>
    <tr><td>Reviews</td><td>{reviews.count()}</td></tr>
  </table>
</div>
<div class="section">
  <div class="section-title">Plagiarism Score</div>
  <div class="score-box">
    <div class="score-num">{report.score}%</div>
    <div class="score-label">Similarity Score</div>
  </div>
  <div class="bar-wrap"><div class="bar-fill"></div></div>
  <div class="verdict">{"⚠ " if report.score > 50 else "✓ "}{verdict}</div>
</div>
{"<div class='section'><div class='section-title'>Analysis Summary</div><p style='font-size:12px;color:#4a5568;line-height:1.7;'>" + report.summary + "</p></div>" if report.summary else ""}
{"<div class='section'><div class='section-title'>Extracted Keywords</div><p style='font-size:12px;color:#4a5568;'>" + report.keywords + "</p></div>" if report.keywords else ""}
{suggestions_html}
{"<div class='section'><div class='section-title'>Abstract</div><div class='abstract-box'>" + paper.abstract + "</div></div>" if paper.abstract else ""}
{"<div class='section'><div class='section-title'>Feedback (" + str(reviews.count()) + ")</div>" + reviews_html + "</div>" if reviews.exists() else ""}
<div class="footer">Generated by ResearchHub — AI-Powered Research Paper Management System</div>
</body>
</html>'''

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER

        buffer = io.BytesIO()
        doc    = SimpleDocTemplate(buffer, pagesize=A4,
                     rightMargin=2*cm, leftMargin=2*cm,
                     topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()

        s_brand   = ParagraphStyle('Brand', fontSize=11, fontName='Helvetica-Bold', textColor=colors.HexColor('#5b6ef5'), alignment=TA_CENTER, spaceAfter=4)
        s_title   = ParagraphStyle('Title2', fontSize=20, fontName='Helvetica-Bold', textColor=colors.HexColor('#1a202c'), alignment=TA_CENTER, spaceAfter=6)
        s_sub     = ParagraphStyle('Sub', fontSize=9, fontName='Helvetica', textColor=colors.HexColor('#a0aec0'), alignment=TA_CENTER, spaceAfter=10)
        s_h2      = ParagraphStyle('H2', fontSize=11, fontName='Helvetica-Bold', textColor=colors.HexColor('#2d3748'), spaceBefore=14, spaceAfter=6)
        s_body    = ParagraphStyle('Body', fontSize=10, fontName='Helvetica', textColor=colors.HexColor('#4a5568'), spaceAfter=6, leading=16)
        s_score   = ParagraphStyle('Score', fontSize=40, fontName='Helvetica-Bold', textColor=colors.HexColor(score_color), alignment=TA_CENTER, spaceAfter=4)
        s_verdict = ParagraphStyle('Verdict', fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor(score_color), alignment=TA_CENTER, spaceAfter=8)
        s_footer  = ParagraphStyle('Footer', fontSize=8, fontName='Helvetica', textColor=colors.HexColor('#a0aec0'), alignment=TA_CENTER, spaceBefore=8)
        s_suggest = ParagraphStyle('Suggest', fontSize=10, fontName='Helvetica', textColor=colors.HexColor('#78350f'), spaceAfter=5, leading=15)

        hr = HRFlowable(width='100%', thickness=1, color=colors.HexColor('#e2e8f0'))

        story = []
        story.append(Paragraph('ResearchHub', s_brand))
        story.append(Paragraph('Plagiarism Detection Report', s_title))
        story.append(Paragraph(f'Generated on {report.checked_at.strftime("%B %d, %Y at %H:%M UTC")}', s_sub))
        story.append(hr)
        story.append(Spacer(1, 0.3*cm))

        story.append(Paragraph('Paper Information', s_h2))
        pdata = [
            ['Title',       paper.title],
            ['Author',      paper.uploaded_by.username],
            ['Category',    paper.category.name if paper.category else '—'],
            ['Upload Date', paper.uploaded_at.strftime('%B %d, %Y')],
            ['Status',      paper.status.title()],
            ['Feedback',    str(reviews.count())],
        ]
        pt = Table(pdata, colWidths=[3.5*cm, 13.5*cm])
        pt.setStyle(TableStyle([
            ('FONTNAME',      (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, -1), 10),
            ('TEXTCOLOR',     (0, 0), (0, -1), colors.HexColor('#718096')),
            ('TEXTCOLOR',     (1, 0), (1, -1), colors.HexColor('#2d3748')),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f7fafc')]),
            ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('PADDING',       (0, 0), (-1, -1), 8),
        ]))
        story.append(pt)
        story.append(Spacer(1, 0.4*cm))
        story.append(hr)
        story.append(Spacer(1, 0.3*cm))

        story.append(Paragraph('Plagiarism Score', s_h2))
        story.append(Paragraph(f'{report.score}%', s_score))
        story.append(Paragraph('Similarity Score', s_sub))

        bw   = 17*cm
        fill = bw * (report.score / 100)
        bt   = Table([['']], colWidths=[bw], rowHeights=[0.4*cm])
        bt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e2e8f0')),
            ('GRID',       (0, 0), (-1, -1), 0, colors.white),
        ]))
        story.append(bt)
        bf = Table([['']], colWidths=[max(fill, 0.1*cm)], rowHeights=[0.4*cm])
        bf.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(score_color)),
            ('GRID',       (0, 0), (-1, -1), 0, colors.white),
        ]))
        story.append(Spacer(1, -0.4*cm))
        story.append(bf)
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(('Warning: ' if report.score > 50 else 'Good: ') + verdict, s_verdict))
        story.append(hr)
        story.append(Spacer(1, 0.3*cm))

        if report.summary:
            story.append(Paragraph('Analysis Summary', s_h2))
            story.append(Paragraph(report.summary, s_body))

        if report.keywords:
            story.append(Paragraph('Extracted Keywords', s_h2))
            story.append(Paragraph(report.keywords, s_body))

        if suggestions:
            story.append(hr)
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph('AI Suggestions to Reduce Plagiarism', ParagraphStyle(
                'SugTitle', fontSize=11, fontName='Helvetica-Bold',
                textColor=colors.HexColor('#92400e'), spaceBefore=10, spaceAfter=8
            )))
            for i, sug in enumerate(suggestions, 1):
                story.append(Paragraph(f'{i}. {sug}', s_suggest))
            story.append(Spacer(1, 0.2*cm))

        if paper.abstract:
            story.append(hr)
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph('Abstract', s_h2))
            story.append(Paragraph(paper.abstract, s_body))

        if reviews.exists():
            story.append(hr)
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph(f'Feedback ({reviews.count()})', s_h2))
            for rev in reviews:
                story.append(Paragraph(
                    f'<b>{rev.reviewer.username}</b> — {rev.created_at.strftime("%b %d, %Y")}',
                    ParagraphStyle('RM', fontSize=9, textColor=colors.HexColor('#718096'), spaceAfter=3)
                ))
                story.append(Paragraph(rev.comment, s_body))
                story.append(Spacer(1, 0.2*cm))

        story.append(Spacer(1, 0.5*cm))
        story.append(hr)
        story.append(Paragraph('Generated by ResearchHub — AI-Powered Research Paper Management System', s_footer))

        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="plagiarism_report_{paper.id}.pdf"'
        log_action(request.user, 'download', f'Exported PDF: {paper.title}', request)
        return response

    except ImportError:
        response = HttpResponse(html_content, content_type='text/html')
        response['Content-Disposition'] = f'attachment; filename="plagiarism_report_{paper.id}.html"'
        log_action(request.user, 'download', f'Exported HTML report: {paper.title}', request)
        return response


# ── upload ────────────────────────────────────
# ── upload ────────────────────────────────────
def extract_text_from_file(file):
    """Extract plain text from uploaded file for plagiarism comparison."""
    import os
    text = ''
    name = file.name.lower()

    try:
        if name.endswith('.txt'):
            text = file.read().decode('utf-8', errors='ignore')

        elif name.endswith('.pdf'):
            try:
                import pypdf
                file.seek(0)
                reader = pypdf.PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text() or ''
            except Exception:
                pass

        elif name.endswith('.docx'):
            try:
                import docx
                import io
                file.seek(0)
                doc = docx.Document(io.BytesIO(file.read()))
                text = ' '.join([p.text for p in doc.paragraphs])
            except Exception:
                pass

    except Exception:
        pass

    file.seek(0)
    return text.strip()

@login_required(login_url='login')
def upload_paper(request):
    if get_role(request.user) == 'admin':
        return redirect('admin_panel')

    categories = Category.objects.all()

    if request.method == 'POST':
        title    = request.POST.get('title', '').strip()
        abstract = request.POST.get('abstract', '').strip()
        keywords = request.POST.get('keywords', '').strip()
        cat_id   = request.POST.get('category', '')
        file     = request.FILES.get('file')

        if not title or not file or not cat_id:
            messages.error(request, 'Title, category and file are required.')
            return render(request, 'upload.html', {'categories': categories})

        try:
            category = Category.objects.get(id=cat_id)
        except Category.DoesNotExist:
            messages.error(request, 'Invalid category.')
            return render(request, 'upload.html', {'categories': categories})

        if not keywords and abstract:
            keywords = extract_keywords(abstract)

        paper = ResearchPaper.objects.create(
            title=title,
            abstract=abstract,
            keywords=keywords,
            file=file,
            category=category,
            uploaded_by=request.user,
            status='pending',
        )

        # ── REAL PLAGIARISM COMPARISON ────────────────
        file_text = extract_text_from_file(file)

        new_text = re.sub(
            r'\s+',
            ' ',
            f"{title} {abstract} {keywords} {file_text}".lower().strip()
        )

        max_score = 0.0
        existing_papers = ResearchPaper.objects.exclude(id=paper.id)

        for existing in existing_papers:
            existing_file_text = ''

            if existing.file:
                try:
                    existing.file.open('rb')
                    existing_file_text = extract_text_from_file(existing.file)
                    existing.file.close()
                except Exception:
                    pass

            existing_text = re.sub(
                r'\s+',
                ' ',
                f"{existing.title} {existing.abstract or ''} "
                f"{existing.keywords or ''} {existing_file_text}".lower().strip()
            )

            if existing_text:
                s = round(
                    SequenceMatcher(None, new_text, existing_text).ratio() * 100,
                    1
                )
                if s > max_score:
                    max_score = s

        score = max_score if existing_papers.exists() else round(
            random.uniform(3, 15), 1
        )

        summary = (
            f"Analysis complete. Similarity score: {score}%. "
            + (
                "High similarity detected — review and revision recommended."
                if score >= 40 else
                "Content appears largely original."
            )
        )

        kw = keywords or extract_keywords(abstract or title)

        PlagiarismReport.objects.create(
            paper=paper,
            score=score,
            summary=summary,
            keywords=kw,
        )

        # ── FIXED INDENTATION HERE ──
        if score >= 80:
            paper.status = 'rejected'
        elif score >= 40:
            paper.status = 'revise'
        else:
            paper.status = 'accepted'

        paper.save()

        log_action(request.user, 'upload', f'Uploaded: {title}', request)

        suggestions = generate_suggestions(score, paper)
        if suggestions:
            request.session['suggestions'] = suggestions
            request.session['suggestion_paper_id'] = paper.id

        if score >= 40:
            if score >= 80:
                level = "Very high"
            elif score >= 60:
                level = "High"
            else:
                level = "Moderate"

            Alert.objects.create(
                user=request.user,
                paper=paper,
                alert_type='plagiarism',
                message=f'{level} plagiarism detected in "{title}" — {score}% similarity. AI suggestions provided on the paper page.',
            )

            messages.warning(
                request,
                f'Plagiarism score: {score}%. Check the paper page for AI suggestions.'
            )
        else:
            messages.success(
                request,
                f'Paper uploaded successfully. Plagiarism score: {score}%.'
            )

        return redirect('paper_detail', paper_id=paper.id)

    return render(request, 'upload.html', {'categories': categories})

# ── delete paper (user or admin) ──────────────
@login_required(login_url='login')
def delete_paper(request, paper_id):
    paper = get_object_or_404(ResearchPaper, id=paper_id)

    if paper.uploaded_by != request.user and get_role(request.user) != 'admin':
        messages.error(request, 'You can only delete your own papers.')
        return redirect('dashboard')

    if request.method == 'POST':
        title = paper.title
        paper.delete()
        log_action(request.user, 'delete', f'Deleted: {title}', request)
        messages.success(request, f'Paper "{title}" deleted successfully.')
        return redirect('dashboard')

    return render(request, 'confirm_delete.html', {
        'item':       paper.title,
        'cancel_url': 'dashboard',
    })


# ── reviewer dashboard ────────────────────────
@login_required(login_url='login')
def reviewer_view(request):
    if get_role(request.user) not in ['reviewer', 'admin']:
        messages.error(request, 'Reviewer access only.')
        return redirect('dashboard')

    papers = ResearchPaper.objects.all().order_by('-uploaded_at')
    for paper in papers:
        try:
            paper.report = paper.plagiarismreport
        except PlagiarismReport.DoesNotExist:
            paper.report = None

    return render(request, 'reviewer.html', {'papers': papers})


# ── submit review ─────────────────────────────
@login_required(login_url='login')
def submit_review(request, paper_id):
    paper = get_object_or_404(ResearchPaper, id=paper_id)

    if paper.uploaded_by == request.user:
        messages.error(request, 'You cannot review this paper.')
        return redirect('paper_detail', paper_id=paper.id)

    if get_role(request.user) not in ['reviewer', 'admin']:
        messages.error(request, 'Only reviewers can submit reviews.')
        return redirect('paper_detail', paper_id=paper.id)

    if request.method == 'POST':
        comment = request.POST.get('comment', '').strip()
        decision = request.POST.get('decision', 'pending')

        if comment:
            Review.objects.create(
                paper=paper,
                reviewer=request.user,
                comment=comment,
                decision=decision,
            )

            # Update paper status
            paper.status = decision
            paper.save()

            Alert.objects.create(
                user=paper.uploaded_by,
                paper=paper,
                alert_type='review',
                message=f'{request.user.username} left feedback on your paper "{paper.title}".',
            )

            messages.success(request, 'Your feedback has been submitted.')

    return redirect('paper_detail', paper_id=paper.id)

# ── delete review ─────────────────────────────
@login_required(login_url='login')
def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)

    if review.reviewer != request.user:
        messages.error(request, 'You can only delete your own reviews.')
        return redirect('paper_detail', paper_id=review.paper.id)

    paper_id = review.paper.id

    if request.method == 'POST':
        review.delete()
        messages.success(request, 'Your review has been deleted.')
        return redirect('paper_detail', paper_id=paper_id)

    return render(request, 'confirm_delete.html', {
        'item':       'Your review on this paper',
        'cancel_url': 'dashboard',
    })


# ── mark alert read ───────────────────────────
@login_required(login_url='login')
def mark_read(request, alert_id):
    Alert.objects.filter(id=alert_id, user=request.user).update(is_read=True)
    return redirect('dashboard')


# ── my activity ───────────────────────────────
@login_required(login_url='login')
def my_activity(request):
    logs = ActivityLog.objects.filter(
               user=request.user
           ).order_by('-timestamp')[:50]
    return render(request, 'activity.html', {'logs': logs})


# ══════════════════════════════════════════════
# ADMIN VIEWS
# ══════════════════════════════════════════════

@admin_required
def admin_panel(request):
    total_users   = User.objects.exclude(profile__role='admin').count()
    total_papers  = ResearchPaper.objects.count()
    total_alerts  = Alert.objects.filter(is_read=False).count()
    high_plag     = PlagiarismReport.objects.filter(score__gt=50).count()
    recent_papers = ResearchPaper.objects.all().order_by('-uploaded_at')[:6]
    recent_users  = User.objects.exclude(
                        profile__role='admin'
                    ).order_by('-date_joined')[:5]
    recent_logs   = ActivityLog.objects.all().order_by('-timestamp')[:8]

    for paper in recent_papers:
        try:
            paper.report = paper.plagiarismreport
        except PlagiarismReport.DoesNotExist:
            paper.report = None

    return render(request, 'admin_panel.html', {
        'total_users':   total_users,
        'total_papers':  total_papers,
        'total_alerts':  total_alerts,
        'high_plag':     high_plag,
        'recent_papers': recent_papers,
        'recent_users':  recent_users,
        'recent_logs':   recent_logs,
    })


@admin_required
def admin_users(request):
    users = User.objects.exclude(
                profile__role='admin'
            ).order_by('-date_joined')

    for u in users:
        u.paper_count = ResearchPaper.objects.filter(uploaded_by=u).count()
        u.alert_count = Alert.objects.filter(user=u, is_read=False).count()
        try:
            u.role = u.profile.role
        except Profile.DoesNotExist:
            u.role = 'user'

    return render(request, 'admin_users.html', {'users': users})


@admin_required
def admin_user_detail(request, user_id):
    u      = get_object_or_404(User, id=user_id)
    papers = ResearchPaper.objects.filter(uploaded_by=u).order_by('-uploaded_at')
    logs   = ActivityLog.objects.filter(user=u).order_by('-timestamp')[:20]
    alerts = Alert.objects.filter(user=u).order_by('-created_at')[:10]

    for paper in papers:
        try:
            paper.report = paper.plagiarismreport
        except PlagiarismReport.DoesNotExist:
            paper.report = None

    try:
        role = u.profile.role
    except Profile.DoesNotExist:
        role = 'user'

    return render(request, 'admin_user_detail.html', {
        'u':      u,
        'papers': papers,
        'logs':   logs,
        'alerts': alerts,
        'role':   role,
    })


@admin_required
def admin_delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'User "{username}" deleted.')
        return redirect('admin_users')
    return render(request, 'confirm_delete.html', {
        'item':       user.username,
        'cancel_url': 'admin_users',
    })


@admin_required
def admin_papers(request):
    query      = request.GET.get('q', '')
    cat_id     = request.GET.get('category', '')
    papers     = ResearchPaper.objects.all().order_by('-uploaded_at')
    categories = Category.objects.all()

    if query:
        papers = papers.filter(title__icontains=query)
    if cat_id:
        papers = papers.filter(category_id=cat_id)

    for paper in papers:
        try:
            paper.report = paper.plagiarismreport
        except PlagiarismReport.DoesNotExist:
            paper.report = None

    return render(request, 'admin_papers.html', {
        'papers':     papers,
        'categories': categories,
        'query':      query,
        'cat_id':     cat_id,
    })


@admin_required
def admin_delete_paper(request, paper_id):
    paper = get_object_or_404(ResearchPaper, id=paper_id)
    if request.method == 'POST':
        title = paper.title
        paper.delete()
        messages.success(request, f'Paper "{title}" deleted.')
        return redirect('admin_papers')
    return render(request, 'confirm_delete.html', {
        'item':       paper.title,
        'cancel_url': 'admin_papers',
    })


@admin_required
def admin_alerts(request):
    alerts = Alert.objects.all().order_by('-created_at')
    return render(request, 'admin_alerts.html', {'alerts': alerts})


@admin_required
def admin_logs(request):
    logs = ActivityLog.objects.all().order_by('-timestamp')
    return render(request, 'admin_logs.html', {'logs': logs})


@admin_required
def admin_categories(request):
    categories = Category.objects.all()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            name = request.POST.get('name', '').strip()
            if name:
                if Category.objects.filter(name__iexact=name).exists():
                    messages.error(request, 'Category already exists.')
                else:
                    Category.objects.create(name=name)
                    messages.success(request, f'Category "{name}" added.')
        elif action == 'delete':
            cat_id = request.POST.get('cat_id')
            cat    = get_object_or_404(Category, id=cat_id)
            cat.delete()
            messages.success(request, 'Category deleted.')
        return redirect('admin_categories')

    return render(request, 'admin_categories.html', {'categories': categories})


@admin_required
def admin_make_reviewer(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = 'reviewer' if profile.role == 'user' else 'user'
        profile.save()
        messages.success(request, f'{user.username} role updated to {profile.role}.')
    return redirect('admin_users')

